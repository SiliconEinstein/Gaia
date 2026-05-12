"""Replay-build helpers for ``gaia starmap-replay`` v4.

Three responsibilities:

1. **Tick splitting** — turn each merged event into N IR-ticks, one per
   ``gaia_actions[]`` entry whose action lands an IR-side change
   (``claim`` / ``support`` / ``deduction`` / ``contradiction`` /
   ``equivalence`` / ``prior``). Events with no such action stay on the
   timeline as plain markers but produce zero ticks.

2. **Pinned canonical layout** — invoke Graphviz ``dot -Tjson0`` against
   the final compiled IR's DOT source (the same DOT the user gets from
   ``gaia starmap --format dot``) and extract per-node positions, cluster
   bounding boxes, and a viewport size so the frontend can place
   everything at canonical pinned coordinates.

3. **Per-round belief snapshots** — for each round visible in the
   growth-log stream, materialize a truncated ``LocalCanonicalGraph``
   that contains only those IR knowledges whose ``metadata.lkm_id``
   appeared in some ``graph_delta.nodes_added`` entry by end-of-round R
   (plus all knowledges we cannot map to any nodes_added — they are
   treated as always-present), keep operators / strategies whose
   variables / premises / conclusion are all in the truncated knowledge
   set, and run inference. Round-belief tables are returned as a
   ``{round_id: {claim_id: belief}}`` dict.

These helpers are shared with the ``starmap-replay`` command and unit-
tested directly so the integration tests don't have to spin up a real
``dot`` invocation or a real package compilation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from gaia.bp import InferenceEngine, lower_local_graph
from gaia.ir.graphs import LocalCanonicalGraph

# IR-side gaia_action types — each one is one tick on the IR-tick axis.
IR_TICK_ACTIONS: frozenset[str] = frozenset(
    {"claim", "support", "deduction", "contradiction", "equivalence", "prior"}
)

# Operator-type literal that carries the special red hexagon styling in
# both the static DOT renderer and the replay layout annotation.
_CONTRADICTION = "contradiction"


# ── 1. Tick splitting ────────────────────────────────────────────────────────


def split_into_ir_ticks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand each event into one tick per IR-relevant ``gaia_actions[]``.

    The returned list preserves event order and, within an event, action
    order. Each tick is a dict with::

        {
          "tick_index": int,                # global, 0-based
          "event_index": int,               # index into the input events list
          "event_id": str,
          "action_index": int,              # index into event.gaia_actions
          "action": GaiaAction (dict),
          "round_id": str | None,
          "lkm_driven": bool,               # True iff parent event has retrieval_event_ids
          "retrieval_event_ids": list[str], # carried verbatim for the LKM overlay
        }

    Events whose ``gaia_actions`` is empty (or which have no IR-relevant
    actions) contribute zero ticks. They still live on the timeline as
    markers — the frontend reads ``events`` for that.
    """
    ticks: list[dict[str, Any]] = []
    tick_index = 0
    for ev_idx, event in enumerate(events):
        actions = event.get("gaia_actions") or []
        if not isinstance(actions, list):
            continue
        retrieval_ids = list(event.get("retrieval_event_ids") or [])
        lkm_driven = len(retrieval_ids) > 0
        round_id = event.get("round_id")
        for a_idx, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            if action.get("action") not in IR_TICK_ACTIONS:
                continue
            ticks.append(
                {
                    "tick_index": tick_index,
                    "event_index": ev_idx,
                    "event_id": event.get("event_id", ""),
                    "action_index": a_idx,
                    "action": action,
                    "round_id": round_id,
                    "lkm_driven": lkm_driven,
                    "retrieval_event_ids": retrieval_ids,
                }
            )
            tick_index += 1
    return ticks


# ── 2. Pinned canonical layout ───────────────────────────────────────────────


def _parse_pos(pos: str) -> tuple[float, float] | None:
    """Parse a Graphviz ``pos`` attr ("x,y" or "x,y!") into floats."""
    if not pos:
        return None
    s = pos.rstrip("!")
    parts = s.split(",")
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def _parse_bb(bb: str) -> tuple[float, float, float, float] | None:
    """Parse a Graphviz ``bb`` attr ("x1,y1,x2,y2") into four floats."""
    if not bb:
        return None
    parts = bb.split(",")
    if len(parts) < 4:
        return None
    try:
        return (
            float(parts[0]),
            float(parts[1]),
            float(parts[2]),
            float(parts[3]),
        )
    except ValueError:
        return None


