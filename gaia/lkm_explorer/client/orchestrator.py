"""The phase-aware turn state machine (CLIENT.md "Turn state machine").

This is the heart of the ``gaia-lkm-explore`` orchestrator. It is stateless between
runs and save-game driven: each invocation reads ``map.turn_phase`` (and infers
``AWAITING_CHECKPOINT`` from the presence of a result manifest), runs the
deterministic engine step for that phase via the **gaia SDK** (never by shelling
out to ``gaia``), advances the phase, and returns.

```
gaia-lkm-explore turn <pkg>
  IDLE                → rank the frontier (extract → reconcile → score), build a
                        self-contained survey task → turn-<n>.task.json,
                        set AWAITING_SURVEY, return the task path, EXIT.
  AWAITING_CHECKPOINT → compile + infer (SDK) + explore round → discovery report,
                        set IDLE, EXIT.
```

(``AWAITING_SURVEY`` with no result manifest yet is a no-op that just reports the
outstanding task — the agent is still surveying.)

All engine work goes through ``gaia.engine.*`` (the SDK): frontier extraction /
scoring, the joint root+dependency view, compile, infer, and the round
bookkeeping. The orchestrator never reasons over evidence and never runs fuzzy
LKM steps — those are the agent's, between the two phases.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gaia.lkm_explorer.client.instructions import (
    build_consolidate_instructions,
    build_survey_instructions,
)
from gaia.lkm_explorer.engine.frontier import (
    JointView,
    build_joint_view,
    reconcile_frontier,
)
from gaia.lkm_explorer.engine.handoff import (
    IslandBrief,
    SurveyResult,
    SurveyTask,
    TaskContact,
    result_path,
    task_path,
)
from gaia.lkm_explorer.engine.health import MapHealth, compute_map_health
from gaia.lkm_explorer.engine.scorer import sanitize_score_features, score_frontier
from gaia.lkm_explorer.engine.state import (
    MODE_SELECT_CONSOLIDATE,
    MODE_SELECT_EXPAND,
    TURN_PHASE_AWAITING_CHECKPOINT,
    TURN_PHASE_AWAITING_SURVEY,
    TURN_PHASE_IDLE,
    Contact,
    ExplorationMap,
    SurveyRecord,
    append_round,
    exploration_dir,
    load_map,
    load_round_beliefs,
    save_map,
    save_round_beliefs,
)


class OrchestratorError(Exception):
    """A turn could not proceed (missing map, uncompiled package, etc.)."""


@dataclass
class TurnOutcome:
    """The structured result of one ``gaia-lkm-explore turn`` invocation.

    The CLI renders this for the human; tests assert on it directly.

    Attributes:
        phase_before: ``map.turn_phase`` on entry (after manifest inference).
        phase_after: ``map.turn_phase`` on exit.
        action: a short machine label — ``"emitted_task"`` / ``"checkpointed"`` /
            ``"awaiting_survey"``.
        round: the round index this turn acted on.
        task_path: the written task envelope, when a task was emitted.
        result_path: the result envelope the agent should write, when a task was
            emitted.
        contacts: contact ids placed in the emitted task.
        seed_survey: whether the emitted task is a round-0 seed survey.
        surveyed: QIDs recorded as surveyed this turn (checkpoint).
        discoveries: the round's discovery records (checkpoint).
        discovery_labels: ``qid -> author label`` for the discovered nodes, so the
            report can name a labeled node (e.g. a ``contradict`` the user named
            ``spinfluc_vs_phonon``) by its label rather than its ``_anon``-bearing
            QID. The QID stays the durable ``discoveries[].ids`` key.
        messages: extra human-readable notes (warnings / hints).
    """

    phase_before: str
    phase_after: str
    action: str
    round: int
    task_path: str | None = None
    result_path: str | None = None
    contacts: list[str] = field(default_factory=list)
    seed_survey: bool = False
    surveyed: list[str] = field(default_factory=list)
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    discovery_labels: dict[str, str] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    # EXPANSION.md §3 — the expand↔consolidate turn dimension.
    task_kind: str = "expand"
    islands: int = 0
    # Connectivity readout (component / orphan / ratified / reopened counts) so the
    # CLI and tests can surface MapHealth without re-deriving it.
    health: dict[str, Any] = field(default_factory=dict)
    connectivity_delta: dict[str, Any] = field(default_factory=dict)
    ratified: list[list[str]] = field(default_factory=list)
    reopened: list[list[str]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# SDK seams — thin programmatic wrappers over the gaia engine                 #
# --------------------------------------------------------------------------- #


def _gaia_dir(pkg: str | Path) -> Path:
    return Path(pkg).resolve() / ".gaia"


def _map_exists(pkg: str | Path) -> bool:
    return (_gaia_dir(pkg) / "exploration" / "map.json").exists()


def _load_beliefs(pkg: str | Path) -> dict[str, float]:
    """Flatten ``.gaia/beliefs.json``'s ``beliefs[]`` to ``dict[qid -> P]``."""
    import json

    p = _gaia_dir(pkg) / "beliefs.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    flat: dict[str, float] = {}
    for entry in raw.get("beliefs", []):
        kid = entry.get("knowledge_id")
        belief = entry.get("belief")
        if isinstance(kid, str) and belief is not None:
            flat[kid] = float(belief)
    return flat


