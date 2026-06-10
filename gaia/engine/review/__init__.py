"""gaia.engine.review — review engine (thin orchestration, no new IR/BP logic).

This package provides:
  - _schemas: pydantic report/finding/recommendation models
  - calibration: Δ_qid computation + honesty check
  - orchestrator: merge inquiry + trace + calibration into unified PackageReviewReport
  - status: read-only package review status
  - redteam: deterministic adversarial heuristic review
  - diff: semantic diff report orchestration
  - gate: composed pass/warn/fail review gates
  - query: structured review queries
"""
