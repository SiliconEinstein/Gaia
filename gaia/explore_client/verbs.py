"""The deterministic exploration-engine verbs (SCHEMA.md §7c).

These are the engine half of the exploration turn loop's "LLM proposes / engine
adjudicates" split (DESIGN §2): thin Typer commands over
:mod:`gaia.engine.exploration`. As of build 7 (CLIENT.md "Unified surface") they
live under the **``gaia-lkm-explore``** client (``gaia.explore_client``) — the
single user-facing exploration surface — alongside the orchestrator's ``turn``
verb, rather than as a ``gaia explore`` sub-app on the gaia CLI. They are pure
and deterministic — **no LKM call, no ``gaia author`` orchestration** live here;
those are the agent's survey step.

Commands (SCHEMA.md §7c / §7f):

* ``init <pkg> --seed … [--doctrine …]`` — create
  ``.gaia/exploration/map.json`` with seeds + a policy from the named doctrine.
* ``observe <pkg> --source <qid> [--search-json <file>] [--query …]`` —
  read ``gaia search lkm`` JSON (file/stdin) and record each unpulled related
  paper as an ``lkm_related`` paper-contact (SCHEMA.md §7f — the primary frontier
  source). This is the step the agent calls after each LKM survey.
* ``frontier <pkg>`` — load map + IR + manifest + beliefs, build the joint view,
  promote any now-materialized ``lkm`` contacts, run ``extract_frontier`` →
  ``reconcile_frontier`` → ``score_frontier``, save, and print the ranked top-k
  open contacts (qid + ``lkm_related``) to survey.
* ``round <pkg> [--surveyed …]`` — compute discoveries vs. the previous round's
  beliefs, append a round record, bump ``map.round``, refresh ``stats``.
* ``status <pkg>`` — a human-readable map summary.
* ``render <pkg> [--out …]`` — render the map to a self-contained static HTML.

Mirrors ``gaia inquiry`` (``commands/inquiry.py`` → ``engine/inquiry/``): the
same ``typer.echo`` envelope style, ``typer.Exit`` error handling, and the IR
graph loader reused from ``inquiry/review.resolve_graph`` (so we never hand-roll
``ir.json`` parsing). When required artifacts are missing, commands fail
gracefully with an actionable message.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from gaia.engine.exploration.discoveries import compute_discoveries
from gaia.engine.exploration.frontier import (
    JointView,
    build_joint_view,
    reconcile_frontier,
    resolve_freetext_seed_qid,
)
from gaia.engine.exploration.observe import (
    materialized_paper_ids_from_roots,
    observe_lkm_results,
    promote_materialized_lkm_contacts,
)
from gaia.engine.exploration.render import render_map_html
from gaia.engine.exploration.scorer import (
    load_open_obligations,
    sanitize_score_features,
    score_frontier,
)
from gaia.engine.exploration.state import (
    DOCTRINE_PRESETS,
    Contact,
    ExplorationMap,
    SurveyRecord,
    append_round,
    doctrine_policy,
    load_map,
    load_round_beliefs,
    read_rounds,
    save_map,
    save_round_beliefs,
)
from gaia.engine.inquiry.focus import resolve_focus_target
from gaia.engine.inquiry.review import resolve_graph

# Module-level option singletons — Typer needs ``typer.Option`` objects as the
# parameter defaults, but ruff B008 forbids the call literally in the signature,
# so we bind them here once (the ``B008`` "read from a module-level singleton"
# escape hatch).
_PKG_ARG = typer.Argument(..., help="Package path.")
_SEED_OPT = typer.Option(..., "--seed", help="Seed claim text or QID (repeatable).")
_DOCTRINE_OPT = typer.Option(
    "Cartographer",
    "--doctrine",
    help=f"Named doctrine preset: {sorted(DOCTRINE_PRESETS)}.",
)
_BUDGET_K_OPT = typer.Option(5, "--budget-k", help="Top-k contacts to survey per round.")
_FRONTIER_JSON_OPT = typer.Option(False, "--json", help="Emit the ranked contacts as JSON.")
_SURVEYED_OPT = typer.Option(
    None,
    "--surveyed",
    help="QID promoted/surveyed this round (repeatable).",
)
_SEARCH_JSON_OPT = typer.Option(
    None,
    "--search-json",
    help="Path to a `gaia search lkm` result JSON file (omit to read from stdin).",
)
_OBSERVE_SOURCE_OPT = typer.Option(
    None,
    "--source",
    help="The surveyed node QID whose LKM survey surfaced these results.",
)
_OBSERVE_QUERY_OPT = typer.Option(
    None,
    "--query",
    help="The LKM query text that surfaced these results (stored on contact meta).",
)
_RENDER_OUT_OPT = typer.Option(
    None,
    "--out",
    help="Output HTML path (default <pkg>/.gaia/exploration/map.html).",
)


# --------------------------------------------------------------------------- #
# shared helpers                                                              #
# --------------------------------------------------------------------------- #


def _gaia_dir(pkg: str) -> Path:
    return Path(pkg).resolve() / ".gaia"


def _load_beliefs(pkg: str) -> dict[str, float]:
    """Flatten ``.gaia/beliefs.json``'s ``beliefs[]`` to ``dict[qid -> P(x=1)]``.

    Returns ``{}`` when no beliefs artifact exists yet (callers decide whether
    that is fatal). Raises ``typer.Exit`` only on a corrupt file.
    """
    p = _gaia_dir(pkg) / "beliefs.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: {p} is not valid JSON: {exc}", err=True)
        raise typer.Exit(1) from exc
    flat: dict[str, float] = {}
    for entry in raw.get("beliefs", []):
        kid = entry.get("knowledge_id")
        belief = entry.get("belief")
        if isinstance(kid, str) and belief is not None:
            flat[kid] = float(belief)
    return flat


def _load_ir_dict(pkg: str) -> dict[str, Any] | None:
    """Load ``.gaia/ir.json`` as a dict (drives the prior-dissent detector)."""
    p = _gaia_dir(pkg) / "ir.json"
    if not p.exists():
        return None
    try:
        return dict(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return None


def _require_graph(pkg: str) -> Any:
    """Resolve the package IR graph or fail with a build-first message."""
    graph = resolve_graph(pkg)
    if graph is None:
        typer.echo(
            f"Error: could not compile the IR for {pkg!r}; run `gaia build compile` first.",
            err=True,
        )
        raise typer.Exit(1)
    return graph


def _project_config(pkg: str) -> dict[str, Any]:
    """Return the package's ``[project]`` pyproject section for dep discovery.

    Reuses ``load_gaia_package`` (the same loader ``resolve_graph`` runs) so the
    editable ``-gaia`` dependency source roots are on ``sys.path`` before
    :func:`build_joint_view` calls ``load_dependency_compiled_graphs``. Returns an
    empty config (→ root-only joint view) if the package can't be loaded.
    """
    from gaia.engine.packaging import load_gaia_package

    try:
        loaded = load_gaia_package(pkg)
    except Exception:  # any load failure degrades to root-only
        return {}
    return dict(loaded.project_config)


def _require_joint_view(pkg: str, graph: Any) -> JointView:
    """Build the joint root+dependency view, surfacing any skip warnings.

    Spans the root graph + transitive ``-gaia`` deps (SCHEMA.md §7e). A dep that
    isn't compiled yet is skipped with a warning printed to stderr rather than
    crashing; with no deps this degrades to the root-only view.
    """
    view = build_joint_view(pkg, graph, project_config=_project_config(pkg), depth=-1)
    for warning in view.warnings:
        typer.echo(f"Warning: {warning}", err=True)
    return view


def _promote_lkm_from_view(
    exploration_map: ExplorationMap,
    view: JointView,
    *,
    survey_round: int,
) -> list[str]:
    """Promote ``lkm`` contacts whose paper is now materialized in the joint view.

    A paper pulled via ``gaia pkg add --lkm-paper <id>`` lands as a dependency
    sub-package carrying its authoritative ``paper_id`` in its
    ``[tool.gaia.source]`` table (theme 004); the joint view collects those into
    ``view.materialized_paper_ids``. We union that ground-truth set with the
    dist-dir-name heuristic (a defensive backstop for any dep whose manifest could
    not be read) so a pulled paper's ``lkm_related`` contact is reliably retired.
    Each matching open ``lkm`` contact flips to ``surveyed`` with a SurveyRecord.
    """
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


def _refresh_stats(exploration_map: ExplorationMap) -> None:
    """Recompute the cheap denormalized ``map.stats`` counters (SCHEMA.md §2).

    Preserves any per-kind ``discoveries`` tally already present (written by
    :func:`_apply_discovery_tally` from ``rounds.jsonl``); ``init`` / ``frontier``
    carry an empty tally until the first round lands.
    """
    open_count = sum(1 for c in exploration_map.frontier if c.status == "open")
    exploration_map.stats = {
        "surveyed_count": len(exploration_map.surveyed),
        "frontier_open": open_count,
        "discoveries": dict(exploration_map.stats.get("discoveries", {})),
    }


def _discovery_tally(pkg: str) -> dict[str, int]:
    """Tally discovery kinds across every round in ``rounds.jsonl``."""
    tally: dict[str, int] = {}
    for rec in read_rounds(pkg):
        for disc in rec.get("discoveries", []):
            kind = disc.get("kind")
            if isinstance(kind, str):
                tally[kind] = tally.get(kind, 0) + 1
    return tally


def _resolve_seeds(exploration_map: ExplorationMap, graph: Any, view: JointView) -> bool:
    """Resolve null-qid seeds against the joint graph and persist (SCHEMA.md §7e #3).

    For every seed with ``qid is None``, attempts to resolve its ``text`` to a QID
    so the scorer's ``closeness_to_seed`` can use it. Resolution order:

    1. text already a QID materialized somewhere in the joint set → accept it;
    2. otherwise resolve text (id or label) against the root ``graph`` via
       ``inquiry/focus.resolve_focus_target`` (exact id/label hit);
    3. (theme 010) otherwise, for a FREE-TEXT seed, match the seed text against the
       materialized nodes' label+content by token overlap and accept the best
       materialized QID — so a cold-start question seed resolves once round 0 has
       materialized something to match, and ``closeness_to_seed`` bites from then
       on. Resolution is persisted to the map by the caller.

    Returns ``True`` if any seed was newly resolved (so the caller can persist).
    """
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
        # (theme 010) Free-text seed: resolve by content-token overlap against the
        # materialized set (post round-0 materialization gives something to match).
        matched = resolve_freetext_seed_qid(text, view.materialized, node_texts)
        if matched is not None:
            seed["qid"] = matched
            changed = True
    return changed


def _ranked_open_contacts(exploration_map: ExplorationMap) -> list[Contact]:
    """Open contacts sorted by score (desc, ``None`` last) then id."""
    open_contacts = [c for c in exploration_map.frontier if c.status == "open"]
    return sorted(
        open_contacts,
        key=lambda c: (c.score is None, -(c.score or 0.0), c.id),
    )


def _obligation_contents(obligations: list[Any]) -> list[str]:
    """The non-empty ``content`` strings of the open obligations (theme 006)."""
    return [
        str(getattr(o, "content", "")).strip()
        for o in obligations
        if str(getattr(o, "content", "")).strip()
    ]


def _is_obligation_pressed(contact: Contact) -> bool:
    """True iff the scorer set this contact's ``obligation_pressure`` > 0 (theme 006)."""
    try:
        return float(contact.score_features.get("obligation_pressure", 0.0)) > 0.0
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# init                                                                        #
# --------------------------------------------------------------------------- #


def init_command(
    pkg: str = _PKG_ARG,
    seed: list[str] = _SEED_OPT,
    doctrine: str = _DOCTRINE_OPT,
    budget_k: int = _BUDGET_K_OPT,
) -> None:
    r"""Create the exploration map (``.gaia/exploration/map.json``).

    ``<pkg>`` must be an EXISTING Gaia package; scaffold one first with
    ``gaia pkg scaffold --target <pkg> --name <name>-gaia`` if you have none.

    Seeds are the inquiry origins. A seed that looks like a QID (contains
    ``::``) is recorded resolved (``kind="claim"``, ``qid`` set) so the scorer's
    ``closeness_to_seed`` can use it immediately; a free-text seed is recorded as
    a ``question`` with ``qid: null`` until the agent materializes it.

    Example:

    .. code-block:: bash

        gaia pkg scaffold --target ./pkg --name galileo-gaia    # first-timer: make the package
        gaia-lkm-explore init ./pkg --seed "Why do bodies fall?" --doctrine Surveyor
        gaia-lkm-explore init ./pkg --seed github:pkg::aristotle_model --seed other::q
    """
    if doctrine not in DOCTRINE_PRESETS:
        typer.echo(
            f"Error: unknown doctrine {doctrine!r}; allowed: {sorted(DOCTRINE_PRESETS)}",
            err=True,
        )
        raise typer.Exit(2)

    seeds: list[dict[str, Any]] = []
    for raw in seed:
        text = raw.strip()
        if "::" in text:
            seeds.append({"kind": "claim", "text": text, "qid": text})
        else:
            seeds.append({"kind": "question", "text": text, "qid": None})

    policy = doctrine_policy(doctrine, budget_k=budget_k)
    exploration_map = ExplorationMap(seeds=seeds, policy=policy)
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    resolved = sum(1 for s in seeds if s["qid"])
    typer.echo(
        f"Initialised exploration map for {pkg} "
        f"({len(seeds)} seed(s), {resolved} resolved; doctrine {doctrine}, budget_k={budget_k})."
    )
    typer.echo(f"Output: {_gaia_dir(pkg) / 'exploration' / 'map.json'}")


# --------------------------------------------------------------------------- #
# observe                                                                     #
# --------------------------------------------------------------------------- #


def observe_command(
    pkg: str = _PKG_ARG,
    search_json: str | None = _SEARCH_JSON_OPT,
    source: str | None = _OBSERVE_SOURCE_OPT,
    query: str | None = _OBSERVE_QUERY_OPT,
) -> None:
    r"""Record unpulled related papers from an LKM search as frontier contacts.

    Reads ``gaia search lkm`` result JSON (from ``--search-json <file>`` or, if
    omitted, stdin) and, for every result whose **paper** is not materialized in
    the joint view, adds or merges an ``lkm_related`` paper-contact (SCHEMA.md
    §7f — the primary frontier source). De-dup is by ``paper_id`` (a paper
    surfaced several times is one contact; sources + LKM node ids union, the max
    rank wins). A result whose ``gaia.qid`` is already set (materialized in the
    IR) is skipped. ``--source`` is the surveyed node whose survey prompted the
    search and becomes the contact's ``lkm_related`` source.

    Example:

    .. code-block:: bash

        gaia search lkm knowledge "free fall" --limit 5 > leads.json
        gaia-lkm-explore observe ./pkg --source example:pkg::seed --search-json leads.json
        gaia search lkm knowledge "drag" | gaia-lkm-explore observe ./pkg --source example:pkg::seed
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia-lkm-explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    # Read the LKM search JSON from the file or stdin.
    if search_json is not None:
        path = Path(search_json)
        if not path.exists():
            typer.echo(f"Error: --search-json file not found: {search_json}", err=True)
            raise typer.Exit(1)
        raw_text = path.read_text(encoding="utf-8")
    else:
        raw_text = typer.get_text_stream("stdin").read()
    if not raw_text.strip():
        typer.echo("Error: no LKM search JSON provided (empty file/stdin).", err=True)
        raise typer.Exit(1)
    try:
        search_results = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: LKM search input is not valid JSON: {exc}", err=True)
        raise typer.Exit(1) from exc
    if not isinstance(search_results, dict):
        typer.echo("Error: LKM search JSON must be an object with a `results` array.", err=True)
        raise typer.Exit(1)

    exploration_map = load_map(pkg)

    # Build the joint materialized set so an already-pulled paper's nodes are not
    # re-added as fresh contacts (best-effort: degrade to root-only if uncompiled).
    materialized: set[str] = set()
    materialized_papers: set[str] = set()
    graph = resolve_graph(pkg)
    if graph is not None:
        view = _require_joint_view(pkg, graph)
        materialized = set(view.materialized)
        materialized_papers = set(view.materialized_paper_ids) | materialized_paper_ids_from_roots(
            view.package_roots
        )
    else:
        typer.echo(
            "(no compiled IR yet — observing against an empty materialized set; "
            "run `gaia build compile` for paper-already-pulled de-dup)",
            err=True,
        )

    result = observe_lkm_results(
        exploration_map,
        search_results,
        materialized=materialized,
        materialized_paper_ids=materialized_papers,
        source_qid=source,
        query=query,
        discovered_round=exploration_map.round,
    )
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    typer.echo(
        f"Observed LKM results for {pkg}: "
        f"{len(result.new_contacts)} new, {len(result.updated_contacts)} updated "
        f"lkm_related paper-contact(s)" + (f" (source {source})" if source else "") + "."
    )
    if result.new_contacts:
        typer.echo(f"  new papers: {', '.join(result.new_contacts)}")
    if result.updated_contacts:
        typer.echo(f"  merged papers: {', '.join(result.updated_contacts)}")
    typer.echo(
        "Next: `gaia-lkm-explore frontier` to rank them; pull the top via `pkg add --lkm-paper`."
    )


# --------------------------------------------------------------------------- #
# frontier                                                                    #
# --------------------------------------------------------------------------- #


def frontier_command(
    pkg: str = _PKG_ARG,
    json_out: bool = _FRONTIER_JSON_OPT,
) -> None:
    r"""Extract, score, and rank the exploration frontier.

    Loads the map, compiles the root IR graph (reusing the inquiry graph
    loader), builds the **joint** root+dependency view (SCHEMA.md §7e) — root +
    transitive ``-gaia`` dep graphs + every package's ``depends_on`` manifest —
    resolves any null-qid seeds against it, then runs ``JointView.extract`` →
    ``reconcile_frontier`` → ``score_frontier`` (scorer adjacency spans the joint
    edge set) and saves. Prints the ranked top-k open contacts (k =
    ``policy.budget_k``) — the survey shortlist the orchestrator client consumes.

    Example:

    .. code-block:: bash

        gaia-lkm-explore frontier ./pkg
        gaia-lkm-explore frontier ./pkg --json
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia-lkm-explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    graph = _require_graph(pkg)
    beliefs = _load_beliefs(pkg)

    # Joint root+dependency view (SCHEMA.md §7e): contacts are derived against the
    # union of every package's materialized QIDs, and edges span the root graph,
    # each dep graph, and every package's depends_on manifest records.
    view = _require_joint_view(pkg, graph)

    # Resolve any null-qid seed against the joint graph (#3) before scoring, so
    # closeness_to_seed bites this round.
    _resolve_seeds(exploration_map, graph, view)

    # (§7f) Promote any lkm_related contact whose paper is now materialized in
    # the joint view (pulled via `pkg add --lkm-paper`) so it leaves the open
    # frontier and is recorded as surveyed.
    promoted_papers = _promote_lkm_from_view(
        exploration_map, view, survey_round=exploration_map.round
    )

    extracted = view.extract(exploration_map)
    reconcile_frontier(exploration_map, extracted, discovered_round=exploration_map.round)
    # (build 12, CLIENT.md steer 3) Load the package's open synthetic obligations
    # and pass them to the scorer so this standalone verb scores
    # ``obligation_pressure`` exactly as ``gaia-lkm-explore turn`` does — the two
    # surfaces must agree (a contact discharging an open obligation scores 1.0).
    obligations = load_open_obligations(pkg)
    score_frontier(exploration_map, beliefs=beliefs, edges=view.edges, obligations=obligations)
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    ranked = _ranked_open_contacts(exploration_map)
    top_k = ranked[: exploration_map.policy.budget_k]

    if json_out:
        # Build 11 steer 4 (Jaynes' robot): the engine ranks by belief
        # (score_frontier, above) but the agent-facing frontier output never
        # surfaces the belief math. ``top_k`` is already belief-ordered; here we
        # drop the belief-derived ``belief_entropy`` feature and the raw
        # belief-weighted ``score`` from each emitted row. Ordering is preserved.
        rows = [
            {
                "id": c.id,
                "ref": c.ref,
                "score_features": sanitize_score_features(c.score_features),
                "sources": c.sources,
            }
            for c in top_k
        ]
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not beliefs:
        typer.echo("(no beliefs.json yet — run `gaia run infer` to rank the frontier)")
    if promoted_papers:
        typer.echo(
            f"Promoted {len(promoted_papers)} lkm_related contact(s) "
            f"(paper(s) now materialized): {', '.join(promoted_papers)}"
        )
    # ``ranked`` is already open-only; count the lkm_related share for legibility.
    n_lkm = sum(1 for c in ranked if c.ref.get("kind") == "lkm")
    typer.echo(
        f"Frontier: {len(ranked)} open contact(s) ({n_lkm} lkm_related); "
        f"top {len(top_k)} (budget_k={exploration_map.policy.budget_k}, "
        f"doctrine {exploration_map.policy.doctrine}):"
    )
    if not top_k:
        typer.echo("  (frontier empty — every referenced node is materialized)")
        return
    # Rank order conveys priority; the numeric belief-weighted score is NOT
    # printed (build 11 steer 4 — belief stays internal to the engine).
    obligation_contents = _obligation_contents(obligations)
    for rank, c in enumerate(top_k, start=1):
        ref = str(c.ref.get("value"))
        srcs = ", ".join(f"{s['qid']}[{s['edge']}]" for s in c.sources) or "(no sources)"
        if c.ref.get("kind") == "lkm":
            title = c.meta.get("title")
            label = f"paper:{ref}"
            if isinstance(title, str) and title:
                label = f'{label}  "{title}"'
            index_id = c.meta.get("index_id")
            idx_arg = f" --lkm-index {index_id}" if isinstance(index_id, str) else ""
            typer.echo(f"  {rank}. [lkm] {label}")
            typer.echo(f"       pull: gaia pkg add{idx_arg} --lkm-paper {ref}")
        else:
            typer.echo(f"  {rank}. {ref}")
        typer.echo(f"       via: {srcs}")
        # (theme 006) Surface that this contact discharges an open obligation —
        # set by the scorer's ref/source OR one-hop-adjacency match.
        if _is_obligation_pressed(c) and obligation_contents:
            typer.echo(f"       discharges open obligation: {'; '.join(obligation_contents[:2])}")


# --------------------------------------------------------------------------- #
# round                                                                       #
# --------------------------------------------------------------------------- #


def round_command(
    pkg: str = _PKG_ARG,
    surveyed: list[str] = _SURVEYED_OPT,
) -> None:
    r"""Complete one exploration round: discoveries + history + bookkeeping.

    Computes the v1 discovery taxonomy (contradiction / keystone / settled_core)
    from the current beliefs vs. the *previous* round's beliefs snapshot,
    appends a record to ``rounds.jsonl``, bumps ``map.round``, refreshes
    ``stats``, and snapshots this round's beliefs as the next round's baseline.

    The previous-round baseline is the compact
    ``.gaia/exploration/beliefs-round-<n>.json`` sidecar this command writes each
    round (chosen over a ``prev_beliefs`` block so ``rounds.jsonl`` keeps its
    schema shape).

    Example:

    .. code-block:: bash

        gaia-lkm-explore round ./pkg
        gaia-lkm-explore round ./pkg --surveyed github:pkg::claim7 --surveyed github:pkg::claim8
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia-lkm-explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    graph = _require_graph(pkg)
    beliefs = _load_beliefs(pkg)
    ir_dict = _load_ir_dict(pkg)

    current_round = exploration_map.round
    prev_beliefs = load_round_beliefs(pkg, current_round - 1) if current_round > 0 else {}

    # (§7f) Promote any lkm_related contact whose paper is now materialized in
    # the joint view (pulled via `pkg add --lkm-paper`), so `status` / the round
    # log agree with the frontier.
    view = _require_joint_view(pkg, graph)
    _promote_lkm_from_view(exploration_map, view, survey_round=current_round)

    # Record the surveyed QIDs into map.surveyed (SCHEMA.md §7e #4): promote a
    # matching open contact via the state bookkeeping, else add a bare
    # SurveyRecord so `status` surveyed-count and the round log agree.
    surveyed_qids = list(surveyed or [])
    _record_surveyed(exploration_map, surveyed_qids, survey_round=current_round)

    discoveries = compute_discoveries(graph, beliefs, prev_beliefs, ir_dict=ir_dict)

    open_after = sum(1 for c in exploration_map.frontier if c.status == "open")
    scored = [
        c.score for c in exploration_map.frontier if c.status == "open" and c.score is not None
    ]
    frontier_summary = {
        "open_after": open_after,
        "top_score": max(scored) if scored else None,
    }

    append_round(
        pkg,
        round_index=current_round,
        policy=exploration_map.policy,
        surveyed=surveyed_qids,
        discoveries=discoveries,
        frontier_summary=frontier_summary,
    )
    # Snapshot the beliefs THIS round saw, keyed by the round just completed, so
    # the next round (current_round + 1) can diff against it.
    save_round_beliefs(pkg, current_round, beliefs)

    exploration_map.round = current_round + 1
    _apply_discovery_tally(pkg, exploration_map)
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    kinds = ", ".join(sorted({d["kind"] for d in discoveries})) or "none"
    typer.echo(
        f"Round {current_round} complete (doctrine {exploration_map.policy.doctrine}): "
        f"{len(discoveries)} discovery(ies) [{kinds}], "
        f"{len(surveyed_qids)} surveyed, {open_after} open contact(s)."
    )
    typer.echo(f"Map advanced to round {exploration_map.round}.")


def _record_surveyed(
    exploration_map: ExplorationMap,
    surveyed_qids: list[str],
    *,
    survey_round: int,
) -> None:
    """Record surveyed QIDs into ``map.surveyed`` (SCHEMA.md §7e #4).

    For each QID: if an **open** frontier contact references it, promote that
    contact (flips its status to ``surveyed`` and adds a ``SurveyRecord`` with
    ``promoted_from_contact`` via the state bookkeeping). Otherwise add a bare
    ``SurveyRecord`` keyed by the QID. Idempotent — a QID already in
    ``map.surveyed`` is left as-is (its original survey round is preserved). After
    this, the ``status`` surveyed count and the ``rounds.jsonl`` ``surveyed`` list
    agree.
    """
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


def _apply_discovery_tally(pkg: str, exploration_map: ExplorationMap) -> None:
    """Write the per-kind discovery tally into ``map.stats['discoveries']``."""
    tally = _discovery_tally(pkg)
    stats = dict(exploration_map.stats)
    stats["discoveries"] = tally
    exploration_map.stats = stats


# --------------------------------------------------------------------------- #
# status                                                                      #
# --------------------------------------------------------------------------- #


def status_command(
    pkg: str = _PKG_ARG,
) -> None:
    r"""Print a human-readable exploration summary.

    Surveyed count, the top open frontier contacts by score, the most recent
    rounds (doctrine + discoveries), and the cumulative discovery tally.

    Example:

    .. code-block:: bash

        gaia-lkm-explore status ./pkg
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia-lkm-explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    rounds = read_rounds(pkg)
    ranked = _ranked_open_contacts(exploration_map)
    obligations = load_open_obligations(pkg)

    typer.echo(f"Exploration status for {pkg}")
    typer.echo(f"  round:          {exploration_map.round}")
    typer.echo(f"  doctrine:       {exploration_map.policy.doctrine}")
    typer.echo(f"  seeds:          {len(exploration_map.seeds)}")
    typer.echo(f"  surveyed:       {len(exploration_map.surveyed)}")
    n_lkm = sum(1 for c in ranked if c.ref.get("kind") == "lkm")
    typer.echo(f"  open frontier:  {len(ranked)} ({n_lkm} lkm_related)")

    # (theme 006) Surface open obligations and how many open contacts are pressed
    # by one — the agent-visible obligation_pressure steer (ref/source OR one-hop).
    n_pressed = sum(1 for c in ranked if _is_obligation_pressed(c))
    typer.echo(f"  open obligations: {len(obligations)} ({n_pressed} pressed contact(s))")
    if obligations:
        for o in obligations[:5]:
            content = str(getattr(o, "content", "")).strip() or "(no content)"
            typer.echo(f"    - {getattr(o, 'target_qid', '?')}: {content}")

    typer.echo("  top open contacts:")
    if not ranked:
        typer.echo("    (none)")
    else:
        # Ranked order (not the numeric belief-weighted score) is shown —
        # belief stays internal to the engine (build 11 steer 4).
        for rank, c in enumerate(ranked[:5], start=1):
            tag = "[lkm] paper:" if c.ref.get("kind") == "lkm" else ""
            pressed = "  [discharges open obligation]" if _is_obligation_pressed(c) else ""
            typer.echo(f"    {rank}. {tag}{c.ref.get('value')}{pressed}")

    typer.echo("  recent rounds:")
    if not rounds:
        typer.echo("    (none)")
    else:
        for rec in rounds[-5:]:
            doctrine = rec.get("policy", {}).get("doctrine", "?")
            discs = rec.get("discoveries", [])
            kinds = ", ".join(sorted({d.get("kind", "?") for d in discs})) or "none"
            typer.echo(
                f"    - round {rec.get('round')}: {doctrine}; {len(discs)} discovery(ies) [{kinds}]"
            )

    tally = _discovery_tally(pkg)
    typer.echo("  discovery tallies:")
    if not tally:
        typer.echo("    (none)")
    else:
        for kind in sorted(tally):
            typer.echo(f"    - {kind}: {tally[kind]}")


# --------------------------------------------------------------------------- #
# render                                                                      #
# --------------------------------------------------------------------------- #


def _node_roles(graph: Any) -> tuple[set[str], set[str], dict[str, str]]:
    """Derive contradiction/support QIDs + a label map from the IR graph (§7g).

    * ``contradiction_qids`` — every QID an authored CONTRADICTION operator ties
      together (its ``variables`` + ``conclusion``), so a node involved in a
      contradiction lights up red.
    * ``support_qids`` — every QID a Strategy (``derive``/support) ties together
      (``premises`` + ``conclusion`` + ``background``), lighting amber.
    * ``labels`` — ``qid -> short label`` from each Knowledge node's own ``label``,
      so the render need not parse QIDs to display a name.

    Best-effort and defensive: a graph missing an attribute simply contributes
    nothing to that set (the render degrades to QID-suffix labels / no glow).
    """
    contradiction: set[str] = set()
    support: set[str] = set()
    labels: dict[str, str] = {}

    for knowledge in getattr(graph, "knowledges", []):
        kid = getattr(knowledge, "id", None)
        label = getattr(knowledge, "label", None)
        if isinstance(kid, str) and isinstance(label, str) and label:
            labels[kid] = label

    for operator in getattr(graph, "operators", []):
        op_type = getattr(operator, "operator", None)
        if str(op_type) == "OperatorType.CONTRADICTION" or str(op_type) == "contradiction":
            refs = [*getattr(operator, "variables", []), getattr(operator, "conclusion", None)]
            contradiction.update(r for r in refs if isinstance(r, str))

    for strategy in getattr(graph, "strategies", []):
        refs = list(getattr(strategy, "premises", []) or [])
        conclusion = getattr(strategy, "conclusion", None)
        if isinstance(conclusion, str):
            refs.append(conclusion)
        refs.extend(getattr(strategy, "background", []) or [])
        support.update(r for r in refs if isinstance(r, str))

    return contradiction, support, labels


def render_command(
    pkg: str = _PKG_ARG,
    out: str | None = _RENDER_OUT_OPT,
) -> None:
    r"""Render the exploration map to a self-contained static HTML file (SCHEMA §7g).

    Loads the map + the joint root+dependency view + beliefs + the round history,
    derives each surveyed node's role (seed / contradiction / support) from the
    IR graph, and writes a single self-contained ``.html`` (inline SVG + CSS, no
    external assets, no JS) with our own deterministic radial layout: the seed at
    centre, surveyed nodes ringed by graph distance, frontier contacts on the
    outer rim. Prints the output path.

    Example:

    .. code-block:: bash

        gaia-lkm-explore render ./pkg
        gaia-lkm-explore render ./pkg --out /tmp/galileo-map.html
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia-lkm-explore init`/`frontier` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    graph = _require_graph(pkg)
    beliefs = _load_beliefs(pkg)
    view = _require_joint_view(pkg, graph)
    rounds = read_rounds(pkg)
    contradiction_qids, support_qids, labels = _node_roles(graph)

    html_doc = render_map_html(
        exploration_map,
        view,
        beliefs=beliefs,
        rounds=rounds,
        contradiction_qids=contradiction_qids,
        support_qids=support_qids,
        labels=labels,
    )

    out_path = (
        Path(out).resolve() if out is not None else _gaia_dir(pkg) / "exploration" / "map.html"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")

    typer.echo(
        f"Rendered exploration map for {pkg} "
        f"({len(exploration_map.surveyed)} surveyed, "
        f"{sum(1 for c in exploration_map.frontier if c.status == 'open')} open contact(s), "
        f"{len(html_doc)} bytes)."
    )
    typer.echo(f"Output: {out_path}")


__all__ = [
    "frontier_command",
    "init_command",
    "observe_command",
    "render_command",
    "round_command",
    "status_command",
]