def _load_open_obligations(pkg: str | Path) -> list[Any]:
    """Load the package's OPEN synthetic obligations (build 12, CLIENT.md steer 3).

    Thin alias over the shared SDK seam
    :func:`gaia.lkm_explorer.engine.scorer.load_open_obligations` so the turn loop
    and the standalone ``frontier`` verb load obligations the same way (no
    duplicated state parsing). Missing state ⇒ empty list ⇒ the scorer's
    ``obligation_pressure`` is ``0.0`` everywhere (graceful).
    """
    from gaia.lkm_explorer.engine.scorer import load_open_obligations

    return list(load_open_obligations(pkg))


def _resolve_graph(pkg: str | Path) -> Any | None:
    """Resolve the package IR graph via the inquiry graph loader (SDK)."""
    from gaia.engine.inquiry.review import resolve_graph

    return resolve_graph(str(pkg))


def _project_config(pkg: str | Path) -> dict[str, Any]:
    """Return the package ``[project]`` config for dependency discovery (SDK)."""
    from gaia.engine.packaging import load_gaia_package

    try:
        loaded = load_gaia_package(str(pkg))
    except Exception:
        return {}
    return dict(loaded.project_config)


def _joint_view(pkg: str | Path, graph: Any) -> JointView:
    """Build the joint root+dependency view (SDK; SCHEMA.md §7e)."""
    return build_joint_view(str(pkg), graph, project_config=_project_config(pkg), depth=-1)


def _compute_health(exploration_map: ExplorationMap, view: JointView) -> MapHealth:
    """Compute the joint-graph MapHealth for the map (EXPANSION.md §3.A).

    The surveyed set is ``map.surveyed`` keys; the seeds are the resolved seed
    QIDs; the edges are the joint view's edge set (the same one the scorer
    adjacency spans); the ratified separations are the map's recorded islands.
    Pure (no I/O) — the view was already built by the caller.
    """
    surveyed = list(exploration_map.surveyed.keys())
    seeds = [str(s["qid"]) for s in exploration_map.seeds if s.get("qid")]
    return compute_map_health(
        surveyed,
        seeds,
        view.edges,
        ratified=exploration_map.ratified_as_health_objects(),
    )


def _health_summary(exploration_map: ExplorationMap, health: MapHealth) -> dict[str, Any]:
    """A small JSON-able connectivity readout for the outcome / status."""
    policy = exploration_map.policy
    return {
        "components": health.component_count,
        "orphans": len(health.orphans),
        "unratified_orphans": health.unratified_orphan_count,
        "ratified": health.ratified_count,
        "reopened": len(health.reopened),
        "largest_fraction": round(health.largest_fraction, 4),
        "orphan_fraction": round(health.orphan_node_fraction, 4),
        "unhealthy": health.is_unhealthy(
            min_orphan_components=policy.fragment_min_orphans,
            orphan_fraction=policy.fragment_orphan_fraction,
        ),
    }


def _select_mode(exploration_map: ExplorationMap, health: MapHealth) -> str:
    """Pick expand vs. consolidate for this IDLE turn (EXPANSION.md §3.C / §4).

    ``mode_select`` pins the mode when set to ``expand`` / ``consolidate``; under
    ``auto`` the orchestrator consolidates iff the map is unhealthy past the
    policy's fragmentation threshold (a reopened ratification counts as
    un-ratified, handled inside MapHealth), else expands.
    """
    mode = exploration_map.policy.mode_select
    if mode == MODE_SELECT_EXPAND:
        return MODE_SELECT_EXPAND
    if mode == MODE_SELECT_CONSOLIDATE:
        return MODE_SELECT_CONSOLIDATE
    # auto
    unhealthy = health.is_unhealthy(
        min_orphan_components=exploration_map.policy.fragment_min_orphans,
        orphan_fraction=exploration_map.policy.fragment_orphan_fraction,
    )
    return MODE_SELECT_CONSOLIDATE if unhealthy else MODE_SELECT_EXPAND


def _promote_lkm_from_view(
    exploration_map: ExplorationMap, view: JointView, *, survey_round: int
) -> list[str]:
    """Retire ``lkm_related`` contacts whose paper is now materialized (theme 004).

    A paper pulled via ``gaia pkg add --lkm-paper <id>`` lands as a dependency
    sub-package carrying its authoritative ``paper_id`` (``[tool.gaia.source]``),
    collected into ``view.materialized_paper_ids``; we union it with the
    dist-dir-name heuristic as a defensive backstop. Each matching open ``lkm``
    contact flips to ``surveyed`` (kept, not deleted, so ``reconcile`` won't
    resurrect it). The standalone ``frontier``/``round`` verbs already do this; the
    turn loop's IDLE step did not, so a pulled paper lingered as an open contact —
    this closes that gap so ``turn`` and the ``frontier`` verb agree.
    """
    from gaia.lkm_explorer.engine.observe import (
        materialized_paper_ids_from_roots,
        promote_materialized_lkm_contacts,
    )

    paper_ids = set(view.materialized_paper_ids) | materialized_paper_ids_from_roots(
        view.package_roots
    )
    if not paper_ids:
        return []
    return promote_materialized_lkm_contacts(
        exploration_map,
        materialized_paper_ids=paper_ids,
        survey_round=survey_round,
    )


