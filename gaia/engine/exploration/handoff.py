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
* :class:`SurveyResult` — ``turn-<n>.result.json`` (agent → client). Minimal:
  the heavy state already landed in the package + save-game via the agent's
  ``observe`` / ``author`` calls, so the result only reports *what* was surveyed
  so the checkpoint can record it honestly.

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


class SurveyTask(BaseModel):
    """The task envelope (client → agent): ``turn-<n>.task.json``.

    Self-contained per CLIENT.md "no skill": ``instructions`` carries the full
    survey procedure absorbed from the retired ``gaia-lkm-explorer`` skill, so an
    agent reading only this file can survey correctly and re-invoke the client.
    """

    pkg: str
    round: int
    doctrine: str
    budget_k: int
    contacts: list[TaskContact] = Field(default_factory=list)
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


class SurveyResult(BaseModel):
    """The result envelope (agent → client): ``turn-<n>.result.json``.

    Minimal by design (CLIENT.md "Envelopes"): the heavy state already landed in
    the package + save-game via the agent's ``observe`` / ``author`` calls. The
    client only needs *what* was surveyed to record the checkpoint honestly, so
    ``surveyed_qids`` feeds ``explore round --surveyed``.
    """

    surveyed_qids: list[str] = Field(default_factory=list)
    observed: bool = False
    notes: str = ""

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
    "SurveyResult",
    "SurveyTask",
    "TaskContact",
    "result_path",
    "task_path",
]
