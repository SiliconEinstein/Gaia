"""Shared test fixtures."""

import os

import pytest

import lancedb.background_loop as _lance_bg

# Env vars that load_dotenv() may inject from .env and leak across tests.
# gateway/app.py calls load_dotenv() when create_app() is invoked without deps,
# which sets GAIA_LANCEDB_URI to s3://... causing later tests to hit remote S3.
_LEAKED_ENV_VARS = ("GAIA_LANCEDB_URI", "GAIA_NEO4J_URI")


@pytest.fixture(autouse=True)
def _clean_dotenv_leaks():
    """Remove env vars that load_dotenv() may have injected from .env."""
    yield
    for var in _LEAKED_ENV_VARS:
        os.environ.pop(var, None)


@pytest.fixture
def fresh_lancedb_loop():
    """Reset LanceDB background event loop before a test.

    LanceDB uses a module-level ``LOOP`` singleton (a daemon thread running
    ``asyncio.run_forever``). After many tests the loop can degrade, causing
    "Spill has sent an error" on merge-insert.  Replacing it with a fresh
    loop avoids the issue.  The old daemon thread exits on process end.
    """
    _lance_bg.LOOP = _lance_bg.BackgroundEventLoop()