def rekey_layout_to_lkm_ids(
    layout: dict[str, Any], ir: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Re-key knowledge node entries in *layout* by their ``metadata.lkm_id``.

    The pinned layout produced by ``compute_dot_layout`` keys knowledge nodes
    by their IR-namespaced id (e.g. ``github:pkg::label``), but the
    growth-log events reference nodes by raw LKM id (e.g. ``gcn_<hex>``).
    The frontend store admits nodes by event-side id; without re-keying,
    every node misses its pinned coordinate and renders at the canvas
    centre.

    For each IR knowledge whose ``metadata.lkm_id`` is set, this function
    moves its layout entry from the IR id key to the lkm_id key. Nodes
    without an ``lkm_id`` (e.g. ``__implication_result_*`` helpers,
    operator-conclusion claims declared by the package author) keep their
    namespaced key. Strategy / operator entries (``strat_<i>`` /
    ``oper_<i>``) are also untouched — events never reference those by
    layout id.

    Returns the (possibly mutated) layout dict and a list of warnings
    naming any duplicate lkm_id collisions found in the IR.
    """
    warnings: list[str] = []
    if not layout or not ir:
        return layout, warnings

    nodes = layout.get("nodes")
    if not isinstance(nodes, dict):
        return layout, warnings

    # Build IR-id -> lkm_id mapping for knowledges that carry one.
    ir_to_lkm: dict[str, str] = {}
    seen_lkm_ids: dict[str, str] = {}  # lkm_id -> first IR id we saw it on
    for k in ir.get("knowledges", []) or []:
        kid = k.get("id")
        if not isinstance(kid, str) or not kid:
            continue
        meta = k.get("metadata") or {}
        lid = meta.get("lkm_id")
        if not isinstance(lid, str) or not lid:
            continue
        if lid in seen_lkm_ids and seen_lkm_ids[lid] != kid:
            warnings.append(
                f"duplicate lkm_id {lid!r}: IR knowledges {seen_lkm_ids[lid]!r} "
                f"and {kid!r} both claim it"
            )
            continue
        seen_lkm_ids[lid] = kid
        ir_to_lkm[kid] = lid

    # Apply the re-key: move each pinned-layout entry from its IR id to lkm_id.
    rekeyed: dict[str, dict[str, Any]] = {}
    for key, value in nodes.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        new_key = ir_to_lkm.get(key, key)
        # If two IR ids unexpectedly collide on the same lkm_id (should be
        # caught above as a warning), keep the first and record the second.
        if new_key in rekeyed:
            warnings.append(
                f"layout re-key collision at {new_key!r}: dropping later entry from {key!r}"
            )
            continue
        rekeyed[new_key] = value
    layout["nodes"] = rekeyed
    return layout, warnings


def annotate_layout_with_kinds(layout: dict[str, Any], ir: dict[str, Any]) -> dict[str, Any]:
    """Decorate every layout node entry with kind + styling info from the IR.

    The pinned layout from ``compute_dot_layout`` only carries ``(x, y)`` for
    each node. The replay frontend needs more — without ``kind`` it can't
    decide whether to render an entry as a knowledge box (claims), strategy
    ellipse (e.g. deduction / support), or operator hexagon
    (contradiction / equivalence). Additional fields (``label``,
    ``operator_type``, ``strategy_type``, ``exported``, ``prior``,
    ``module``) let the canvas mirror the static DOT output exactly without
    waiting for matching ``graph_delta`` entries to land.

    The CLI ships the IR and we know the layout key conventions:

    * ``strat_<i>`` → IR ``strategies[i]``  (kind = ``strategy``)
    * ``oper_<i>`` → IR ``operators[i]``  (kind = ``operator``)
    * everything else → IR knowledge (kind = ``knowledge``); after
      ``rekey_layout_to_lkm_ids`` the key is the raw ``lkm_id`` for IR
      knowledges that carry one, else the IR-namespaced id.

    Knowledge nodes are matched back to their IR knowledge by id (post-rekey
    keys are looked up against ``metadata.lkm_id``; anything else against
    raw IR id). Unmatched entries retain the bare ``(x, y)`` shape — the
    frontend falls back to a generic claim look.
    """
    if not layout or not ir:
        return layout

    nodes = layout.get("nodes")
    if not isinstance(nodes, dict):
        return layout

    # Build (lkm_id-or-irid → IR knowledge dict) lookup, so we can decorate
    # both pre- and post-rekey knowledge entries.
    ir_by_id: dict[str, dict[str, Any]] = {}
    ir_by_lkm: dict[str, dict[str, Any]] = {}
    for k in ir.get("knowledges", []) or []:
        kid = k.get("id")
        if isinstance(kid, str):
            ir_by_id[kid] = k
        meta = k.get("metadata") or {}
        lid = meta.get("lkm_id")
        if isinstance(lid, str) and lid:
            ir_by_lkm[lid] = k

    strategies = ir.get("strategies", []) or []
    operators = ir.get("operators", []) or []

    # Track which knowledge ids are derived (a strategy or operator
    # concludes them); knowledge nodes that aren't `setting`, `exported`,
    # or `derived` fall through to `premise`.
    derived_ids: set[str] = set()
    for s in strategies:
        c = s.get("conclusion")
        if isinstance(c, str):
            derived_ids.add(c)
    for o in operators:
        c = o.get("conclusion")
        if isinstance(c, str):
            derived_ids.add(c)

    def _knowledge_subkind(k: dict[str, Any]) -> str:
        if k.get("type") == "setting":
            return "setting"
        if k.get("exported"):
            return "exported"
        if k.get("id") in derived_ids:
            return "derived"
        return "claim"

    # Map IR knowledge id → its lkm_id (or fall through to id when the
    # knowledge doesn't carry one) so we can resolve operator/strategy
    # conclusion ids to their post-rekey layout keys.
    id_to_layout_key: dict[str, str] = {}
    for k in ir.get("knowledges", []) or []:
        kid = k.get("id")
        if not isinstance(kid, str):
            continue
        meta = k.get("metadata") or {}
        lid = meta.get("lkm_id")
        if isinstance(lid, str) and lid and lid in nodes:
            id_to_layout_key[kid] = lid
        elif kid in nodes:
            id_to_layout_key[kid] = kid

    for key, value in list(nodes.items()):
        if not isinstance(value, dict):
            continue
        # Strategy entry.
        if key.startswith("strat_"):
            try:
                idx = int(key.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            if 0 <= idx < len(strategies):
                s = strategies[idx]
                stype = s.get("type", "") or ""
                value["kind"] = "strategy"
                value["strategy_type"] = stype
                value["label"] = stype
                # Link to its conclusion + premises in layout-key space so
                # the replay store can co-admit the strategy's incident
                # claims when this strategy lands.
                concl_layout_key = id_to_layout_key.get(s.get("conclusion") or "")
                if concl_layout_key:
                    value["conclusion_id"] = concl_layout_key
                premise_keys = [
                    id_to_layout_key[p] for p in (s.get("premises") or []) if p in id_to_layout_key
                ]
                if premise_keys:
                    value["premise_ids"] = premise_keys
            continue
        # Operator entry.
        if key.startswith("oper_"):
            try:
                idx = int(key.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            if 0 <= idx < len(operators):
                o = operators[idx]
                otype = o.get("operator", "") or ""
                value["kind"] = "operator"
                value["operator_type"] = otype
                if otype == _CONTRADICTION:
                    value["label"] = "⊗ contradiction"
                else:
                    value["label"] = f"⊙ {otype}".rstrip()
                # Link to its conclusion + variables in layout-key space.
                # Important for contradiction / equivalence — the static
                # DOT renders both the operator hexagon AND the helper
                # claim that holds the conclusion as a knowledge box, so
                # the replay must admit both in tandem when the operator
                # action lands.
                concl_layout_key = id_to_layout_key.get(o.get("conclusion") or "")
                if concl_layout_key:
                    value["conclusion_id"] = concl_layout_key
                variable_keys = [
                    id_to_layout_key[v] for v in (o.get("variables") or []) if v in id_to_layout_key
                ]
                if variable_keys:
                    value["variable_ids"] = variable_keys
            continue
        # Knowledge entry — try lkm_id first (post-rekey), then raw IR id.
        k = ir_by_lkm.get(key) or ir_by_id.get(key)
        if k is None:
            continue
        sub = _knowledge_subkind(k)
        value["kind"] = "knowledge"
        value["sub_kind"] = sub
        title = k.get("title") or k.get("label") or ""
        value["label"] = ("★ " if k.get("exported") else "") + str(title)
        value["exported"] = bool(k.get("exported"))
        value["module"] = k.get("module")
        prior = (k.get("metadata") or {}).get("prior")
        if isinstance(prior, (int, float)):
            value["prior"] = float(prior)
        # Defensive: if IR knowledge dict carries `prior` directly (some
        # tooling stamps it at the top level rather than under metadata).
        elif isinstance(k.get("prior"), (int, float)):
            value["prior"] = float(k["prior"])

    return layout


_BRIDGE_ACTION_KINDS: frozenset[str] = frozenset(
    {"deduction", "support", "contradiction", "equivalence"}
)
_PAIR_BRIDGE_ACTION_KINDS: frozenset[str] = frozenset({"support", "contradiction", "equivalence"})


@dataclass(frozen=True)
class _PendingBridgeAction:
    """Event-side symbol that still needs a fallback layout bridge."""

    kind: str
    symbol: str
    module: str
    position: int


@dataclass(frozen=True)
class _BridgeContext:
    """Shared indexes used by replay symbol bridging."""

    ir: dict[str, Any]
    nodes: dict[str, Any]
    strategy_signatures: dict[tuple[Any, ...], str]
    pair_signatures: dict[tuple[Any, ...], str]
    knowledge_module_by_id: dict[str, str]
    knowledge_ids: set[str]


def _bridge_ir_to_lkm(ir: dict[str, Any]) -> dict[str, str]:
    """Build the IR-id to LKM-id map used by post-rekey layout matching."""
    ir_to_lkm: dict[str, str] = {}
    for knowledge in ir.get("knowledges", []) or []:
        kid = knowledge.get("id")
        meta = knowledge.get("metadata") or {}
        lid = meta.get("lkm_id")
        if isinstance(kid, str) and isinstance(lid, str) and lid:
            ir_to_lkm[kid] = lid
    return ir_to_lkm


def _bridge_lkm_id(kid: str | None, ir_to_lkm: dict[str, str]) -> str | None:
    """Return the LKM id for an IR id, falling back to the IR id itself."""
    if not isinstance(kid, str):
        return None
    return ir_to_lkm.get(kid, kid)


def _record_bridge_signature(
    sig_dict: dict[tuple[Any, ...], str], sig: tuple[Any, ...], target: str
) -> None:
    """Record a signature-to-layout-key mapping, marking collisions ambiguous."""
    existing = sig_dict.get(sig)
    if existing is None and sig not in sig_dict:
        sig_dict[sig] = target
    elif existing != target:
        sig_dict[sig] = ""


def _build_bridge_signatures(
    ir: dict[str, Any], ir_to_lkm: dict[str, str]
) -> tuple[dict[tuple[Any, ...], str], dict[tuple[Any, ...], str]]:
    """Index IR strategies/operators by the edge signatures emitted in events."""
    strategy_signatures: dict[tuple[Any, ...], str] = {}
    pair_signatures: dict[tuple[Any, ...], str] = {}
    for i, strategy in enumerate(ir.get("strategies", []) or []):
        conclusion = strategy.get("conclusion")
        premises = strategy.get("premises", []) or []
        if not conclusion or not premises:
            continue
        conclusion_lkm = _bridge_lkm_id(conclusion, ir_to_lkm)
        premise_lkms = frozenset(
            lkm for lkm in (_bridge_lkm_id(premise, ir_to_lkm) for premise in premises) if lkm
        )
        target = f"strat_{i}"
        _record_bridge_signature(
            strategy_signatures, ("strategy", premise_lkms, conclusion_lkm), target
        )
        strategy_type = strategy.get("type")
        if isinstance(strategy_type, str) and len(premise_lkms) == 1 and conclusion_lkm:
            (premise_lkm,) = premise_lkms
            _record_bridge_signature(
                pair_signatures, (strategy_type, frozenset({premise_lkm, conclusion_lkm})), target
            )
    for i, operator in enumerate(ir.get("operators", []) or []):
        kind = operator.get("operator")
        variables = operator.get("variables", []) or []
        if not kind or not variables:
            continue
        variable_lkms = frozenset(
            lkm for lkm in (_bridge_lkm_id(variable, ir_to_lkm) for variable in variables) if lkm
        )
        if len(variable_lkms) >= 2:
            _record_bridge_signature(pair_signatures, (kind, variable_lkms), f"oper_{i}")
    return strategy_signatures, pair_signatures


def _build_bridge_knowledge_indexes(ir: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    """Return knowledge module lookup plus the set of live IR knowledge ids."""
    knowledge_module_by_id: dict[str, str] = {}
    knowledge_ids: set[str] = set()
    for knowledge in ir.get("knowledges", []) or []:
        kid = knowledge.get("id")
        if isinstance(kid, str) and kid:
            knowledge_ids.add(kid)
            module = knowledge.get("module")
            if isinstance(module, str) and module:
                knowledge_module_by_id[kid] = module
    return knowledge_module_by_id, knowledge_ids


def _build_bridge_context(ir: dict[str, Any], nodes: dict[str, Any]) -> _BridgeContext:
    """Build all indexes needed by edge-signature and fallback bridging."""
    ir_to_lkm = _bridge_ir_to_lkm(ir)
    strategy_signatures, pair_signatures = _build_bridge_signatures(ir, ir_to_lkm)
    knowledge_module_by_id, knowledge_ids = _build_bridge_knowledge_indexes(ir)
    return _BridgeContext(
        ir=ir,
        nodes=nodes,
        strategy_signatures=strategy_signatures,
        pair_signatures=pair_signatures,
        knowledge_module_by_id=knowledge_module_by_id,
        knowledge_ids=knowledge_ids,
    )


def _gcn(s: Any) -> str | None:
    """Return event graph ids, which use the ``gcn_`` prefix."""
    return s if isinstance(s, str) and s.startswith("gcn_") else None


def _bucket_edges_by_kind(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Bucket event ``edges_added`` records by their ``kind`` field."""
    edges_by_kind: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        edges_by_kind.setdefault(edge.get("kind") or "", []).append(edge)
    return edges_by_kind


def _claim_bridge_target(nodes: dict[str, Any], symbol: str, target: str) -> bool:
    """Alias ``target``'s layout entry to ``symbol`` and stamp canonical ids."""
    if target not in nodes or symbol in nodes:
        return False
    aliased_entry = dict(nodes[target])
    aliased_entry["canonical_id"] = target
    nodes[target]["canonical_id"] = target
    nodes[symbol] = aliased_entry
    return True


def _deduction_signature_target(
    context: _BridgeContext,
    edges_by_kind: dict[str, list[dict[str, Any]]],
    position: int,
) -> str | None:
    """Find a strategy target from deduction edges in the current event."""
    deduction_edges = edges_by_kind.get("deduction") or []
    candidate: str | None = None
    if position < len(deduction_edges):
        edge = deduction_edges[position]
        from_id = _gcn(edge.get("from"))
        to_id = _gcn(edge.get("to"))
        if from_id and to_id:
            candidate = context.strategy_signatures.get(("strategy", frozenset({from_id}), to_id))
    if candidate:
        return candidate
    gcns_from = {from_id for edge in deduction_edges if (from_id := _gcn(edge.get("from")))}
    gcns_to = {to_id for edge in deduction_edges if (to_id := _gcn(edge.get("to")))}
    premises = gcns_from - gcns_to
    conclusions = gcns_to - gcns_from
    if len(conclusions) == 1 and premises:
        conclusion = next(iter(conclusions))
        return context.strategy_signatures.get(("strategy", frozenset(premises), conclusion))
    return None


def _pair_signature_target(
    context: _BridgeContext,
    edges_by_kind: dict[str, list[dict[str, Any]]],
    kind: str,
    position: int,
) -> str | None:
    """Find an operator/strategy target from a two-endpoint relation edge."""
    kind_edges = edges_by_kind.get(kind) or []
    if position >= len(kind_edges):
        return None
    edge = kind_edges[position]
    from_id = _gcn(edge.get("from"))
    to_id = _gcn(edge.get("to"))
    if not from_id or not to_id:
        return None
    return context.pair_signatures.get((kind, frozenset({from_id, to_id})))


def _edge_signature_candidate(
    context: _BridgeContext,
    action: dict[str, Any],
    edges_by_kind: dict[str, list[dict[str, Any]]],
    kind_seen: dict[str, int],
) -> tuple[str, str] | None:
    """Return ``(symbol, target)`` for an edge-signature bridge candidate."""
    kind = action.get("action")
    symbol = action.get("symbol")
    if not isinstance(kind, str) or not isinstance(symbol, str) or not symbol:
        return None
    position = kind_seen.get(kind, 0)
    kind_seen[kind] = position + 1
    if symbol in context.nodes:
        return None
    if kind == "deduction":
        target = _deduction_signature_target(context, edges_by_kind, position)
    elif kind in _PAIR_BRIDGE_ACTION_KINDS:
        target = _pair_signature_target(context, edges_by_kind, kind, position)
    else:
        target = None
    if target and target in context.nodes:
        return symbol, target
    return None


def _bridge_edge_signature_events(context: _BridgeContext, events: list[dict[str, Any]]) -> int:
    """Apply the strongest bridge path: event edge signatures."""
    bridged = 0
    for event in events:
        delta = event.get("graph_delta") or {}
        actions = event.get("gaia_actions") or []
        edges = delta.get("edges_added") or []
        if not actions or not edges:
            continue
        edges_by_kind = _bucket_edges_by_kind(edges)
        kind_seen: dict[str, int] = {}
        for action in actions:
            if not isinstance(action, dict):
                continue
            candidate = _edge_signature_candidate(context, action, edges_by_kind, kind_seen)
            if candidate is None:
                continue
            symbol, target = candidate
            bridged += int(_claim_bridge_target(context.nodes, symbol, target))
    return bridged


def _target_index(target: str, prefix: str) -> int | None:
    """Parse ``strat_<i>`` / ``oper_<i>`` target indexes."""
    if not target.startswith(prefix):
        return None
    try:
        return int(target.split("_", 1)[1])
    except (ValueError, IndexError):
        return None


def _strategy_for_target(ir: dict[str, Any], target: str) -> dict[str, Any] | None:
    """Return the IR strategy dict for a ``strat_<i>`` target."""
    index = _target_index(target, "strat_")
    strategies = ir.get("strategies", []) or []
    if index is None or not (0 <= index < len(strategies)):
        return None
    strategy = strategies[index]
    return strategy if isinstance(strategy, dict) else None


def _operator_for_target(ir: dict[str, Any], target: str) -> dict[str, Any] | None:
    """Return the IR operator dict for an ``oper_<i>`` target."""
    index = _target_index(target, "oper_")
    operators = ir.get("operators", []) or []
    if index is None or not (0 <= index < len(operators)):
        return None
    operator = operators[index]
    return operator if isinstance(operator, dict) else None


def _bridge_target_conclusion(ir: dict[str, Any], target: str) -> str | None:
    """Return the conclusion knowledge id for a strategy/operator target."""
    strategy = _strategy_for_target(ir, target)
    operator = _operator_for_target(ir, target) if strategy is None else None
    target_record = strategy or operator
    if target_record is None:
        return None
    conclusion = target_record.get("conclusion")
    return conclusion if isinstance(conclusion, str) else None


def _module_of_bridge_target(context: _BridgeContext, target: str) -> str | None:
    """Return the conclusion-knowledge module for a bridge target."""
    conclusion = _bridge_target_conclusion(context.ir, target)
    return context.knowledge_module_by_id.get(conclusion) if conclusion else None


def _conclusion_slug(context: _BridgeContext, target: str) -> str | None:
    """Return the Python symbol slug encoded in a relation conclusion id."""
    conclusion = _bridge_target_conclusion(context.ir, target)
    if not isinstance(conclusion, str) or "::" not in conclusion:
        return None
    return conclusion.rsplit("::", 1)[-1]


def _ir_kind_for_bridge_target(context: _BridgeContext, target: str, action_kind: str) -> bool:
    """Return whether an IR target aligns with an event-side action kind."""
    if action_kind == "deduction":
        strategy = _strategy_for_target(context.ir, target)
        return bool(strategy and strategy.get("type") == "deduction")
    if action_kind not in _PAIR_BRIDGE_ACTION_KINDS:
        return False
    operator = _operator_for_target(context.ir, target)
    if operator is not None:
        return bool(operator.get("operator") == action_kind)
    strategy = _strategy_for_target(context.ir, target)
    return bool(strategy and strategy.get("type") == action_kind)


def _bridge_target_refs(context: _BridgeContext, target: str) -> list[str]:
    """Collect knowledge ids referenced by a bridge target."""
    refs: list[str] = []
    strategy = _strategy_for_target(context.ir, target)
    operator = _operator_for_target(context.ir, target) if strategy is None else None
    target_record = strategy or operator
    if target_record is None:
        return refs
    conclusion = target_record.get("conclusion")
    if isinstance(conclusion, str):
        refs.append(conclusion)
    field = "premises" if strategy is not None else "variables"
    for ref in target_record.get(field) or []:
        if isinstance(ref, str):
            refs.append(ref)
    return refs


def _ir_refs_consistent(context: _BridgeContext, target: str) -> bool:
    """Return whether a fallback target references only live IR knowledges."""
    refs = _bridge_target_refs(context, target)
    return bool(refs) and all(ref in context.knowledge_ids for ref in refs)


def _refresh_already_bridged(nodes: dict[str, Any]) -> set[str]:
    """Return canonical strat_/oper_ ids already claimed by event aliases."""
    already: set[str] = set()
    for entry in nodes.values():
        if not isinstance(entry, dict):
            continue
        canonical_id = entry.get("canonical_id")
        if isinstance(canonical_id, str) and canonical_id:
            already.add(canonical_id)
    return already


def _action_module(action: dict[str, Any]) -> str | None:
    """Return the stem of ``action.file`` when it names a Python file."""
    file_name = action.get("file")
    if not isinstance(file_name, str) or not file_name.endswith(".py"):
        return None
    base = file_name.rsplit("/", 1)[-1]
    return base[:-3] if base.endswith(".py") else None


def _collect_pending_bridge_actions(
    events: list[dict[str, Any]], nodes: dict[str, Any]
) -> list[_PendingBridgeAction]:
    """Collect unbridged event-side symbols eligible for file-based fallback."""
    file_kind_seen: dict[tuple[str, str], int] = {}
    pending: list[_PendingBridgeAction] = []
    for event in events:
        for action in event.get("gaia_actions") or []:
            if not isinstance(action, dict):
                continue
            kind = action.get("action")
            symbol = action.get("symbol")
            if not isinstance(kind, str) or not isinstance(symbol, str) or not symbol:
                continue
            if kind not in _BRIDGE_ACTION_KINDS:
                continue
            module = _action_module(action)
            if module is None:
                continue
            position = file_kind_seen.get((module, kind), 0)
            file_kind_seen[(module, kind)] = position + 1
            if symbol not in nodes:
                pending.append(_PendingBridgeAction(kind, symbol, module, position))
    return pending


def _bridge_target_keys(context: _BridgeContext, module: str, kind: str) -> list[str]:
    """Return canonical layout targets matching a fallback module/kind pair."""
    already = _refresh_already_bridged(context.nodes)
    targets: list[str] = []
    for target_key in list(context.nodes.keys()):
        if not (target_key.startswith("strat_") or target_key.startswith("oper_")):
            continue
        if target_key in already:
            continue
        if _module_of_bridge_target(context, target_key) != module:
            continue
        if not _ir_kind_for_bridge_target(context, target_key, kind):
            continue
        targets.append(target_key)
    return targets


def _apply_symbol_name_fallback(
    context: _BridgeContext, pending: list[_PendingBridgeAction]
) -> tuple[int, list[str]]:
    """Bridge by matching action symbols to IR conclusion-id slugs."""
    bridged = 0
    warnings: list[str] = []
    for item in pending:
        if item.symbol in context.nodes:
            continue
        for target_key in _bridge_target_keys(context, item.module, item.kind):
            if _conclusion_slug(context, target_key) != item.symbol:
                continue
            bridged += int(_claim_bridge_target(context.nodes, item.symbol, target_key))
            warnings.append(
                f"symbol-name fallback: bridged {item.symbol!r} (kind={item.kind!r}, "
                f"file={item.module}.py) to {target_key!r} via IR conclusion-id slug."
            )
            break
    return bridged, warnings


def _apply_file_uniqueness_fallback(
    context: _BridgeContext, pending: list[_PendingBridgeAction]
) -> tuple[int, list[str]]:
    """Bridge when exactly one sane unclaimed IR target exists for a file/kind."""
    bridged = 0
    warnings: list[str] = []
    for item in pending:
        if item.symbol in context.nodes:
            continue
        candidates = _bridge_target_keys(context, item.module, item.kind)
        if len(candidates) != 1 or not _ir_refs_consistent(context, candidates[0]):
            continue
        bridged += int(_claim_bridge_target(context.nodes, item.symbol, candidates[0]))
        warnings.append(
            f"file-uniqueness fallback: bridged {item.symbol!r} (kind={item.kind!r}, "
            f"file={item.module}.py) to {candidates[0]!r} as the sole unbridged "
            "candidate of that kind in that module."
        )
    return bridged, warnings


def _positional_target_keys(context: _BridgeContext, module: str, kind: str) -> list[str]:
    """Return fallback targets in the same declaration order as the IR."""
    targets: list[str] = []
    prefixes = ("strat_",) if kind == "deduction" else ("oper_", "strat_")
    counts = {
        "strat_": len(context.ir.get("strategies", []) or []),
        "oper_": len(context.ir.get("operators", []) or []),
    }
    already = _refresh_already_bridged(context.nodes)
    for prefix in prefixes:
        for index in range(counts[prefix]):
            key = f"{prefix}{index}"
            if key not in context.nodes or key in already:
                continue
            if _module_of_bridge_target(context, key) != module:
                continue
            if _ir_kind_for_bridge_target(context, key, kind):
                targets.append(key)
    return targets


def _apply_positional_fallback(
    context: _BridgeContext, pending: list[_PendingBridgeAction]
) -> tuple[int, list[str]]:
    """Bridge remaining symbols by event order within each source file and kind."""
    bridged = 0
    warnings: list[str] = []
    by_bucket: dict[tuple[str, str], list[_PendingBridgeAction]] = {}
    for item in pending:
        if item.symbol not in context.nodes:
            by_bucket.setdefault((item.module, item.kind), []).append(item)
    for (module, kind), unbridged in by_bucket.items():
        ir_targets = _positional_target_keys(context, module, kind)
        for index, item in enumerate(sorted(unbridged, key=lambda entry: entry.position)):
            if index >= len(ir_targets):
                break
            target_key = ir_targets[index]
            if not _ir_refs_consistent(context, target_key):
                continue
            bridged += int(_claim_bridge_target(context.nodes, item.symbol, target_key))
            warnings.append(
                f"positional fallback: bridged {item.symbol!r} "
                f"(kind={item.kind!r}, file={module}.py) to {target_key!r} "
                "by IR declaration order — no edge-signature or symbol-name match was available."
            )
    return bridged, warnings


def _bridge_fallback_events(
    context: _BridgeContext, events: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    """Apply file/module fallback bridge strategies after signature matching."""
    pending = _collect_pending_bridge_actions(events, context.nodes)
    if not pending:
        return 0, []
    bridged = 0
    warnings: list[str] = []
    for apply_fallback in (
        _apply_symbol_name_fallback,
        _apply_file_uniqueness_fallback,
        _apply_positional_fallback,
    ):
        count, fallback_warnings = apply_fallback(context, pending)
        bridged += count
        warnings.extend(fallback_warnings)
    return bridged, warnings


def bridge_event_symbols_to_layout(
    layout: dict[str, Any],
    ir: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Add layout entries for event-side strategy / operator symbols.

    Events reference deduction-pivot nodes by ``gfac_*`` ids (the
    deduction backbone) and support/contradiction/equivalence operator
    nodes by human-readable ids like ``older_dmc_enhancement_vs_revised_dmc_benchmarks``.
    Neither matches the IR-side ``strat_<i>`` / ``oper_<i>`` layout keys.

    The bridge runs four strategies in order of falling specificity. The
    first that succeeds for a given event-side symbol claims the match;
    subsequent strategies skip already-bridged symbols.

    1. **Edge-signature match** — match (premises/variables, conclusion)
       lkm-id sets between an IR strategy/operator and the edges that
       landed in the same event as the symbol. Reliable when the event
       payload carries a faithful ``graph_delta``.

    2. **File + symbol-name match** — when the action's ``file`` field
       is a fully-qualified ``.py`` path, derive the source module from
       the file stem and try to match ``action.symbol`` against the
       conclusion-id slug (last ``::``-segment) of an unbridged IR
       operator/strategy whose conclusion knowledge lives in that
       module. Catches the case where the agent emitted a structurally-
       broken ``graph_delta`` but the symbol name still matches what
       the package author actually committed.

    3. **File + kind + uniqueness** — when the action's ``file`` is
       fully-qualified and there is exactly one unbridged IR
       operator/strategy of that kind in that module, claim it.

    4. **Positional-in-file fallback** — for the Nth event-side
       ``(kind, file)`` action emitted across the whole log, claim the
       Nth unbridged IR operator/strategy of matching kind in matching
       module (in IR declaration order). Sanity gate: the IR
       operator/strategy's referenced ids must all resolve to IR
       knowledges that exist (rejects phantom claims). Emits a
       ``build_warning`` per positional fire so the auditor can trace
       which event-side symbol was bridged by chronology rather than
       structure.

    All bridged matches alias the layout entry from ``strat_<i>`` /
    ``oper_<i>`` to the event-side symbol id (a copy — the original entry
    stays so other callers that expect ``strat_<i>`` keys keep working).
    Both alias and canonical entry are stamped with ``canonical_id`` so
    the replay store can dedupe at final-state reconciliation.

    The logic is deliberately tolerant: ambiguous or non-matching cases
    are silently skipped (the frontend falls back to viewport-centre for
    unmatched symbols, same as before this fix).
    """
    warnings: list[str] = []
    if not layout or not ir or not events:
        return layout, warnings

    nodes = layout.get("nodes")
    if not isinstance(nodes, dict):
        return layout, warnings

    context = _build_bridge_context(ir, nodes)
    bridged = _bridge_edge_signature_events(context, events)
    fallback_count, fallback_warnings = _bridge_fallback_events(context, events)
    bridged += fallback_count
    warnings.extend(fallback_warnings)

    if bridged:
        warnings.append(f"bridged {bridged} event-side symbol(s) to pinned positions")
    return layout, warnings


def annotate_ticks_with_survival(
    ticks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    layout: dict[str, Any] | None,
    ir: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Stamp ``survives_to_final`` on each tick + return orphan-tick warnings.

    A tick "survives to final" iff its ``action.symbol`` resolves — via the
    fully-bridged layout — to an entity that is present in the final IR:

    * ``claim``: the symbol is the id (or ``metadata.lkm_id``) of an IR
      knowledge.
    * ``deduction`` / ``support``: the symbol bridges to a ``strat_<i>``
      whose strategy is in the final IR. (The bridge in
      ``bridge_event_symbols_to_layout`` only aliases symbols whose
      ``(premises, conclusion)`` signature matches an IR strategy, so any
      symbol that ends up in the layout under a strategy entry survives by
      construction.)
    * ``contradiction`` / ``equivalence``: the symbol bridges to an
      ``oper_<i>`` whose operator is in the final IR.
    * ``prior``: the prior's target node (drawn from
      ``payload.target_lkm_id`` / ``payload.priors`` /
      ``payload.claim_ids`` / ``graph_delta.edges_added`` of kind ``prior``)
      is in the final IR. When no target can be determined at all the
      tick is treated as surviving (priors are a side channel and don't
      add canvas content).
    * Any other action type (``metadata_update`` etc.): treated as
      surviving — it doesn't admit canvas content anyway.

    When *layout* or *ir* is missing (fixture / no-IR build), every tick
    is marked ``True`` and no warnings emit — survival can't be checked
    so we degrade to current behaviour.

    Mutates and returns *ticks*. The returned warnings list contains a
    single line per orphan tick naming its ``event_id`` + symbol.
    """
    warnings: list[str] = []
    if not ticks:
        return ticks, warnings

    # When we don't have enough context to judge, default everything True
    # (matches pre-fix behaviour for fixtures without IR / layout).
    if not layout or not ir:
        for t in ticks:
            t["survives_to_final"] = True
        return ticks, warnings

    layout_nodes = layout.get("nodes") or {}
    if not isinstance(layout_nodes, dict):
        for t in ticks:
            t["survives_to_final"] = True
        return ticks, warnings

    # Build the set of layout keys that map to a surviving strategy /
    # operator. The bridge stamps ``canonical_id`` on aliased entries; we
    # accept either form (canonical or alias) as "this strategy/operator
    # is in the final IR".
    surviving_strat_keys: set[str] = set()
    surviving_oper_keys: set[str] = set()
    n_strats = len(ir.get("strategies", []) or [])
    n_opers = len(ir.get("operators", []) or [])
    for key, value in layout_nodes.items():
        if not isinstance(value, dict):
            continue
        kind = value.get("kind")
        cid = value.get("canonical_id") or key
        if kind == "strategy":
            # canonical_id should be strat_<i> for both the canonical entry
            # and any bridged aliases. Accept the entry only if its
            # underlying strategy index is in range of the final IR.
            if cid.startswith("strat_"):
                try:
                    idx = int(cid.split("_", 1)[1])
                except (ValueError, IndexError):
                    continue
                if 0 <= idx < n_strats:
                    surviving_strat_keys.add(key)
        elif kind == "operator" and cid.startswith("oper_"):
            try:
                idx = int(cid.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            if 0 <= idx < n_opers:
                surviving_oper_keys.add(key)

    # Build the set of "knowledge symbols" that resolve to a final-IR
    # knowledge: every IR knowledge id + every IR knowledge metadata.lkm_id.
    surviving_knowledge_symbols: set[str] = set()
    for k in ir.get("knowledges", []) or []:
        kid = k.get("id")
        if isinstance(kid, str) and kid:
            surviving_knowledge_symbols.add(kid)
        meta = k.get("metadata") or {}
        lid = meta.get("lkm_id")
        if isinstance(lid, str) and lid:
            surviving_knowledge_symbols.add(lid)

    def _prior_target_survives(ev: dict[str, Any]) -> bool:
        """Best-effort prior survival check.

        Inspects the parent event's payload + graph_delta for any target
        node id that resolves to a final-IR knowledge. Returns True when
        at least one target survives, OR when no targets can be located
        at all (priors are a side channel; default to surviving).
        """
        payload = ev.get("payload") or {}
        candidates: list[str] = []
        target_lkm = payload.get("target_lkm_id")
        if isinstance(target_lkm, str) and target_lkm:
            candidates.append(target_lkm)
        priors = payload.get("priors")
        if isinstance(priors, dict):
            candidates.extend(k for k in priors if isinstance(k, str))
        claim_ids = payload.get("claim_ids")
        if isinstance(claim_ids, list):
            candidates.extend(c for c in claim_ids if isinstance(c, str))
        delta = ev.get("graph_delta") or {}
        for e in delta.get("edges_added") or []:
            if e.get("kind") == "prior" and isinstance(e.get("to"), str):
                candidates.append(e["to"])
        if not candidates:
            return True
        return any(c in surviving_knowledge_symbols for c in candidates)

    for tick in ticks:
        action = tick.get("action") or {}
        kind = action.get("action")
        symbol = action.get("symbol")

        survives = True
        if kind == "claim":
            if isinstance(symbol, str) and symbol:
                survives = symbol in surviving_knowledge_symbols
            else:
                # No symbol — defer to default True (no canvas content
                # is admitted by the action either way).
                survives = True
        elif kind in ("deduction", "support"):
            if isinstance(symbol, str) and symbol:
                survives = symbol in surviving_strat_keys
            else:
                # Symbol-less deductions are a known shape (one action
                # covering several edges); the reconcile-final pass
                # admits the IR strategies anyway, so they're surviving.
                survives = True
        elif kind in ("contradiction", "equivalence"):
            survives = symbol in surviving_oper_keys if isinstance(symbol, str) and symbol else True
        elif kind == "prior":
            ev_idx = tick.get("event_index")
            ev = events[ev_idx] if isinstance(ev_idx, int) and 0 <= ev_idx < len(events) else None
            survives = _prior_target_survives(ev) if ev is not None else True
        else:
            # Anything else (metadata_update, contradiction_prior_modified,
            # ...) doesn't add canvas content; treat as surviving.
            survives = True

        tick["survives_to_final"] = survives
        if not survives:
            warnings.append(
                f"orphan IR-tick {tick.get('tick_index')!r} "
                f"(event {tick.get('event_id')!r}, action={kind!r}, "
                f"symbol={symbol!r}) — symbol does not resolve to the final IR; "
                f"hidden from canvas, marker desaturated on timeline."
            )

    return ticks, warnings


def topo_reorder_ticks(
    ticks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    layout: dict[str, Any] | None,
    ir: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Topologically reorder surviving ticks by IR dependency.

    The growth log emits gaia_actions in *chronological* order, but the
    lkm-to-gaia agent sometimes admits a strategy / operator before all
    of its referenced claims have been admitted (later revising which
    claims it references). Played back chronologically, this produces a
    transient frame where a contradiction hexagon's edges fan into nodes
    that haven't been drawn yet.

    Reorder rule: a strategy / operator tick fires only after every
    claim it references is admitted. Build a dependency DAG over
    surviving ticks::

        deps[T]      = {layout-keys T needs admitted first}
        provides[T]  = layout-key T admits (or None for `prior`)

    Then topologically sort by Kahn's algorithm, breaking ties on the
    original ``tick_index`` (preserves chronology when no dependency
    forces a swap).

    Per-action dep rules:

    * ``claim``        → no deps (claims are roots).
    * ``prior``        → the claim it attaches to (best-effort lookup
                          from the parent event's payload / graph_delta).
    * ``support`` /
      ``deduction``    → IR strategy's premises + conclusion (+ background
                          for deductions).
    * ``contradiction``/
      ``equivalence``  → IR operator's variables (+ conclusion if any).

    Orphans (``survives_to_final=False``) are not reordered. They remain
    interleaved in their original chronological positions; survivors
    pour through the surviving slots in topo order. After reorder,
    ``tick_index`` is re-stamped 0..N-1 to reflect the new positions;
    every other field (``event_id``, ``seq``, ``event_index``,
    ``action_index``, ``round_id``, ``lkm_driven``, ``survives_to_final``,
    etc.) is preserved.

    On a dependency cycle (defensive — should not happen in a compiled
    IR), the cycle members fall back to chronological order and a
    ``cycle detected`` warning is emitted naming them.

    When *layout* or *ir* is missing, no reorder is attempted (degraded
    behaviour for fixtures without IR / layout). Returns the original
    ticks unchanged.
    """
    warnings: list[str] = []
    if not ticks:
        return ticks, warnings
    if not layout or not ir:
        return ticks, warnings

    layout_nodes = layout.get("nodes")
    if not isinstance(layout_nodes, dict):
        return ticks, warnings

    # ── Build helper lookups ──────────────────────────────────────────
    # IR knowledge id → its layout key (lkm_id when available, else IR id).
    id_to_layout_key: dict[str, str] = {}
    knowledge_layout_keys: set[str] = set()
    for k in ir.get("knowledges", []) or []:
        kid = k.get("id")
        if not isinstance(kid, str):
            continue
        meta = k.get("metadata") or {}
        lid = meta.get("lkm_id")
        if isinstance(lid, str) and lid and lid in layout_nodes:
            id_to_layout_key[kid] = lid
            knowledge_layout_keys.add(lid)
        elif kid in layout_nodes:
            id_to_layout_key[kid] = kid
            knowledge_layout_keys.add(kid)

    strategies = ir.get("strategies", []) or []
    operators = ir.get("operators", []) or []

    # symbol-or-canonical → canonical layout id (strat_<i>/oper_<i>).
    def _canonical_of(sym: str | None) -> str | None:
        if not isinstance(sym, str) or not sym:
            return None
        entry = layout_nodes.get(sym)
        if not isinstance(entry, dict):
            return None
        cid = entry.get("canonical_id")
        if isinstance(cid, str) and cid in layout_nodes:
            return cid
        # Already a canonical strat_/oper_ key, or a knowledge symbol.
        return sym

    # canonical strat/oper id → its dependency layout-key set
    # (premises/variables/conclusion in layout-key space).
    strat_deps: dict[str, set[str]] = {}
    for i, s in enumerate(strategies):
        key = f"strat_{i}"
        if key not in layout_nodes:
            continue
        dep_keys: set[str] = set()
        for p in s.get("premises") or []:
            lk = id_to_layout_key.get(p)
            if lk:
                dep_keys.add(lk)
        for b in s.get("background") or []:
            lk = id_to_layout_key.get(b)
            if lk:
                dep_keys.add(lk)
        concl = s.get("conclusion")
        if isinstance(concl, str):
            lk = id_to_layout_key.get(concl)
            if lk:
                dep_keys.add(lk)
        strat_deps[key] = dep_keys

    oper_deps: dict[str, set[str]] = {}
    for i, o in enumerate(operators):
        key = f"oper_{i}"
        if key not in layout_nodes:
            continue
        oper_dep_keys: set[str] = set()
        for v in o.get("variables") or []:
            lk = id_to_layout_key.get(v)
            if lk:
                oper_dep_keys.add(lk)
        concl = o.get("conclusion")
        if isinstance(concl, str):
            lk = id_to_layout_key.get(concl)
            if lk:
                oper_dep_keys.add(lk)
        oper_deps[key] = oper_dep_keys

    # ── Compute provides + deps for each surviving tick ───────────────
    survivors: list[dict[str, Any]] = []
    survivor_positions: list[int] = []  # positions in original ticks list
    orphans_by_pos: dict[int, dict[str, Any]] = {}

    provides: dict[int, str | None] = {}  # tick original_idx → layout key (or None)
    tick_deps: dict[int, set[str]] = {}  # tick original_idx → set of layout keys

    def _prior_dep_keys(ev: dict[str, Any]) -> set[str]:
        """Best-effort: derive the prior's target claim layout key(s)."""
        out: set[str] = set()
        if not isinstance(ev, dict):
            return out
        payload = ev.get("payload") or {}
        candidates: list[str] = []
        tlid = payload.get("target_lkm_id")
        if isinstance(tlid, str) and tlid:
            candidates.append(tlid)
        priors = payload.get("priors")
        if isinstance(priors, dict):
            candidates.extend(k for k in priors if isinstance(k, str))
        cids = payload.get("claim_ids")
        if isinstance(cids, list):
            candidates.extend(c for c in cids if isinstance(c, str))
        delta = ev.get("graph_delta") or {}
        for e in delta.get("edges_added") or []:
            if e.get("kind") == "prior" and isinstance(e.get("to"), str):
                candidates.append(e["to"])
        for c in candidates:
            # If candidate is itself a layout key (likely a knowledge),
            # use it directly; else look up via id_to_layout_key.
            if c in knowledge_layout_keys:
                out.add(c)
            elif c in id_to_layout_key:
                out.add(id_to_layout_key[c])
        return out

    for pos, tick in enumerate(ticks):
        if tick.get("survives_to_final") is False:
            orphans_by_pos[pos] = tick
            continue
        action = tick.get("action") or {}
        kind = action.get("action")
        symbol = action.get("symbol")

        prov: str | None = None
        d: set[str] = set()

        if kind == "claim":
            if isinstance(symbol, str) and symbol in knowledge_layout_keys:
                prov = symbol
            elif isinstance(symbol, str) and symbol in id_to_layout_key:
                prov = id_to_layout_key[symbol]
        elif kind in ("deduction", "support"):
            canon = _canonical_of(symbol)
            if canon and canon.startswith("strat_") and canon in strat_deps:
                prov = canon
                d = set(strat_deps[canon])
        elif kind in ("contradiction", "equivalence"):
            canon = _canonical_of(symbol)
            if canon and canon.startswith("oper_") and canon in oper_deps:
                prov = canon
                d = set(oper_deps[canon])
        elif kind == "prior":
            ev_idx = tick.get("event_index")
            ev = events[ev_idx] if isinstance(ev_idx, int) and 0 <= ev_idx < len(events) else None
            if ev is not None:
                d = _prior_dep_keys(ev)
            prov = None
        # Other action kinds: leave both empty.

        # A tick should not list itself as a dependency.
        if prov is not None:
            d.discard(prov)

        provides[pos] = prov
        tick_deps[pos] = d
        survivors.append(tick)
        survivor_positions.append(pos)

    if not survivors:
        return ticks, warnings

    # ── Build provider-of-key map (key → set of surviving tick positions) ─
    providers_of: dict[str, set[int]] = {}
    for pos in survivor_positions:
        prov = provides.get(pos)
        if prov is not None:
            providers_of.setdefault(prov, set()).add(pos)

    # Edges: predecessor_pos → successor_pos for each (dep on prov_pos).
    # We also drop deps that no surviving tick provides (e.g. a claim
    # that's "always present" or that's already on the canvas at t=0) —
    # they impose no ordering constraint.
    in_edges: dict[int, set[int]] = {pos: set() for pos in survivor_positions}
    out_edges: dict[int, set[int]] = {pos: set() for pos in survivor_positions}
    for succ_pos in survivor_positions:
        for k in tick_deps.get(succ_pos, ()):
            for pred_pos in providers_of.get(k, ()):
                if pred_pos == succ_pos:
                    continue
                if pred_pos in out_edges and succ_pos not in out_edges[pred_pos]:
                    out_edges[pred_pos].add(succ_pos)
                    in_edges[succ_pos].add(pred_pos)

    # ── Kahn's algorithm with chronological tiebreak ──────────────────
    import heapq

    ready: list[int] = [pos for pos in survivor_positions if not in_edges[pos]]
    heapq.heapify(ready)
    sorted_positions: list[int] = []
    remaining_in_edges = {p: set(s) for p, s in in_edges.items()}
    while ready:
        pos = heapq.heappop(ready)
        sorted_positions.append(pos)
        for succ in sorted(out_edges[pos]):
            remaining_in_edges[succ].discard(pos)
            if not remaining_in_edges[succ]:
                heapq.heappush(ready, succ)

    # Cycle detection: any position not reached → it's part of a cycle.
    if len(sorted_positions) != len(survivor_positions):
        unresolved = [p for p in survivor_positions if p not in set(sorted_positions)]
        # Append unresolved survivors in their original order.
        sorted_positions.extend(sorted(unresolved))
        warnings.append(
            "topo_reorder: dependency cycle detected among ticks "
            f"{unresolved!r}; falling back to chronological order for cycle members."
        )

    # ── Re-assemble final tick array ──────────────────────────────────
    # Walk the original position slots: orphan slots stay put; survivor
    # slots receive the next survivor from the topo-sorted list.
    sorted_iter = iter(sorted_positions)
    new_ticks: list[dict[str, Any]] = []
    for orig_pos in range(len(ticks)):
        if orig_pos in orphans_by_pos:
            new_ticks.append(orphans_by_pos[orig_pos])
        else:
            try:
                next_pos = next(sorted_iter)
            except StopIteration:  # pragma: no cover - defensive
                break
            new_ticks.append(ticks[next_pos])

    # Re-stamp tick_index (0..N-1) reflecting the new positions; preserve
    # every other field.
    swap_count = 0
    for new_idx, tick in enumerate(new_ticks):
        old_idx = tick.get("tick_index")
        if isinstance(old_idx, int) and old_idx != new_idx:
            swap_count += 1
        tick["tick_index"] = new_idx

    if swap_count:
        warnings.append(
            f"topo_reorder: moved {swap_count} tick(s) from their original "
            "chronological position to satisfy IR-dependency order."
        )

    return new_ticks, warnings


def compute_dot_layout(dot_source: str, *, dot_binary: str = "dot") -> dict[str, Any]:
    """Return a replay frontend layout from Graphviz output.

    Runs Graphviz ``dot -Tjson0`` against *dot_source* and returns a layout
    dict shaped for the replay frontend.

    Output shape::

        {
          "viewport": {"width": float, "height": float},
          "nodes": {<node-id>: {"x": float, "y": float}},
          "clusters": [
              {"name": str,           # raw cluster id (e.g. "cluster_paper_x")
               "label": str,          # human label (the module name)
               "x": float,            # bb x-min in flipped coords
               "y": float,            # bb y-min
               "w": float,
               "h": float,
               "label_x": float,
               "label_y": float},
              ...
          ],
        }

    Coordinate convention: Graphviz emits y-up, but SVG is y-down. We
    flip y (``y' = bb_y2 - y``) so the frontend can consume the layout
    directly with no further transform.
    """
    binary = shutil.which(dot_binary)
    if binary is None:
        raise FileNotFoundError(
            f"Graphviz '{dot_binary}' binary not found on PATH; "
            "install graphviz to enable pinned layout."
        )

    proc = subprocess.run(
        [binary, "-Tjson0"],
        input=dot_source,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"`dot -Tjson0` failed (exit {proc.returncode}): {proc.stderr.strip()}")
    layout = json.loads(proc.stdout)

    objects = layout.get("objects") or []
    bb = _parse_bb(layout.get("bb", "")) or (0.0, 0.0, 800.0, 600.0)
    _, _, x_max, y_max = bb

    nodes: dict[str, dict[str, float]] = {}
    clusters: list[dict[str, Any]] = []
    for obj in objects:
        # Cluster objects carry a ``nodes`` array (list of indices into objects).
        if "nodes" in obj or str(obj.get("name", "")).startswith("cluster"):
            obj_bb = _parse_bb(obj.get("bb", ""))
            if not obj_bb:
                continue
            x1, y1, x2, y2 = obj_bb
            # Flip Y: graphviz origin is bottom-left, screen origin is top-left.
            cx = x1
            cy = y_max - y2
            w = x2 - x1
            h = y2 - y1
            lp = _parse_pos(obj.get("lp", ""))
            label_x, label_y = (cx + 8.0, cy + 12.0)
            if lp is not None:
                label_x = lp[0]
                label_y = y_max - lp[1]
            clusters.append(
                {
                    "name": str(obj.get("name", "")),
                    "label": str(obj.get("label", "")),
                    "x": cx,
                    "y": cy,
                    "w": w,
                    "h": h,
                    "label_x": label_x,
                    "label_y": label_y,
                }
            )
        else:
            pos = _parse_pos(str(obj.get("pos", "")))
            if pos is None:
                continue
            x, y = pos
            nodes[str(obj.get("name", ""))] = {"x": x, "y": y_max - y}

    return {
        "viewport": {"width": x_max, "height": y_max},
        "nodes": nodes,
        "clusters": clusters,
    }


# ── 3. Per-round belief snapshots ────────────────────────────────────────────


def collect_round_order(events: list[dict[str, Any]]) -> list[str]:
    """Return ``round_id`` values in the order they first appear."""
    seen: dict[str, None] = {}
    for ev in events:
        rid = ev.get("round_id")
        if rid and rid not in seen:
            seen[rid] = None
    return list(seen.keys())


def collect_round_lkm_membership(events: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Map each ``round_id`` to cumulative ``lkm_id`` membership.

    Membership includes values added in any ``graph_delta.nodes_added`` entry
    by the end of that round.

    The cumulative set for round R is monotonically non-decreasing across
    R's natural order. Knowledge nodes whose ``nodes_added`` entry has no
    ``lkm_id`` (e.g. ``inquiry:*``, ``gfac_*`` deduction shells) do not
    contribute to membership — they aren't tracked here because they don't
    correspond to IR knowledges.
    """
    round_order = collect_round_order(events)
    cumulative: dict[str, set[str]] = {}
    seen: set[str] = set()
    cursor = 0
    for ev in events:
        rid = ev.get("round_id")
        # Catch up cumulative snapshots for any round that closed.
        if rid is None:
            continue
        # Advance cursor past prior rounds in round_order until we land on rid.
        while cursor < len(round_order) and round_order[cursor] != rid:
            cumulative[round_order[cursor]] = set(seen)
            cursor += 1
        for n in (ev.get("graph_delta") or {}).get("nodes_added", []) or []:
            lid = n.get("lkm_id")
            if lid:
                seen.add(lid)
    # Snapshot the remaining (open) rounds.
    while cursor < len(round_order):
        cumulative[round_order[cursor]] = set(seen)
        cursor += 1
    return cumulative


def _truncated_canonical_graph(
    ir: dict[str, Any],
    keep_knowledge_ids: set[str],
) -> LocalCanonicalGraph | None:
    """Build a truncated ``LocalCanonicalGraph`` from *ir*.

    The graph contains only the knowledges in *keep_knowledge_ids* plus
    operators and strategies whose every reference lands inside that kept set.
    Returns ``None`` when no claim survives the cut.
    """
    knowledges = [k for k in ir.get("knowledges", []) if k.get("id") in keep_knowledge_ids]
    if not knowledges:
        return None

    # First pass — keep operators whose conclusion + every variable is in the
    # kept set; their conclusions might be helper-claims (``__*``) which are
    # part of the IR knowledges list, so we may need to expand keep_knowledge_ids.
    kept_ids = set(keep_knowledge_ids)
    operators_in: list[dict[str, Any]] = []
    for op in ir.get("operators", []) or []:
        concl = op.get("conclusion")
        variables = list(op.get("variables", []) or [])
        if concl in kept_ids and all(v in kept_ids for v in variables):
            operators_in.append(op)

    strategies_in: list[dict[str, Any]] = []
    for s in ir.get("strategies", []) or []:
        concl = s.get("conclusion")
        premises = list(s.get("premises", []) or [])
        background = list(s.get("background", []) or [])
        if concl in kept_ids and all(p in kept_ids for p in premises + background):
            strategies_in.append(s)

    payload = {
        "namespace": ir.get("namespace", "replay"),
        "package_name": ir.get("package_name", "replay"),
        "scope": ir.get("scope", "local"),
        "ir_hash": None,  # let the validator re-hash
        "knowledges": knowledges,
        "operators": operators_in,
        "strategies": strategies_in,
        "module_order": ir.get("module_order"),
        "module_titles": ir.get("module_titles"),
    }
    try:
        return LocalCanonicalGraph.model_validate(payload)
    except Exception:
        # Defensive: if the Pydantic round-trip fails (e.g. orphan refs the
        # kept-set logic missed), return None and let the caller fall back to
        # an empty round-belief table for this round.
        return None


def compute_round_beliefs(
    ir: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Return per-round beliefs from truncated IR inference.

    Runs inference on a truncated IR for each ``round_id`` and returns
    ``{round_id: {knowledge_id: belief}}``.

    The truncation is keyed on each knowledge's ``metadata.lkm_id``: a
    knowledge is kept if its ``lkm_id`` has appeared in some
    ``graph_delta.nodes_added`` entry by end-of-round R, OR if the
    knowledge has no ``lkm_id`` at all (treated as always-present —
    helper claims like ``__implication_result_*`` and any package-level
    knowledges declared by the author rather than discovered by an LKM
    walk).

    Returns an empty dict when *ir* has no knowledges (e.g. the test
    fixture, which has no compiled IR shipped) — callers degrade
    gracefully and the frontend just uses prior-only display.
    """
    if not ir or not ir.get("knowledges"):
        return {}

    # Group IR knowledges by their lkm_id (or None for "always present").
    lkm_to_kid: dict[str, str] = {}
    always_present: set[str] = set()
    for k in ir["knowledges"]:
        kid = k.get("id")
        if not kid:
            continue
        lid = (k.get("metadata") or {}).get("lkm_id")
        if isinstance(lid, str) and lid:
            lkm_to_kid[lid] = kid
        else:
            always_present.add(kid)

    cumulative = collect_round_lkm_membership(events)
    if not cumulative:
        return {}

    out: dict[str, dict[str, float]] = {}
    engine = InferenceEngine()
    for round_id, lkm_set in cumulative.items():
        keep = set(always_present)
        for lid in lkm_set:
            kid = lkm_to_kid.get(lid)
            if kid:
                keep.add(kid)
        if not keep:
            out[round_id] = {}
            continue
        canonical = _truncated_canonical_graph(ir, keep)
        if canonical is None:
            out[round_id] = {}
            continue
        try:
            fg = lower_local_graph(canonical)
            fg_errors = fg.validate()
            if fg_errors:
                out[round_id] = {}
                continue
            result = engine.run(fg)
            beliefs = result.bp_result.beliefs
        except Exception:
            out[round_id] = {}
            continue
        out[round_id] = {kid: float(beliefs[kid]) for kid in beliefs if kid in keep}
    return out
