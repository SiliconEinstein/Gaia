"""Exploration turn-handoff envelopes (CLIENT.md "Envelopes").

The orchestrator client (``gaia-lkm-explore``) is stateless between runs and
save-game driven: it sequences the deterministic engine steps, then **hands the
fuzzy survey to an external agent** via a structured task envelope written to
disk, and consumes the agent's result envelope on the next invocation.

Two pydantic models live here, plus a small contact row the task carries:

* :class:`SurveyTask` — ``turn-<n>.task.json`` (client → agent). A
  *self-contained* survey instruction: the round's doctrine + budget, the ranked
  contacts to survey (each with its score breakdown and a per-contact
  ``survey_brief``), the full survey procedure baked into ``instructions`` (so an
  agent reading **only** the task can survey correctly — there is no skill), and
  the ``result_path`` the agent must write back to.
* :class:`SurveyResult` — ``turn-<n>.result.json`` (agent → client). The
  single irreducible handoff signal: the QIDs the agent materialized this round.
  The heavy state already landed in the package + save-game via the agent's
  ``observe`` / ``author`` calls, and the durable timeline is the client's
  (``rounds.jsonl``) — so the agent has no logging duty; it reports only *what*
  it surveyed so the checkpoint can record it honestly.

The orchestrator **infers** the ``AWAITING_CHECKPOINT`` phase from the presence
of the result manifest (CLIENT.md "Resolved") — the agent never sets
``turn_phase`` by hand.

These are pydantic v2 models (``.model_dump()`` / ``.model_validate()`` /
``.model_validate_json()`` per the repo style) rather than dataclasses, because
the envelope is the cross-process contract with an external agent and benefits
from validation on the way in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# The on-disk envelope filenames are keyed by round so a turn's task and result
# travel together and several turns' artifacts can coexist for legibility.
TASK_FILENAME_TEMPLATE = "turn-{round}.task.json"
RESULT_FILENAME_TEMPLATE = "turn-{round}.result.json"


def task_path(exploration_dir: str | Path, round_index: int) -> Path:
    """Return the task-envelope path for a round under an exploration dir."""
    return Path(exploration_dir) / TASK_FILENAME_TEMPLATE.format(round=round_index)


def result_path(exploration_dir: str | Path, round_index: int) -> Path:
    """Return the result-envelope path for a round under an exploration dir."""
    return Path(exploration_dir) / RESULT_FILENAME_TEMPLATE.format(round=round_index)


class TaskContact(BaseModel):
    """One contact the agent should survey this turn (a row of ``contacts``).

    Mirrors the open :class:`~gaia.engine.exploration.state.Contact` the engine
    ranked, flattened for the agent: ``id`` / ``ref`` / ``score`` /
    ``score_features`` / ``sources`` come straight off the contact, plus a
    per-contact ``survey_brief`` the client composes (what the contact is, how it
    is reached, and the concrete next command — e.g. the ``gaia pkg add
    --lkm-paper`` pull line for an ``lkm_related`` paper-contact).
    """

    id: str
    ref: dict[str, Any]
    score: float | None = None
    score_features: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    survey_brief: str = ""


class IslandBrief(BaseModel):
    """One disconnected island in a consolidate task's bridge worklist (EXPANSION.md §3.D).

    A consolidate turn operates over ALREADY-surveyed nodes (no new pulls): for
    each orphan island the agent either authors a connecting
    ``derive``/``contradict``/``depends_on`` to wire it to the core, OR ratifies
    it as a legitimately separate region.

    Attributes:
        member_qids: the surveyed QIDs in this island (the component members).
        brief: a short NL description of the island (its node labels / what it is)
            so the agent can judge whether a sound connection exists.
        reopened: whether this island was previously ratified and is back on the
            worklist because new evidence may now connect it (provisional reopen).
        bridge_hint: when ``reopened`` (or otherwise bridgeable), the QID whose
            presence may now connect this island to the core — surfaced in the
            "reconsider" note.
    """

    member_qids: list[str] = Field(default_factory=list)
    brief: str = ""
    reopened: bool = False
    bridge_hint: str | None = None


class SurveyTask(BaseModel):
    """The task envelope (client → agent): ``turn-<n>.task.json``.

    Self-contained per CLIENT.md "no skill": ``instructions`` carries the full
    survey procedure absorbed from the retired ``gaia-lkm-explorer`` skill, so an
    agent reading only this file can survey correctly and re-invoke the client.

    EXPANSION.md §3.D adds a ``kind`` discriminator: an ``"expand"`` task is the
    today's-behaviour frontier shortlist (``contacts``); a ``"consolidate"`` task
    instead carries a ``bridge_worklist`` of disconnected ``islands`` (over
    already-surveyed nodes) for the agent to bridge-or-ratify. Default ``"expand"``
    keeps a task written before this existed back-compat.
    """

    pkg: str
    round: int
    doctrine: str
    budget_k: int
    # EXPANSION.md §3.D — task kind discriminator (default expand, back-compat).
    kind: str = "expand"
    contacts: list[TaskContact] = Field(default_factory=list)
    # EXPANSION.md §3.D — the consolidate bridge worklist (empty for an expand
    # task): the disconnected islands/orphans, each with a per-island brief.
    bridge_worklist: list[IslandBrief] = Field(default_factory=list)
    # CLIENT.md round-0 special case: a seed-survey task instead of a frontier
    # shortlist. The client sets this so the agent knows to survey the seed text.
    seed_survey: bool = False
    instructions: str = ""
    result_path: str = ""

    def write(self, path: str | Path) -> Path:
        """Atomically write this task to ``path`` and return it."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(p)
        return p

    @classmethod
    def read(cls, path: str | Path) -> SurveyTask:
        """Load and validate a task envelope from ``path``."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class RatifiedSeparationResult(BaseModel):
    """One island the agent ratified as legitimately separate (EXPANSION.md §3.E).

    The agent reports the island's surveyed-node set and a one-line scientific
    rationale; the orchestrator records it into ``map.ratified_separations`` (with
    the round + evidence fingerprint it stamps) so MapHealth excludes the island
    from the unhealthy count until new evidence reopens it.
    """

    member_qids: list[str] = Field(default_factory=list)
    rationale: str = ""


class SurveyResult(BaseModel):
    """The result envelope (agent → client): ``turn-<n>.result.json``.

    The single irreducible handoff signal (CLIENT.md "Build 9" / Occam): the QIDs
    the agent materialized this round. The heavy state already landed in the
    package + save-game via the agent's ``observe`` / ``author`` calls, and the
    durable timeline is the client's (``rounds.jsonl``) — so the agent has no
    logging duty. ``surveyed_qids`` feeds ``explore round --surveyed``.

    Pydantic's default ``extra="ignore"`` means legacy result files carrying the
    retired ``observed`` / ``notes`` keys still read without error — the extra
    keys are tolerated and dropped.

    EXPANSION.md §3.E adds the consolidate outcome: ``ratified`` carries the
    islands the agent judged legitimately-separate this turn (each a
    :class:`RatifiedSeparationResult`). It is the one consolidate signal the
    orchestrator cannot infer from the authored DSL (a bridge authored as a
    ``derive`` shows up in the graph; a *non-connection* — "this island is
    legitimately apart" — has no graph footprint, so the agent must report it).
    Default empty keeps an expand-turn result envelope just ``{surveyed_qids}``,
    back-compat.
    """

    surveyed_qids: list[str] = Field(default_factory=list)
    ratified: list[RatifiedSeparationResult] = Field(default_factory=list)

    def write(self, path: str | Path) -> Path:
        """Atomically write this result to ``path`` and return it."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(p)
        return p

    @classmethod
    def read(cls, path: str | Path) -> SurveyResult:
        """Load and validate a result envelope from ``path``."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "RESULT_FILENAME_TEMPLATE",
    "TASK_FILENAME_TEMPLATE",
    "IslandBrief",
    "RatifiedSeparationResult",
    "SurveyResult",
    "SurveyTask",
    "TaskContact",
    "result_path",
    "task_path",
]
