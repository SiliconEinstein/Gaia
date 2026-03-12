# Server-Side V2 Commit/Review/Merge Pipeline

**Status:** Not yet implemented. See xfail tests in `tests/integration/test_v2_e2e.py::TestV2ServerCommitReviewMerge`.

## Current State

V2 storage currently supports:
- `POST /v2/packages/ingest` — bulk ingest (CLI-originated data)
- `GET /v2/packages/{id}`, `GET /v2/knowledge/{id}`, etc. — read endpoints

## Planned Endpoints

### Commit Workflow
- `POST /v2/commits` — submit operations (add_knowledge, add_chain, modify_knowledge, etc.)
- `GET /v2/commits/{id}` — get commit status
- `POST /v2/commits/{id}/review` — trigger async review (LLM + BP)
- `GET /v2/commits/{id}/review` — poll review status
- `GET /v2/commits/{id}/review/result` — get review result
- `POST /v2/commits/{id}/merge` — apply to storage

### Search
- `POST /v2/search/knowledge` — BM25 full-text search
- `POST /v2/search/vector` — embedding similarity search
- `POST /v2/search/topology` — graph traversal search

## Design Considerations

1. **V2 CommitEngine**: Needs to be built on top of v2 StorageManager, not v1.
   The v1 CommitEngine operates on Node/HyperEdge; v2 operates on Knowledge/Chain.

2. **Review Pipeline**: Can reuse existing operators (BP, embedding, etc.) but needs
   adapters for v2 models.

3. **Merge**: Already implemented as `StorageManager.ingest_package()` for bulk writes.
   Individual operations (modify single knowledge item) need additional methods.

4. **Search**: StorageManager already has `search_bm25()`, `search_vector()`,
   `search_topology()`. Just need HTTP route wrappers + request/response models.
