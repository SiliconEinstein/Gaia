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

from gaia.engine.exploration.frontier import (
    JointView,
    build_joint_view,
    reconcile_frontier,
)
from gaia.engine.exploration.handoff import (
    SurveyResult,
    SurveyTask,
    TaskContact,
    result_path,
    task_path,
)
from gaia.engine.exploration.scorer import sanitize_score_features, score_frontier
from gaia.engine.exploration.state import (
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
from gaia.explore_client.instructions import build_survey_instructions


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
    messages: list[str] = field(default_factory=list)


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
    :func:`gaia.engine.exploration.scorer.load_open_obligations` so the turn loop
    and the standalone ``frontier`` verb load obligations the same way (no
    duplicated state parsing). Missing state ⇒ empty list ⇒ the scorer's
    ``obligation_pressure`` is ``0.0`` everywhere (graceful).
    """
    from gaia.engine.exploration.scorer import load_open_obligations

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
    from gaia.engine.exploration.observe import (
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
    from gaia.engine.exploration.frontier import resolve_freetext_seed_qid
    from gaia.engine.inquiry.focus import resolve_focus_target

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


def _compile_and_infer(pkg: str | Path) -> None:
    """Compile the package then run BP inference, writing artifacts (SDK).

    Mirrors what ``gaia build compile`` + ``gaia run infer`` do, but called
    programmatically through the engine packaging / BP SDK rather than by
    shelling out to the ``gaia`` CLI (CLIENT.md "Resolved: compile/infer via the
    SDK"). Writes ``.gaia/ir.json`` (+ manifests) and ``.gaia/beliefs.json`` — the
    artifacts the subsequent round step diffs.
    """
    import json
    from dataclasses import asdict as _asdict

    from gaia.engine.bp import lower_local_graph
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
    )

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

    # Inference (flat priors — depth 0; the round diffs root beliefs).
    factor_graph = lower_local_graph(compiled.graph)
    fg_errors = factor_graph.validate()
    if fg_errors:
        raise OrchestratorError("inference failed: " + "; ".join(fg_errors))
    result = InferenceEngine().run(factor_graph).result

    knowledge_by_id = {k.id: k for k in compiled.graph.knowledges}
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
    (gaia_dir / "beliefs.json").write_text(
        json.dumps(beliefs_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


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
    cited — belief stays internal to the engine (Jaynes' robot). ``tension_potential``
    / ``bridge_potential`` are 0.0 v1 slots and are never cited (the ``Inquisitor``
    doctrine is inert).
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
    seed_survey = False

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
        # Build 12 (CLIENT.md steer 3): load the package's open synthetic
        # obligations so this live turn scores obligation_pressure — contacts
        # discharging an open obligation get boosted in the ranking below.
        obligations = _load_open_obligations(pkg)
        score_frontier(exploration_map, beliefs=beliefs, edges=view.edges, obligations=obligations)
        _refresh_stats(exploration_map)

        ranked = _rank_open_contacts(exploration_map)
        top_k = ranked[: exploration_map.policy.budget_k]
        if not top_k:
            # No frontier yet (round 0, or a survey that grew nothing): fall back
            # to a seed survey so the loop can still make progress.
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
    task = SurveyTask(
        pkg=str(pkg),
        round=round_index,
        doctrine=exploration_map.policy.doctrine,
        budget_k=exploration_map.policy.budget_k,
        contacts=contacts,
        seed_survey=seed_survey,
        instructions=build_survey_instructions(seed_survey=seed_survey),
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
        messages=messages,
    )


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

    from gaia.engine.exploration.discoveries import compute_discoveries

    messages: list[str] = []
    current_round = exploration_map.round

    # Recompute belief through the SDK (never shelling out to gaia).
    _compile_and_infer(pkg)

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

    discoveries = compute_discoveries(graph, beliefs, prev_beliefs, ir_dict=ir_dict)

    open_after = sum(1 for c in exploration_map.frontier if c.status == "open")
    scored = [
        c.score for c in exploration_map.frontier if c.status == "open" and c.score is not None
    ]
    frontier_summary = {"open_after": open_after, "top_score": max(scored) if scored else None}

    # Credit the round with the papers materialized during this turn's
    # survey (pulled via `pkg add --lkm-paper`, outside the round step) so the
    # durable record no longer shows `lkm_pulls: 0`. Count the joint view's
    # materialized paper QIDs and credit the net-new ones since the prior round.
    from gaia.engine.exploration.observe import materialized_paper_ids_from_roots
    from gaia.engine.exploration.state import lkm_pulls_this_round

    try:
        view = _joint_view(pkg, graph)
        materialized_papers = set(view.materialized_paper_ids) | materialized_paper_ids_from_roots(
            view.package_roots
        )
        lkm_pulls = lkm_pulls_this_round(pkg, len(materialized_papers))
    except Exception:
        # A degraded joint view (e.g. uncompiled deps) must not break the
        # checkpoint; default to no credit rather than crashing the round.
        lkm_pulls = 0

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
