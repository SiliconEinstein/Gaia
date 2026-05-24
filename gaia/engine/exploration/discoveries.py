"""Discovery taxonomy — what each exploration round surfaces to the human.

This is build 4a's deterministic discovery layer (SCHEMA.md §6 / §7c). It turns
engine state — the IR graph, the current round's beliefs, and the *previous*
round's beliefs — into the ``discoveries[]`` list of ``{kind, ids, note}`` records
that ``rounds.jsonl`` expects (``state.append_round``'s ``discoveries`` argument).

The v1 taxonomy (SCHEMA.md §6), ranked by what is cheap to compute from engine
state today:

================  =========================================================  ======
kind              meaning                                                    source
================  =========================================================  ======
``contradiction``  an authored ``contradict`` fired / a belief conflict       v1
``keystone``       a high in-degree node many others depend on                v1
``settled_core``   a high-belief, low-entropy stable region                   v1
================  =========================================================  ======

``bridge`` / ``fault_line`` are deferred (DESIGN §8 topology / §2a half-b). The
``discoveries[].kind`` field is an open string, so deferred kinds slot in later
without a schema migration.

Contradiction wiring (documented decision)
------------------------------------------
The ``contradiction`` discovery has two sources, both reusing
``gaia.engine.inquiry.diagnostics``:

* **Belief drop** — we *reuse* the real ``detect_large_belief_drop`` rather than
  recomputing the drop by hand. That detector reads
  ``belief_report['largest_decreases']`` (a list of ``{label, before, after,
  delta}``), so we synthesise exactly that shape from ``prev_beliefs`` (the
  baseline) vs. ``beliefs`` (current) and hand it to the detector. Building the
  ``largest_decreases`` shape from two ``dict[qid -> float]`` snapshots is
  trivial and keeps the threshold semantics identical to the inquiry review's,
  so full reuse is preferred over a hand-rolled ``abs(prev - curr) > t``.
* **Prior dissent** — we reuse ``detect_prior_dissent(ir_dict)`` directly; it
  walks the IR dict's claim nodes for multi-source prior disagreement.

This module is **pure**: every function takes its inputs explicitly and returns
fresh records. No I/O, no LKM, no IR mutation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gaia.engine.exploration.frontier import _edges_from_ir
from gaia.engine.exploration.scorer import binary_entropy
from gaia.engine.inquiry.diagnostics import (
    detect_large_belief_drop,
    detect_prior_dissent,
)

if TYPE_CHECKING:
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# §6 discovery kinds delivered in v1 (open string field; deferred kinds slot in
# without a migration).
KIND_CONTRADICTION = "contradiction"
KIND_KEYSTONE = "keystone"
KIND_SETTLED_CORE = "settled_core"

# A belief that moved down by more than this between rounds is a contradiction
# signal (mirrors inquiry diagnostics' conservative default).
BELIEF_DROP_THRESHOLD = 0.3

# A node whose binary entropy is below this is "settled" — high-confidence,
# low-uncertainty stable territory.
SETTLED_ENTROPY_EPSILON = 0.2

# A node referenced by at least this many distinct other nodes (in-degree over
# the IR adjacency) is a keystone.
KEYSTONE_MIN_INDEGREE = 3


def _labels_from_graph(ir: LocalCanonicalGraph) -> dict[str, str]:
    """Map each materialized QID to its author-given ``label`` (for the report).

    A node the author labeled (e.g. a ``contradict`` the user named
    ``spinfluc_vs_phonon``) is minted with a QID that can carry an anonymous
    ``_anon_NNN`` segment, so a discovery report keyed on the bare QID reads as an
    opaque internal id. The author's ``label`` lives on the ``Knowledge`` node;
    collecting it here lets the report surface the label the user actually wrote,
    falling back to the QID for nodes with no label.
    """
    labels: dict[str, str] = {}
    for k in ir.knowledges:
        if k.id is not None and getattr(k, "label", None):
            labels[k.id] = str(k.label)
    return labels


def _display(qid: str, labels: dict[str, str] | None) -> str:
    """The author label for ``qid`` if known, else the QID itself."""
    if labels:
        return labels.get(qid, qid)
    return qid


def _largest_decreases(
    beliefs: dict[str, float],
    prev_beliefs: dict[str, float],
) -> list[dict[str, Any]]:
    """Synthesise the ``belief_report['largest_decreases']`` shape from two snapshots.

    For every node present in *both* snapshots, emit a record
    ``{label, before, after, delta}`` (``delta = after - before``), sorted most
    negative first so the detector's threshold filter reads naturally. The label
    is the QID (the detector only uses it for the human-facing target).
    """
    rows: list[dict[str, Any]] = []
    for qid, after in beliefs.items():
        before = prev_beliefs.get(qid)
        if before is None:
            continue
        rows.append(
            {
                "label": qid,
                "before": before,
                "after": after,
                "delta": after - before,
            }
        )
    rows.sort(key=lambda r: r["delta"])
    return rows


def detect_contradictions(
    ir: LocalCanonicalGraph,
    beliefs: dict[str, float],
    prev_beliefs: dict[str, float],
    *,
    ir_dict: dict[str, Any] | None = None,
    drop_threshold: float = BELIEF_DROP_THRESHOLD,
    labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Find ``contradiction`` discoveries (SCHEMA.md §6).

    Two sources, both reusing ``inquiry/diagnostics`` (see the module docstring):
    a meaningful belief *drop* between the previous round and the current one,
    and *prior dissent* among multi-source priors in the IR.

    Args:
        ir: The package IR graph (unused directly here, kept for a uniform
            signature with the other detectors and future use).
        beliefs: Current-round ``qid -> P(x=1)``.
        prev_beliefs: Previous-round ``qid -> P(x=1)`` baseline. Empty on the
            first round (no drop can fire).
        ir_dict: Optional IR-as-dict (``graph.model_dump`` / on-disk ``ir.json``)
            for the ``detect_prior_dissent`` reuse. When omitted, dissent is
            skipped (the graph object alone cannot drive the dict-shaped detector).
        drop_threshold: Belief-drop magnitude that counts as a contradiction.
        labels: Optional ``qid -> author label`` map; when given, the human-facing
            ``note`` names the author's label instead of the bare QID (the QID is
            still the durable ``ids`` key).

    Returns:
        A list of ``{kind, ids, note}`` records, one per fired signal.
    """
    del ir  # signature uniformity; the dict form drives dissent.
    out: list[dict[str, Any]] = []

    if prev_beliefs:
        belief_report = {"largest_decreases": _largest_decreases(beliefs, prev_beliefs)}
        for diag in detect_large_belief_drop(belief_report, threshold=drop_threshold):
            before = diag.data.get("before")
            after = diag.data.get("after")
            delta = diag.data.get("delta")
            name = _display(diag.label, labels)
            note = f"belief of {name} dropped {delta:+.3f}"
            if before is not None and after is not None:
                note = f"{note} (from {before:.3f} to {after:.3f})"
            out.append({"kind": KIND_CONTRADICTION, "ids": [diag.label], "note": note})

    if ir_dict is not None:
        for diag in detect_prior_dissent(ir_dict):
            spread = diag.data.get("spread")
            note = f"prior dissent on {_display(diag.target, labels)}"
            if spread is not None:
                note = f"{note} (spread {spread:.3f})"
            out.append({"kind": KIND_CONTRADICTION, "ids": [diag.target], "note": note})

    return out


