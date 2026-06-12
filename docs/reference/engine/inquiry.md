# Inquiry API

> **Status:** Generated from current Python docstrings and type hints.

Semantic-inquiry state machine, focus tracking, obligations, hypotheses,
rejections, review reports, and structured diagnostics for the
`gaia inquiry` CLI sub-app. Five of the 45 public symbols moved here
from `gaia.cli.*` in alpha 0 (`KnowledgeBreakdown`, `HoleEntry`,
`analyze_knowledge_breakdown`, `find_possible_duplicate_claims`,
`load_or_generate_review_manifest`).

## Downstream Research Contract

The future `gaia-research` package may depend on the inquiry-state subset named
by `RESEARCH_PUBLIC_STATE_API`. Gaia core treats that subset as a public
semver-governed contract for reading and updating `.gaia/inquiry/state.json`
and the append-only tactic log:

- `STATE_SCHEMA_VERSION`
- `VALID_OBLIGATION_KINDS`
- `InquiryState`
- `SyntheticHypothesis`
- `SyntheticObligation`
- `append_tactic_event`
- `load_state`
- `mint_qid`
- `save_state`

Downstream research code should import these symbols from `gaia.engine.inquiry`
or `gaia.engine.inquiry.state`; it should not import inquiry helpers from
`gaia.cli.*` modules.

::: gaia.engine.inquiry
