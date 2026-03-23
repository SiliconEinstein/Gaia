# Review Engine

> **Status:** Current canonical — target evolution noted

The review engine evaluates knowledge packages and produces probability parameters for belief propagation. It exists as two client implementations in `cli/llm_client.py` and is orchestrated by `libs/pipeline.py:pipeline_review()`.

## What Review Produces

`pipeline_review()` returns a `ReviewOutput` containing:

- **`node_priors`** — `dict[str, float]` mapping each local canonical node ID to its prior probability. Priors are assigned by knowledge type: `setting` = 1.0, `claim`/`question`/`action`/`observation` = 0.5.
- **`factor_params`** — `dict[str, FactorParams]` mapping each inference factor to its conditional probability. Values come from review chain steps (`conditional_prior` field); defaults to 1.0 if no review data.
- **`review`** — raw review data including summary text and per-chain step assessments.
- **`model`** — which model produced the review (`"mock"` or an LLM model name).

## ReviewClient (LLM)

`ReviewClient` uses `litellm` to send the package markdown to an LLM with a system prompt (`cli/prompts/review_system.md`). The LLM returns YAML containing per-chain step assessments with `conditional_prior`, `weak_points`, and `explanation` fields.

The parser (`_parse_response`) handles multiple YAML shapes:
- Structured format with `chains` list containing `steps`
- Flat format with `chain_name.step_index` keys
- Falls back to `{"summary": "Parse error", "chains": []}` on failure

Both sync (`review_package`) and async (`areview_package`) interfaces are provided.

## MockReviewClient

`MockReviewClient` produces deterministic review output without LLM calls:

- `review_from_graph_data()` — used by `pipeline_review(mock=True)`. Iterates over reasoning factors in `graph_data` and assigns `conditional_prior: 0.85` to each.
- `review_package()` — parses `[step:name.N]` anchors from markdown (legacy format).

Mock review is used by all CLI commands (`gaia infer`, `gaia publish --local`) and in tests.

## Pipeline Integration

`libs/pipeline.py:pipeline_review()` orchestrates the flow:

1. If `mock=True`, call `MockReviewClient.review_from_graph_data(graph_data)`
2. If `mock=False`, render markdown from graph data, call `ReviewClient.areview_package()`
3. Build `node_priors` from `LocalCanonicalGraph` knowledge nodes using type-based defaults
4. Build `factor_params` by mapping review chain conclusions back to factor IDs via the local graph
5. Return `ReviewOutput`

The review output feeds directly into `pipeline_infer()`, which constructs a `LocalParameterization` and runs BP.

## Code Paths

| Component | File |
|-----------|------|
| ReviewClient | `cli/llm_client.py:ReviewClient` |
| MockReviewClient | `cli/llm_client.py:MockReviewClient` |
| Review pipeline function | `libs/pipeline.py:pipeline_review()` |
| System prompt | `cli/prompts/review_system.md` |
| Prior/param builders | `libs/pipeline.py:_build_node_priors()`, `_build_factor_params()` |

## Current State

`pipeline_review()` supports both paths via the `mock` parameter. Current CLI commands (`gaia infer`, `gaia publish --local`) and pipeline scripts default to `mock=True` (deterministic, no LLM calls). Real LLM review requires explicit `mock=False` plus valid API credentials (`OPENAI_API_BASE`, `OPENAI_API_KEY`). The review client lives in `cli/` rather than `libs/` because it was originally CLI-only.

## Target State

- Move review logic to a server-side `ReviewService` that runs automatically on package ingest.
- Relocate `ReviewClient` from `cli/` to `libs/` or `services/` so it can be shared by CLI and server.
- Add `gaia review` CLI command that invokes real LLM review and saves a review sidecar.