def _resolve_seeds(exploration_map: ExplorationMap, graph: Any, view: JointView) -> bool:
    """Resolve null-qid seeds against the joint graph (theme 010 / SCHEMA.md §7e #3).

    Mirrors the ``frontier`` verb's resolution so the turn loop and the standalone
    verb agree: a ``::``/exact-id-or-label seed resolves to its materialized QID,
    and a FREE-TEXT cold-start seed resolves by content-token overlap against the
    materialized set once round 0 has materialized something to match — giving the
    scorer's ``closeness_to_seed`` a non-zero signal from round 1 on. Returns
    ``True`` if any seed was newly resolved (caller persists the map).
    """
    from gaia.engine.inquiry.focus import resolve_focus_target
    from gaia.lkm_explorer.engine.frontier import resolve_freetext_seed_qid

    changed = False
    node_texts = view.node_texts()
    for seed in exploration_map.seeds:
        if seed.get("qid"):
            continue
        text = str(seed.get("text", "")).strip()
        if not text:
            continue
        if "::" in text and text in view.materialized:
            seed["qid"] = text
            changed = True
            continue
        binding = resolve_focus_target(text, graph)
        if binding.resolved_id and binding.resolved_id in view.materialized:
            seed["qid"] = binding.resolved_id
            changed = True
            continue
        matched = resolve_freetext_seed_qid(text, view.materialized, node_texts)
        if matched is not None:
            seed["qid"] = matched
            changed = True
    return changed


