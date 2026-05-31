"""``gaia.lkm_explorer`` — the self-contained LKM-explorer module.

This package consolidates the whole exploration surface into one place, with two
internal subpackages:

* :mod:`gaia.lkm_explorer.engine` — the deterministic adjudication library
  (the fog-of-war map-state schema, frontier extraction, scoring, observation,
  discoveries, health, landscape, promotion, and rendering). Pure and I/O-free
  at its core; never reasons over evidence itself.
* :mod:`gaia.lkm_explorer.client` — the ``gaia-lkm-explore`` turn-loop
  orchestrator and CLI. It carries the deterministic engine verbs (``init`` /
  ``observe`` / ``frontier`` / ``round`` / ``status`` / ``render``) and the
  phase-aware ``turn`` step that sequences the engine via the SDK and hands
  *only* the fuzzy survey to an external agent through a self-contained task
  envelope.

The public API is re-exported here for convenience.
"""

from gaia.lkm_explorer.client.orchestrator import TurnOutcome, run_turn

__all__ = ["TurnOutcome", "run_turn"]
