"""``gaia-lkm-explore`` — the unified exploration client (CLIENT.md).

A **sibling client of ``gaia``** and, as of build 7 (CLIENT.md "Unified
surface"), the *single* user-facing surface for exploration. It carries both the
deterministic engine verbs (``init`` / ``observe`` / ``frontier`` / ``round`` /
``status`` / ``render``, migrated here from the removed ``gaia explore`` sub-app)
and the orchestrator phase-aware ``turn`` step that sequences the engine via the
SDK and hands *only* the fuzzy survey to an external agent through a
self-contained task envelope. It NEVER reasons over evidence itself.

This promotes the exploration turn loop from *skill-as-driver* to code: the
machinery that used to be prose in the ``gaia-lkm-explorer`` skill now lives here,
and the skill's survey procedure is **absorbed** into the task template
(:mod:`gaia.explore_client.instructions`) so each emitted task is self-contained
— there is no registered skill any more.

Layering (CLIENT.md):

* ``gaia`` (engine + deterministic CLI) — ``search lkm``, ``pkg add``,
  compile / infer, SDK authoring; the ``gaia.engine.exploration`` library.
* ``gaia-lkm-explore`` (this client) — the engine verbs + the phase-aware turn
  state machine; sequences the engine via the SDK; emits / consumes the
  survey-task envelope.
* agent (thin) — the survey only, then re-invokes the client.
"""

from gaia.explore_client.orchestrator import TurnOutcome, run_turn

__all__ = ["TurnOutcome", "run_turn"]
