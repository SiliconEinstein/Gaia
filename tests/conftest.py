"""Shared test fixtures."""

import pytest

import lancedb.background_loop as _lance_bg


@pytest.fixture
def fresh_lancedb_loop():
    """Reset LanceDB background event loop before a test.

    LanceDB uses a module-level ``LOOP`` singleton (a daemon thread running
    ``asyncio.run_forever``). After many tests the loop can degrade, causing
    "Spill has sent an error" on merge-insert.  Replacing it with a fresh
    loop avoids the issue.  The old daemon thread exits on process end.
    """
    _lance_bg.LOOP = _lance_bg.BackgroundEventLoop()
