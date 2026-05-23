"""``gaia-explore`` — the exploration orchestrator client (CLIENT.md).

A **sibling client of ``gaia``**: a real orchestrator that sequences the
exploration turn, drives the deterministic ``gaia.engine.exploration`` engine via
the SDK, and hands *only* the fuzzy survey to an external agent through a
self-contained task envelope. It NEVER reasons over evidence itself.

This promotes the exploration turn loop from *skill-as-driver* to code: the
machinery that used to be prose in the ``gaia-lkm-explorer`` skill now lives here,
and the skill's survey procedure is **absorbed** into the task template
(:mod:`gaia.explore_client.instructions`) so each emitted task is self-contained
— there is no registered skill any more.

Layering (CLIENT.md):

* ``gaia`` (engine + deterministic CLI) — ``explore`` verbs, ``search lkm``,
  ``pkg add``, compile / infer, SDK authoring.
* ``gaia-explore`` (this client) — the phase-aware turn state machine; sequences
  the engine via the SDK; emits / consumes the survey-task envelope.
* agent (thin) — the survey only, then re-invokes the client.
"""

from gaia.explore_client.orchestrator import TurnOutcome, run_turn

__all__ = ["TurnOutcome", "run_turn"]