def _in_degree(ir: LocalCanonicalGraph) -> dict[str, int]:
    """Count distinct in-references per QID over the IR reference edges.

    Reuses build 2's :func:`_edges_from_ir` enumeration. Within one edge, every
    referenced QID is treated as referencing every *other* referenced QID once
    (an undirected co-reference). The in-degree of a node is then the number of
    distinct other nodes that co-appear with it across all edges — the natural
    "how many other nodes lean on this one" measure for a keystone.
    """
    referencers: dict[str, set[str]] = {}
    for _edge_kind, refs in _edges_from_ir(ir, None):
        nodes = [r for r in refs if r]
        for target in nodes:
            bucket = referencers.setdefault(target, set())
            for other in nodes:
                if other != target:
                    bucket.add(other)
    return {qid: len(others) for qid, others in referencers.items()}


def detect_keystones(
    ir: LocalCanonicalGraph,
    *,
    min_indegree: int = KEYSTONE_MIN_INDEGREE,
    labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Find ``keystone`` discoveries: high in-degree nodes (SCHEMA.md §6).

    A keystone is a node many others depend on. We count distinct co-referencing
    nodes over the IR adjacency (reusing the build-2 edge enumeration) and report
    any node whose in-degree is at least ``min_indegree``.

    Args:
        ir: The package IR graph.
        min_indegree: The in-degree threshold for keystone status.
        labels: Optional ``qid -> author label`` map for the human-facing ``note``
            (defaults to the graph's own labels). The QID stays the ``ids`` key.

    Returns:
        A list of ``{kind, ids, note}`` records, one per keystone, sorted by
        descending in-degree then QID for determinism.
    """
    if labels is None:
        labels = _labels_from_graph(ir)
    degrees = _in_degree(ir)
    keystones = sorted(
        ((qid, deg) for qid, deg in degrees.items() if deg >= min_indegree),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        {
            "kind": KIND_KEYSTONE,
            "ids": [qid],
            "note": f"{_display(qid, labels)} is referenced by {deg} other nodes",
        }
        for qid, deg in keystones
    ]


def detect_settled_core(
    beliefs: dict[str, float],
    *,
    epsilon: float = SETTLED_ENTROPY_EPSILON,
    labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Find ``settled_core`` discoveries: low-entropy stable nodes (SCHEMA.md §6).

    A node is settled when its binary entropy ``H(belief)`` is below ``epsilon``
    (reusing build 3's :func:`binary_entropy`) — i.e. the belief sits near 0 or 1
    and the node is no longer in contention.

    Args:
        beliefs: ``qid -> P(x=1)`` for the materialized nodes.
        epsilon: The entropy ceiling below which a node counts as settled.
        labels: Optional ``qid -> author label`` map for the human-facing ``note``
            (the QID stays the durable ``ids`` key).

    Returns:
        A list of ``{kind, ids, note}`` records, one per settled node, sorted by
        QID for determinism.
    """
    out: list[dict[str, Any]] = []
    for qid in sorted(beliefs):
        belief = beliefs[qid]
        entropy = binary_entropy(belief)
        if entropy < epsilon:
            out.append(
                {
                    "kind": KIND_SETTLED_CORE,
                    "ids": [qid],
                    "note": (
                        f"{_display(qid, labels)} settled at belief {belief:.3f} "
                        f"(entropy {entropy:.3f})"
                    ),
                }
            )
    return out


def compute_discoveries(
    ir: LocalCanonicalGraph,
    beliefs: dict[str, float],
    prev_beliefs: dict[str, float],
    *,
    ir_dict: dict[str, Any] | None = None,
    drop_threshold: float = BELIEF_DROP_THRESHOLD,
    settled_epsilon: float = SETTLED_ENTROPY_EPSILON,
    keystone_min_indegree: int = KEYSTONE_MIN_INDEGREE,
) -> list[dict[str, Any]]:
    """Compute the full v1 discovery set for one round (SCHEMA.md §6 / §7c).

    Runs all three v1 detectors and concatenates their ``{kind, ids, note}``
    records in taxonomy order (contradiction, keystone, settled_core). Pure: no
    I/O, no LKM, no IR mutation.

    Args:
        ir: The package IR graph.
        beliefs: Current-round ``qid -> P(x=1)``.
        prev_beliefs: Previous-round beliefs (empty on round 0 → no drop).
        ir_dict: Optional IR-as-dict for the prior-dissent contradiction source.
        drop_threshold: Belief-drop magnitude for a contradiction.
        settled_epsilon: Entropy ceiling for a settled-core node.
        keystone_min_indegree: In-degree threshold for a keystone.

    Returns:
        The concatenated list of discovery records for the round.
    """
    # Author labels for the human-facing notes — a node the user named (e.g. a
    # `contradict` labeled `spinfluc_vs_phonon`) reads as its label, not the bare
    # `_anon`-bearing QID. The QID stays the durable `ids` key.
    labels = _labels_from_graph(ir)
    discoveries: list[dict[str, Any]] = []
    discoveries.extend(
        detect_contradictions(
            ir,
            beliefs,
            prev_beliefs,
            ir_dict=ir_dict,
            drop_threshold=drop_threshold,
            labels=labels,
        )
    )
    discoveries.extend(detect_keystones(ir, min_indegree=keystone_min_indegree, labels=labels))
    discoveries.extend(detect_settled_core(beliefs, epsilon=settled_epsilon, labels=labels))
    return discoveries