def _compile_and_infer(pkg: str | Path) -> list[str]:
    """Compile the package then run JOINT BP inference, writing artifacts (SDK).

    Mirrors what ``gaia build compile`` + ``gaia run infer --depth -1`` do, but
    called programmatically through the engine packaging / BP SDK rather than by
    shelling out to the ``gaia`` CLI (CLIENT.md "Resolved: compile/infer via the
    SDK"). Writes ``.gaia/ir.json`` (+ manifests) and ``.gaia/beliefs.json`` — the
    artifacts the subsequent round step diffs.

    **Explorer promotion (this build).** Before inference, every pulled-paper
    ``-gaia`` dependency is recompiled from source with its inert ``depends_on``
    scaffolds promoted to live ``derive`` reasoning (see
    :mod:`gaia.lkm_explorer.engine.promote`), and the promoted dependency factor
    graphs are merged into the root's (``merge_factor_graphs``, exactly like
    ``infer --depth -1``). This is what makes a pulled paper's internal reasoning
    enter BP and move belief on the map — root-only / depth-0 inference would
    leave the paper's factors out of the graph entirely, making promotion a no-op.

    Returns the list of human-readable promotion/joint-view notes (counts of
    promoted derives, skipped factors, and any degraded dependency) for the
    checkpoint to surface.
    """
    import json
    from dataclasses import asdict as _asdict

    from gaia.engine.bp import lower_local_graph, merge_factor_graphs
    from gaia.engine.bp.engine import InferenceEngine
    from gaia.engine.ir import LocalCanonicalGraph
    from gaia.engine.ir.validator import validate_local_graph
    from gaia.engine.packaging import (
        GaiaPackagingError,
        apply_package_priors,
        build_package_manifests,
        compile_loaded_package_artifact,
        ensure_package_env,
        gaia_lang_version,
        load_gaia_package,
        write_compiled_artifacts,
        write_text_atomic,
    )
    from gaia.lkm_explorer.engine.promote import promote_dependency_graphs

    pkg_path = Path(pkg).resolve()
    try:
        ensure_package_env(pkg_path)
        loaded = load_gaia_package(str(pkg))
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        manifests = build_package_manifests(loaded, compiled)
    except GaiaPackagingError as exc:
        raise OrchestratorError(f"compile failed: {exc}") from exc

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    if validation.errors:
        raise OrchestratorError("compile failed: " + "; ".join(validation.errors))

    write_compiled_artifacts(
        loaded.pkg_path,
        ir,
        manifests=manifests,
        formalization_manifest=compiled.formalization_manifest,
    )

    notes: list[str] = []

    # (explorer promotion) Recompile each pulled-paper dependency from source with
    # its `depends_on` scaffolds promoted to live `derive`, so the paper's
    # internal reasoning is in the factor graph. Degrades to warnings; never
    # crashes the checkpoint.
    try:
        promotion = promote_dependency_graphs(pkg_path)
    except Exception as exc:  # promotion must never break a checkpoint
        promotion = None
        notes.append(f"dependency promotion skipped ({type(exc).__name__}: {exc})")
    dep_factor_graphs: list[tuple[str, Any, str]] = []
    if promotion is not None:
        notes.extend(promotion.warnings)
        for dep in promotion.dependencies:
            dep_fg = lower_local_graph(dep.graph)
            dep_prefix = f"{dep.graph.namespace}:{dep.graph.package_name}::"
            dep_factor_graphs.append((dep.import_name, dep_fg, dep_prefix))
        if promotion.dependencies:
            notes.append(
                f"promoted {promotion.total_promoted} pulled-paper depends_on edge(s) "
                f"to live derive across {len(promotion.dependencies)} dependency package(s)"
                + (
                    f" (skipped {promotion.total_skipped} unpromotable factor(s))"
                    if promotion.total_skipped
                    else ""
                )
            )

    # Joint inference: merge the promoted dependency factor graphs into the root's
    # (like `gaia run infer --depth -1`). With no deps this is the root graph alone
    # (flat priors — the round diffs root beliefs).
    local_fg = lower_local_graph(compiled.graph)
    if dep_factor_graphs:
        local_prefix = f"{compiled.graph.namespace}:{compiled.graph.package_name}::"
        factor_graph = merge_factor_graphs(local_fg, dep_factor_graphs, local_prefix=local_prefix)
    else:
        factor_graph = local_fg
    fg_errors = factor_graph.validate()
    if fg_errors:
        raise OrchestratorError("inference failed: " + "; ".join(fg_errors))
    result = InferenceEngine().run(factor_graph).result

    # Beliefs span the JOINT graph: root knowledges + every promoted dependency's
    # knowledges, so a pulled paper's now-live claims surface their belief on the
    # map (not just the root's). Each QID is globally unique (namespace:pkg::label
    # prefixed), so the union is collision-free.
    knowledge_by_id = {k.id: k for k in compiled.graph.knowledges}
    if promotion is not None:
        for dep in promotion.dependencies:
            for k in dep.graph.knowledges:
                knowledge_by_id.setdefault(k.id, k)
    beliefs_payload = {
        "ir_hash": compiled.graph.ir_hash,
        "gaia_lang_version": gaia_lang_version(),
        "beliefs": [
            {
                "knowledge_id": kid,
                "label": knowledge_by_id[kid].label,
                "belief": belief,
            }
            for kid, belief in sorted(result.beliefs.items())
            if kid in knowledge_by_id
        ],
        "diagnostics": _asdict(result.diagnostics),
    }
    gaia_dir = loaded.pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    write_text_atomic(
        gaia_dir / "beliefs.json",
        json.dumps(beliefs_payload, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return notes


def _rank_open_contacts(exploration_map: ExplorationMap) -> list[Contact]:
    """Open contacts sorted by score (desc, ``None`` last) then id."""
    open_contacts = [c for c in exploration_map.frontier if c.status == "open"]
    return sorted(open_contacts, key=lambda c: (c.score is None, -(c.score or 0.0), c.id))


def _refresh_stats(exploration_map: ExplorationMap) -> None:
    """Recompute the cheap denormalized ``map.stats`` counters."""
    open_count = sum(1 for c in exploration_map.frontier if c.status == "open")
    exploration_map.stats = {
        "surveyed_count": len(exploration_map.surveyed),
        "frontier_open": open_count,
        "discoveries": dict(exploration_map.stats.get("discoveries", {})),
    }


def _score_feature_hint(score_features: dict[str, Any]) -> str:
    """Translate a contact's live ``score_features`` into a short NL hint.

    Picks the 1-2 dominant *live, non-belief* signals (CLIENT.md build 8, narrowed
    by build 11 steer 4) and renders them as a natural-language nudge appended to
    the brief; returns ``""`` when no signal is strong enough to be worth citing.
    The belief-derived ``belief_entropy`` ("undecided territory") hint is NOT
    cited — belief stays internal to the engine (Jaynes' robot). ``bridge_potential``
    is now a live slot (EXPANSION.md §3.B) and IS cited when high (a bridging
    contact heals fragmentation). ``tension_potential`` stays a 0.0 deferred slot
    and is never cited (the ``Inquisitor`` doctrine remains inert).
    """

    def _f(key: str) -> float:
        try:
            return float(score_features.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0

    # (score, hint phrase) — order = tie-break priority. No belief_entropy hint:
    # belief is not surfaced to the agent (build 11 steer 4).
    candidates: list[tuple[float, str]] = []
    if (v := _f("closeness_to_seed")) >= 0.6:
        candidates.append((v, "on-topic / close to your seed"))
    if (v := _f("new_territory")) >= 0.6:
        candidates.append((v, "fresh unexplored territory"))
    # bridge_potential is binary (0.0/1.0); when high, surveying/wiring this
    # contact would connect an orphan island to the core (EXPANSION.md §3.B).
    if (v := _f("bridge_potential")) >= 1.0:
        candidates.append((v, "bridges a disconnected island to your core"))

    if not candidates:
        return ""
    # Lead with the strongest signal; cite at most two.
    candidates.sort(key=lambda c: -c[0])
    phrases = [phrase for _, phrase in candidates[:2]]
    return "Signal: " + "; ".join(phrases) + "."


def _obligation_brief_line(contact: Contact, obligations: list[Any]) -> str:
    """Name the open obligation a pressed contact discharges (theme 006, part a).

    Returns ``"discharges open obligation: <content>"`` when the contact's
    ``obligation_pressure`` feature is ``> 0`` (set by the scorer's ref/source OR
    one-hop-adjacency match), naming the obligation(s) it is pressed by so the
    agent sees *why* the contact is steered. Returns ``""`` when the contact is not
    pressed or no obligations are loaded — discoverability surface only; the
    ranking is unaffected.
    """
    try:
        pressure = float(contact.score_features.get("obligation_pressure", 0.0))
    except (TypeError, ValueError):
        pressure = 0.0
    if pressure <= 0.0 or not obligations:
        return ""
    # Name the obligation content(s); cite at most two so the brief stays short.
    contents = [
        str(getattr(o, "content", "")).strip()
        for o in obligations
        if str(getattr(o, "content", "")).strip()
    ]
    if not contents:
        return ""
    return "discharges open obligation: " + "; ".join(contents[:2])


def _contact_survey_brief(contact: Contact, obligations: list[Any] | None = None) -> str:
    """Compose a survey brief for a contact (CLIENT.md task contact, build 8).

    The brief adapts to the contact: it keeps the type/sources/pull-line content,
    anchors the agent's first LKM query on the contact's ref + sources, folds in a
    short ``score_features``-derived hint naming the 1-2 dominant live signals, and
    — when the contact is pressed by an open obligation (theme 006) — names the
    obligation it discharges. May span 2-4 lines.
    """
    srcs = ", ".join(f"{s['qid']}[{s['edge']}]" for s in contact.sources) or "(no sources)"
    ref_value = str(contact.ref.get("value"))
    hint = _score_feature_hint(contact.score_features)
    hint_part = f" {hint}" if hint else ""
    obl = _obligation_brief_line(contact, obligations or [])
    obl_part = f" {obl}." if obl else ""
    if contact.ref.get("kind") == "lkm":
        title = contact.meta.get("title")
        index_id = contact.meta.get("index_id")
        idx = f" --lkm-index {index_id}" if isinstance(index_id, str) else ""
        title_part = f' "{title}"' if isinstance(title, str) and title else ""
        return (
            f"unpulled related paper {ref_value}{title_part}; surfaced via {srcs}. "
            f"Pull it: gaia pkg add{idx} --lkm-paper {ref_value}, then survey its content. "
            f"Anchor your first LKM query on {ref_value}"
            f"{' (' + title + ')' if isinstance(title, str) and title else ''} "
            f"plus the context of its sources ({srcs}).{hint_part}{obl_part}"
        )
    return (
        f"referenced-but-unmaterialized node {ref_value}; reached via {srcs}. "
        f"Survey it: search LKM for evidence, observe related papers, author the node. "
        f"Anchor your first LKM query on {ref_value} plus the context of its "
        f"sources ({srcs}).{hint_part}{obl_part}"
    )


def _island_brief_text(member_qids: list[str], node_texts: dict[str, str]) -> str:
    """A short NL description of an orphan island for the consolidate worklist."""
    parts: list[str] = []
    for qid in member_qids[:6]:
        label = qid.rsplit("::", 1)[1] if "::" in qid else qid
        text = node_texts.get(qid, "").strip()
        # node_texts() yields "label content"; keep it short.
        snippet = text[:120] + ("…" if len(text) > 120 else "") if text else label
        parts.append(f"{label}: {snippet}" if text else label)
    more = f" (+{len(member_qids) - 6} more nodes)" if len(member_qids) > 6 else ""
    return "; ".join(parts) + more


def _island_briefs(
    exploration_map: ExplorationMap, health: MapHealth, view: JointView
) -> list[IslandBrief]:
    """Build the consolidate bridge worklist from the orphan islands (EXPANSION.md §3.D).

    One :class:`IslandBrief` per un-ratified-or-reopened orphan component (a
    still-valid ratified island is NOT re-nagged — EXPANSION.md §3.E). A reopened
    island carries its ``bridge_hint`` (the QID whose new presence may now connect
    it) and the ``reopened`` flag so the brief can say "reconsider".
    """
    node_texts = view.node_texts()
    ratified_members = {
        frozenset(str(q) for q in r.get("member_qids", []))
        for r in exploration_map.ratified_separations
    }
    briefs: list[IslandBrief] = []
    for comp in health.orphans:
        members = list(comp.members)
        is_ratified = frozenset(members) in ratified_members
        # Skip still-valid ratified islands (honored, not re-nagged); a reopened
        # one (ratified but stale premise) DOES return to the worklist.
        if is_ratified and not comp.reopened:
            continue
        briefs.append(
            IslandBrief(
                member_qids=members,
                brief=_island_brief_text(members, node_texts),
                reopened=comp.reopened,
                bridge_hint=comp.bridge_qid,
            )
        )
    return briefs


def _seed_contacts(exploration_map: ExplorationMap) -> list[TaskContact]:
    """Build round-0 seed-survey contact rows from the map's seeds."""
    rows: list[TaskContact] = []
    for i, seed in enumerate(exploration_map.seeds):
        text = str(seed.get("text", "")).strip()
        qid = seed.get("qid")
        has_qid = isinstance(qid, str) and bool(qid)
        ref_value = qid if has_qid else text
        brief = (
            f"SEED ({seed.get('kind', 'question')}): {text!r}. "
            "Survey the seed itself: use the seed text as your initial LKM query, "
            "observe related papers (seeds round 1's frontier), and materialize it."
        )
        rows.append(
            TaskContact(
                id=f"seed_{i}",
                ref={"kind": "qid" if has_qid else "lkm", "value": ref_value},
                sources=[],
                survey_brief=brief,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Phase steps                                                                 #
# --------------------------------------------------------------------------- #


def _emit_survey_task(pkg: str | Path, exploration_map: ExplorationMap) -> TurnOutcome:
    """IDLE → rank the frontier, write a self-contained survey task, exit.

    Round 0 (nothing materialized yet) is the special case: the frontier is
    empty, so the task is a *seed survey* — the agent surveys the seed(s) instead
    of a frontier shortlist (CLIENT.md round-0 special case).
    """
    messages: list[str] = []
    round_index = exploration_map.round
    graph = _resolve_graph(pkg)

    contacts: list[TaskContact] = []
    bridge_worklist: list[IslandBrief] = []
    seed_survey = False
    task_kind = MODE_SELECT_EXPAND
    health_summary: dict[str, Any] = {}

    if graph is None:
        # Round 0 before any compile/materialize: survey the seed(s).
        seed_survey = True
        contacts = _seed_contacts(exploration_map)
        messages.append(
            "no compiled IR yet — emitting a round-0 seed-survey task "
            "(run the survey, then re-invoke `gaia-lkm-explore turn`)."
        )
    else:
        beliefs = _load_beliefs(pkg)
        view = _joint_view(pkg, graph)
        messages.extend(f"warning: {w}" for w in view.warnings)
        # (theme 010) Resolve any null-qid (free-text cold-start) seed against the
        # joint materialized set BEFORE scoring, so closeness_to_seed bites this
        # round — matching the frontier verb.
        _resolve_seeds(exploration_map, graph, view)
        # (theme 004) Retire any lkm_related contact whose paper is now
        # materialized in the joint view (pulled via `pkg add --lkm-paper`) BEFORE
        # ranking, so a pulled paper never resurfaces as an open "unpulled"
        # contact in the shortlist — the frontier verb already does this.
        promoted_papers = _promote_lkm_from_view(exploration_map, view, survey_round=round_index)
        if promoted_papers:
            messages.append(
                f"retired {len(promoted_papers)} lkm_related contact(s) "
                f"(paper(s) now materialized): {', '.join(promoted_papers)}"
            )
        extracted = view.extract(exploration_map)
        reconcile_frontier(exploration_map, extracted, discovered_round=round_index)

        # EXPANSION.md §3.A/§3.C — compute MapHealth and pick the turn mode
        # (auto → consolidate iff unhealthy past the threshold; pinned values
        # override). The doctrine IS the mode; mode_select only decides WHEN.
        health = _compute_health(exploration_map, view)
        health_summary = _health_summary(exploration_map, health)
        mode = _select_mode(exploration_map, health)

        # Build 12 (CLIENT.md steer 3): load the package's open synthetic
        # obligations so this live turn scores obligation_pressure. The MapHealth
        # now also activates bridge_potential + qid new_territory (EXPANSION §3.B).
        obligations = _load_open_obligations(pkg)
        score_frontier(
            exploration_map,
            beliefs=beliefs,
            edges=view.edges,
            obligations=obligations,
            health=health,
            materialized=view.materialized,
        )
        _refresh_stats(exploration_map)

        if mode == MODE_SELECT_CONSOLIDATE:
            bridge_worklist = _island_briefs(exploration_map, health, view)
            if bridge_worklist:
                task_kind = MODE_SELECT_CONSOLIDATE
                n_reopened = sum(1 for b in bridge_worklist if b.reopened)
                messages.append(
                    f"consolidate turn: {len(bridge_worklist)} island(s) to bridge or "
                    f"ratify (over already-surveyed nodes; no new pulls)"
                    + (f", {n_reopened} reopened by new evidence" if n_reopened else "")
                    + "."
                )
            else:
                # Pinned/auto consolidate but nothing left to bridge (all islands
                # are validly ratified, or the map is connected) — fall back to an
                # expand turn so the loop still makes progress.
                messages.append(
                    "consolidate requested but no un-ratified islands remain — "
                    "running an expand turn instead."
                )

        if task_kind == MODE_SELECT_EXPAND:
            ranked = _rank_open_contacts(exploration_map)
            top_k = ranked[: exploration_map.policy.budget_k]
            if not top_k:
                # No frontier yet (round 0, or a survey that grew nothing): fall
                # back to a seed survey so the loop can still make progress.
                seed_survey = True
                contacts = _seed_contacts(exploration_map)
                messages.append(
                    "frontier empty — emitting a seed-survey task; observe related "
                    "papers during the survey to grow the frontier for next round."
                )
            else:
                # Build 11 steer 4: rank on the FULL features (done above by
                # score_frontier + _rank_open_contacts), then sanitize for the
                # agent-facing envelope — drop belief_entropy and the raw
                # belief-weighted score so the agent never sees the belief math
                # (Jaynes' robot). Ordering is already fixed by top_k.
                contacts = [
                    TaskContact(
                        id=c.id,
                        ref=c.ref,
                        score=None,
                        score_features=sanitize_score_features(c.score_features),
                        sources=c.sources,
                        survey_brief=_contact_survey_brief(c, obligations),
                    )
                    for c in top_k
                ]

    edir = exploration_dir(pkg)
    res_path = result_path(edir, round_index)
    if task_kind == MODE_SELECT_CONSOLIDATE:
        instructions = build_consolidate_instructions()
    else:
        instructions = build_survey_instructions(seed_survey=seed_survey)
    task = SurveyTask(
        pkg=str(pkg),
        round=round_index,
        doctrine=exploration_map.policy.doctrine,
        budget_k=exploration_map.policy.budget_k,
        kind=task_kind,
        contacts=contacts,
        bridge_worklist=bridge_worklist,
        seed_survey=seed_survey,
        instructions=instructions,
        result_path=str(res_path),
    )
    written = task.write(task_path(edir, round_index))

    exploration_map.turn_phase = TURN_PHASE_AWAITING_SURVEY
    save_map(pkg, exploration_map)

    return TurnOutcome(
        phase_before=TURN_PHASE_IDLE,
        phase_after=TURN_PHASE_AWAITING_SURVEY,
        action="emitted_task",
        round=round_index,
        task_path=str(written),
        result_path=str(res_path),
        contacts=[c.id for c in contacts],
        seed_survey=seed_survey,
        task_kind=task_kind,
        islands=len(bridge_worklist),
        health=health_summary,
        messages=messages,
    )


def _prior_round_health(pkg: str | Path, current_round: int) -> dict[str, Any]:
    """The health summary recorded by the most recent prior round, or ``{}``.

    Reads ``rounds.jsonl`` and returns the latest record's
    ``frontier_summary.health`` (written by a previous checkpoint), so the
    connectivity delta is measured against the last completed round.
    """
    from gaia.lkm_explorer.engine.state import read_rounds

    rounds = [r for r in read_rounds(pkg) if int(r.get("round", -1)) < current_round]
    if not rounds:
        return {}
    last = rounds[-1]
    health = last.get("frontier_summary", {}).get("health", {})
    return dict(health) if isinstance(health, dict) else {}


def _prior_round_components(pkg: str | Path, current_round: int) -> list[frozenset[str]]:
    """The component partition the most recent prior round recorded (or ``[]``).

    Reads ``rounds.jsonl``'s latest ``frontier_summary.component_members`` (a list
    of member lists, written by a previous checkpoint) so ``bridge`` detection can
    diff this round's partition against the prior one.
    """
    from gaia.lkm_explorer.engine.state import read_rounds

    rounds = [r for r in read_rounds(pkg) if int(r.get("round", -1)) < current_round]
    if not rounds:
        return []
    members = rounds[-1].get("frontier_summary", {}).get("component_members", [])
    if not isinstance(members, list):
        return []
    return [frozenset(str(q) for q in comp) for comp in members if isinstance(comp, list)]


def _record_surveyed(
    exploration_map: ExplorationMap, surveyed_qids: list[str], *, survey_round: int
) -> None:
    """Record surveyed QIDs into ``map.surveyed`` (promote matching contacts)."""
    open_by_qid: dict[str, Contact] = {
        str(c.ref["value"]): c
        for c in exploration_map.frontier
        if c.status == "open" and c.ref.get("kind") == "qid"
    }
    for qid in surveyed_qids:
        if qid in exploration_map.surveyed:
            continue
        contact = open_by_qid.get(qid)
        if contact is not None:
            exploration_map.promote_contact(contact.id, survey_round=survey_round)
        else:
            exploration_map.surveyed[qid] = SurveyRecord(qid=qid, survey_round=survey_round)


def _checkpoint(
    pkg: str | Path, exploration_map: ExplorationMap, survey_result: SurveyResult
) -> TurnOutcome:
    """AWAITING_CHECKPOINT → compile + infer (SDK) + explore round, set IDLE.

    The heavy state already landed in the package + save-game via the agent's
    survey; here the orchestrator recomputes belief (compile + infer via the SDK)
    and runs the deterministic round: compute discoveries vs. the previous round's
    beliefs, record what was surveyed, append the round record, snapshot beliefs,
    and advance the round.
    """
    import json

    from gaia.lkm_explorer.engine.discoveries import compute_discoveries

    messages: list[str] = []
    current_round = exploration_map.round

    # Recompute belief through the SDK (never shelling out to gaia). This also
    # promotes each pulled-paper dependency's depends_on scaffolds to live derive
    # and infers over the joint graph, so the paper's reasoning enters BP.
    messages.extend(_compile_and_infer(pkg) or [])

    graph = _resolve_graph(pkg)
    if graph is None:
        raise OrchestratorError("checkpoint failed: package did not compile to an IR graph.")
    beliefs = _load_beliefs(pkg)
    prev_beliefs = load_round_beliefs(pkg, current_round - 1) if current_round > 0 else {}

    ir_path = _gaia_dir(pkg) / "ir.json"
    ir_dict: dict[str, Any] | None = None
    if ir_path.exists():
        try:
            ir_dict = dict(json.loads(ir_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            ir_dict = None

    surveyed_qids = list(survey_result.surveyed_qids)
    _record_surveyed(exploration_map, surveyed_qids, survey_round=current_round)

    # EXPANSION.md §3.E — record any islands the agent ratified-as-separate this
    # turn (the one consolidate signal that has no graph footprint). Stamp the
    # round + a cheap evidence fingerprint (the ratifying round) so the
    # provisional-reopen test can tell whether later evidence has changed the
    # premise. Recorded per component; a re-ratification replaces the prior row.
    ratified_now: list[list[str]] = []
    for r in survey_result.ratified:
        members = [str(q) for q in r.member_qids if q]
        if not members:
            continue
        exploration_map.add_ratified_separation(
            members,
            rationale=r.rationale,
            round_index=current_round,
            evidence_fingerprint={"ratified_round": current_round},
        )
        ratified_now.append(sorted(members))
    if ratified_now:
        messages.append(f"recorded {len(ratified_now)} ratified separation(s) this turn.")

    # Credit the round with the papers materialized during this turn's
    # survey (pulled via `pkg add --lkm-paper`, outside the round step) so the
    # durable record no longer shows `lkm_pulls: 0`. The same joint view also
    # drives the post-checkpoint MapHealth (computed BEFORE discoveries so the
    # connectivity discovery kinds can use its component partition).
    from gaia.lkm_explorer.engine.observe import materialized_paper_ids_from_roots
    from gaia.lkm_explorer.engine.state import lkm_pulls_this_round

    lkm_pulls = 0
    health_summary: dict[str, Any] = {}
    connectivity_delta: dict[str, Any] = {}
    reopened_now: list[list[str]] = []
    curr_components: list[frozenset[str]] | None = None
    orphan_components: list[frozenset[str]] | None = None
    try:
        view = _joint_view(pkg, graph)
        materialized_papers = set(view.materialized_paper_ids) | materialized_paper_ids_from_roots(
            view.package_roots
        )
        lkm_pulls = lkm_pulls_this_round(pkg, len(materialized_papers))

        # EXPANSION.md §3.D/§3.E — recompute MapHealth on the post-checkpoint
        # joint graph. The reopen test (a ratified island whose premise is now
        # stale because new bridging evidence exists) falls straight out of it.
        health = _compute_health(exploration_map, view)
        health_summary = _health_summary(exploration_map, health)
        curr_components = [frozenset(c.members) for c in health.components]
        orphan_components = [frozenset(c.members) for c in health.orphans]
        reopened_now = [list(c.members) for c in health.reopened]
        if reopened_now:
            messages.append(
                f"REOPENED {len(reopened_now)} ratified separation(s): new evidence "
                "may now connect a previously-ratified island — reconsider next "
                "consolidate turn."
            )
        prior_health = _prior_round_health(pkg, current_round)
        if prior_health:
            connectivity_delta = {
                "components": health_summary.get("components", 0)
                - prior_health.get("components", 0),
                "unratified_orphans": health_summary.get("unratified_orphans", 0)
                - prior_health.get("unratified_orphans", 0),
                "ratified": health_summary.get("ratified", 0) - prior_health.get("ratified", 0),
            }
    except Exception:
        # A degraded joint view (e.g. uncompiled deps) must not break the
        # checkpoint; default to no credit / no health rather than crashing.
        lkm_pulls = 0

    # EXPANSION.md §3 / Phase 3 — bridge/fault_line discoveries use the current vs.
    # prior MapHealth component partition (the prior round stored its members).
    prev_components = _prior_round_components(pkg, current_round)
    discoveries = compute_discoveries(
        graph,
        beliefs,
        prev_beliefs,
        ir_dict=ir_dict,
        prev_components=prev_components if curr_components is not None else None,
        curr_components=curr_components,
        orphan_components=orphan_components,
    )

    # Author labels for the discovered nodes, so the report names a labeled node
    # (e.g. a `contradict` the user named `spinfluc_vs_phonon`) by its label rather
    # than its `_anon`-bearing QID. The QID stays the durable `ids` key.
    label_by_qid = {
        k.id: str(k.label)
        for k in getattr(graph, "knowledges", [])
        if k.id is not None and getattr(k, "label", None)
    }
    discovered_ids = {qid for disc in discoveries for qid in disc.get("ids", [])}
    discovery_labels = {qid: label_by_qid[qid] for qid in discovered_ids if qid in label_by_qid}

    open_after = sum(1 for c in exploration_map.frontier if c.status == "open")
    scored = [
        c.score for c in exploration_map.frontier if c.status == "open" and c.score is not None
    ]
    frontier_summary: dict[str, Any] = {
        "open_after": open_after,
        "top_score": max(scored) if scored else None,
    }
    if health_summary:
        frontier_summary["health"] = health_summary
    if curr_components is not None:
        # Persist the component partition so the NEXT round's bridge detection has
        # a prior partition to diff against (sorted member lists, JSON-able).
        frontier_summary["component_members"] = [sorted(c) for c in curr_components]

    append_round(
        pkg,
        round_index=current_round,
        policy=exploration_map.policy,
        surveyed=surveyed_qids,
        discoveries=discoveries,
        frontier_summary=frontier_summary,
        lkm_pulls=lkm_pulls,
    )
    save_round_beliefs(pkg, current_round, beliefs)

    exploration_map.round = current_round + 1
    exploration_map.turn_phase = TURN_PHASE_IDLE
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    return TurnOutcome(
        phase_before=TURN_PHASE_AWAITING_CHECKPOINT,
        phase_after=TURN_PHASE_IDLE,
        action="checkpointed",
        round=current_round,
        surveyed=surveyed_qids,
        discoveries=discoveries,
        discovery_labels=discovery_labels,
        health=health_summary,
        connectivity_delta=connectivity_delta,
        ratified=ratified_now,
        reopened=reopened_now,
        messages=messages,
    )


# --------------------------------------------------------------------------- #
# The single phase-aware step                                                 #
# --------------------------------------------------------------------------- #


def run_turn(pkg: str | Path) -> TurnOutcome:
    """Run one phase-aware exploration turn (CLIENT.md "Turn state machine").

    Reads the save-game's ``turn_phase``, *infers* ``AWAITING_CHECKPOINT`` from
    the presence of a result manifest (the agent never sets the phase by hand),
    runs the deterministic engine step for that phase via the SDK, advances the
    phase, and returns the outcome.

    Args:
        pkg: the knowledge-package directory holding ``.gaia/exploration/map.json``.

    Returns:
        A :class:`TurnOutcome` describing what happened.

    Raises:
        OrchestratorError: if there is no exploration map, or a checkpoint cannot
            compile / infer the package.
    """
    if not _map_exists(pkg):
        raise OrchestratorError(f"no exploration map at {pkg}; run `gaia-lkm-explore init` first.")

    exploration_map = load_map(pkg)
    edir = exploration_dir(pkg)
    res_path = result_path(edir, exploration_map.round)

    # Infer the checkpoint phase from the result manifest's presence (CLIENT.md
    # "Resolved"): if a survey result has landed for this round, we are AWAITING
    # the checkpoint regardless of the persisted phase.
    if res_path.exists():
        survey_result = SurveyResult.read(res_path)
        return _checkpoint(pkg, exploration_map, survey_result)

    if exploration_map.turn_phase == TURN_PHASE_AWAITING_SURVEY:
        # A task is out and no result manifest yet — the agent is still surveying.
        return TurnOutcome(
            phase_before=TURN_PHASE_AWAITING_SURVEY,
            phase_after=TURN_PHASE_AWAITING_SURVEY,
            action="awaiting_survey",
            round=exploration_map.round,
            task_path=str(task_path(edir, exploration_map.round)),
            result_path=str(res_path),
            messages=[
                "a survey task is outstanding; survey it and write the result "
                "manifest, then re-invoke `gaia-lkm-explore turn`."
            ],
        )

    # IDLE (or AWAITING_CHECKPOINT with the manifest gone — degrade to re-emit).
    return _emit_survey_task(pkg, exploration_map)


def outcome_as_dict(outcome: TurnOutcome) -> dict[str, Any]:
    """Return the JSON-compatible payload for a turn outcome (CLI ``--json``)."""
    return asdict(outcome)


__all__ = ["OrchestratorError", "TurnOutcome", "outcome_as_dict", "run_turn"]
