"""gaia explore — the deterministic exploration-engine CLI (SCHEMA.md §7c, build 4a).

This is the *engine* half of the exploration turn loop's "LLM proposes / engine
adjudicates" split (DESIGN §2): a Typer sub-app over
:mod:`gaia.engine.exploration` that an agent (the evolved ``gaia-lkm-explorer``
skill, build 4b) drives. It is pure and deterministic — **no LKM call, no
``gaia author`` orchestration, no render** live here; those are 4b.

Commands (SCHEMA.md §7c):

* ``explore init <pkg> --seed … [--doctrine …]`` — create
  ``.gaia/exploration/map.json`` with seeds + a policy from the named doctrine.
* ``explore frontier <pkg>`` — load map + IR + manifest + beliefs, run
  ``extract_frontier`` → ``reconcile_frontier`` → ``score_frontier``, save, and
  print the ranked top-k open contacts for the skill to survey.
* ``explore round <pkg> [--surveyed …]`` — compute discoveries vs. the previous
  round's beliefs, append a round record, bump ``map.round``, refresh ``stats``.
* ``explore status <pkg>`` — a human-readable map summary.

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
from gaia.engine.exploration.frontier import JointView, build_joint_view, reconcile_frontier
from gaia.engine.exploration.scorer import score_frontier
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

explore_app = typer.Typer(
    name="explore",
    help=(
        "Gaia Explore — fog-of-war exploration of a knowledge package "
        "(init / frontier / round / status)."
    ),
    no_args_is_help=True,
)

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
       ``inquiry/focus.resolve_focus_target``.

    Returns ``True`` if any seed was newly resolved (so the caller can persist).
    """
    changed = False
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
    return changed


def _ranked_open_contacts(exploration_map: ExplorationMap) -> list[Contact]:
    """Open contacts sorted by score (desc, ``None`` last) then id."""
    open_contacts = [c for c in exploration_map.frontier if c.status == "open"]
    return sorted(
        open_contacts,
        key=lambda c: (c.score is None, -(c.score or 0.0), c.id),
    )


# --------------------------------------------------------------------------- #
# init                                                                        #
# --------------------------------------------------------------------------- #


@explore_app.command("init")
def init_command(
    pkg: str = _PKG_ARG,
    seed: list[str] = _SEED_OPT,
    doctrine: str = _DOCTRINE_OPT,
    budget_k: int = _BUDGET_K_OPT,
) -> None:
    r"""Create the exploration map (``.gaia/exploration/map.json``).

    Seeds are the inquiry origins. A seed that looks like a QID (contains
    ``::``) is recorded resolved (``kind="claim"``, ``qid`` set) so the scorer's
    ``closeness_to_seed`` can use it immediately; a free-text seed is recorded as
    a ``question`` with ``qid: null`` until the agent materializes it.

    Example:

    .. code-block:: bash

        gaia explore init ./pkg --seed "Why do bodies fall?" --doctrine Surveyor
        gaia explore init ./pkg --seed github:pkg::aristotle_model --seed other::q
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
# frontier                                                                    #
# --------------------------------------------------------------------------- #


@explore_app.command("frontier")
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
    ``policy.budget_k``) — the survey shortlist the skill consumes.

    Example:

    .. code-block:: bash

        gaia explore frontier ./pkg
        gaia explore frontier ./pkg --json
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia explore init` first.",
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

    extracted = view.extract(exploration_map)
    reconcile_frontier(exploration_map, extracted, discovered_round=exploration_map.round)
    score_frontier(exploration_map, beliefs=beliefs, edges=view.edges)
    _refresh_stats(exploration_map)
    save_map(pkg, exploration_map)

    ranked = _ranked_open_contacts(exploration_map)
    top_k = ranked[: exploration_map.policy.budget_k]

    if json_out:
        rows = [
            {
                "id": c.id,
                "ref": c.ref,
                "score": c.score,
                "score_features": c.score_features,
                "sources": c.sources,
            }
            for c in top_k
        ]
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not beliefs:
        typer.echo("(no beliefs.json — scores use 0.0 belief_entropy; run `gaia run infer`)")
    typer.echo(
        f"Frontier: {len(ranked)} open contact(s); "
        f"top {len(top_k)} (budget_k={exploration_map.policy.budget_k}, "
        f"doctrine {exploration_map.policy.doctrine}):"
    )
    if not top_k:
        typer.echo("  (frontier empty — every referenced node is materialized)")
        return
    for rank, c in enumerate(top_k, start=1):
        score = "n/a" if c.score is None else f"{c.score:+.3f}"
        ref = str(c.ref.get("value"))
        srcs = ", ".join(f"{s['qid']}[{s['edge']}]" for s in c.sources) or "(no sources)"
        typer.echo(f"  {rank}. {score}  {ref}")
        typer.echo(f"       via: {srcs}")


# --------------------------------------------------------------------------- #
# round                                                                       #
# --------------------------------------------------------------------------- #


@explore_app.command("round")
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

        gaia explore round ./pkg
        gaia explore round ./pkg --surveyed github:pkg::claim7 --surveyed github:pkg::claim8
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    graph = _require_graph(pkg)
    beliefs = _load_beliefs(pkg)
    ir_dict = _load_ir_dict(pkg)

    current_round = exploration_map.round
    prev_beliefs = load_round_beliefs(pkg, current_round - 1) if current_round > 0 else {}

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


@explore_app.command("status")
def status_command(
    pkg: str = _PKG_ARG,
) -> None:
    r"""Print a human-readable exploration summary.

    Surveyed count, the top open frontier contacts by score, the most recent
    rounds (doctrine + discoveries), and the cumulative discovery tally.

    Example:

    .. code-block:: bash

        gaia explore status ./pkg
    """
    if not (_gaia_dir(pkg) / "exploration" / "map.json").exists():
        typer.echo(
            f"Error: no exploration map at {pkg}; run `gaia explore init` first.",
            err=True,
        )
        raise typer.Exit(1)

    exploration_map = load_map(pkg)
    rounds = read_rounds(pkg)
    ranked = _ranked_open_contacts(exploration_map)

    typer.echo(f"Exploration status for {pkg}")
    typer.echo(f"  round:          {exploration_map.round}")
    typer.echo(f"  doctrine:       {exploration_map.policy.doctrine}")
    typer.echo(f"  seeds:          {len(exploration_map.seeds)}")
    typer.echo(f"  surveyed:       {len(exploration_map.surveyed)}")
    typer.echo(f"  open frontier:  {len(ranked)}")

    typer.echo("  top open contacts:")
    if not ranked:
        typer.echo("    (none)")
    else:
        for c in ranked[:5]:
            score = "n/a" if c.score is None else f"{c.score:+.3f}"
            typer.echo(f"    - {score}  {c.ref.get('value')}")

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
