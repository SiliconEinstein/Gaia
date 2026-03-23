# Testing

> **Status:** Current canonical

This document describes the test infrastructure, conventions, and how to run tests.

## Running Tests

```bash
# Run all tests (auto-skips Neo4j tests if unavailable)
pytest

# Run with coverage
pytest --cov=libs --cov=services tests

# Run a single file or test
pytest tests/libs/storage/test_lance_content.py
pytest tests/libs/storage/test_models.py::test_knowledge_defaults
```

All async tests run automatically via `asyncio_mode = "auto"` (configured in `pyproject.toml`).

## Test Directory Structure

```
tests/
  conftest.py                      # Global fixtures
  cli/                             # CLI command tests
    test_build.py
    test_clean.py
    test_gaia_main.py
    test_init.py
    test_search.py
  libs/                            # Unit tests for libs/
    curation/                      # Curation engine tests
    global_graph/                  # Global canonicalization tests
    graph_ir/                      # Graph IR compiler tests
    inference/                     # BP engine tests
    lang/                          # Typst loader + language tests
    storage/                       # Storage backend tests
      test_lance_content.py
      test_graph_store.py
      test_manager.py
      test_models.py
      test_remote_storage.py
      test_three_write.py
      test_vector_store.py
  integration/                     # End-to-end pipeline tests
    test_cli_pipeline_real_api.py  # Full CLI pipeline with real LLM API
    test_e2e.py                    # HTTP endpoint integration
    test_v4_pipeline.py            # v4 Typst pipeline end-to-end
  scripts/                         # Pipeline script tests
    test_build_graph_ir.py
  services/
    test_gateway/                  # FastAPI route tests
      test_packages_list_routes.py
  fixtures/                        # Shared test data
    curation/
    examples/                      # Example packages (einstein_elevator, galileo_tied_balls)
    gaia_language_packages/        # v4 Typst test packages
    global_graph/
    inputs/papers/                 # Raw paper inputs for pipeline tests
    storage/                       # Pre-built storage fixtures
```

## Key Fixtures

**`conftest.py` (root)**

- `_clean_dotenv_leaks` (autouse) — Removes `GAIA_LANCEDB_URI` and `GAIA_NEO4J_URI` from the environment after each test. Prevents `.env` values loaded by `create_app()` from leaking into subsequent tests and hitting remote S3.

- `fresh_lancedb_loop` — Resets the LanceDB background event loop singleton before a test. LanceDB uses a module-level daemon thread that can degrade after many tests; this fixture creates a fresh loop to avoid merge-insert errors.

**`tests/libs/storage/conftest.py`**

Storage tests use `tmp_path` for DB isolation — each test gets a fresh LanceDB directory, preventing cross-test interference.

## Test Categories

**Unit tests (`tests/libs/`)** — Test individual library modules in isolation. Storage tests use `tmp_path`-based LanceDB instances. No external services required.

**CLI tests (`tests/cli/`)** — Test CLI commands by invoking `cli/main.py` functions directly or via Typer's test runner. Use temporary directories for package scaffolding and build artifacts.

**Service tests (`tests/services/`)** — Test FastAPI routes via `httpx.AsyncClient` with `create_app(dependencies=...)` injecting test storage. No real server needed.

**Integration tests (`tests/integration/`)** — End-to-end tests that exercise full pipelines. `test_v4_pipeline.py` runs build/review/infer/publish on fixture packages. `test_cli_pipeline_real_api.py` requires real LLM API access.

**Script tests (`tests/scripts/`)** — Test pipeline scripts (e.g., `build_graph_ir.py`) against fixture data.

## Common Patterns

- **`tmp_path` for DB isolation:** Storage tests create fresh LanceDB instances in pytest's `tmp_path` to avoid cross-test state.
- **Async tests:** All async test functions are discovered and run automatically via `asyncio_mode = "auto"`. No `@pytest.mark.asyncio` decorator needed.
- **Neo4j auto-skip:** Tests requiring Neo4j check for a running instance and skip automatically if unavailable. CI provides Neo4j via a service container.
- **Dependency injection in route tests:** Service tests call `create_app(dependencies=test_deps)` to inject mock storage, avoiding real database connections.
- **Fixture packages:** `tests/fixtures/gaia_language_packages/` contains v4 Typst packages (e.g., `galileo_falling_bodies_v4`, `einstein_gravity_v4`) used across build, infer, and publish tests.

## Code Paths

| Component | File |
|-----------|------|
| Root conftest | `tests/conftest.py` |
| Storage conftest | `tests/libs/storage/conftest.py` |
| Pytest config | `pyproject.toml` (asyncio_mode, test paths) |
