"""Shared fixtures for storage_v2 tests."""

import json
from pathlib import Path

import pytest

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
)

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "storage_v2"


def load_fixture(name: str) -> list[dict]:
    """Load a JSON fixture file from tests/fixtures/storage_v2/."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())


@pytest.fixture()
def packages() -> list[Package]:
    return [Package.model_validate(r) for r in load_fixture("packages")]


@pytest.fixture()
def modules() -> list[Module]:
    return [Module.model_validate(r) for r in load_fixture("modules")]


@pytest.fixture()
def knowledge_items() -> list[Knowledge]:
    return [Knowledge.model_validate(r) for r in load_fixture("knowledge")]


@pytest.fixture()
def chains() -> list[Chain]:
    return [Chain.model_validate(r) for r in load_fixture("chains")]


@pytest.fixture()
def probabilities() -> list[ProbabilityRecord]:
    return [ProbabilityRecord.model_validate(r) for r in load_fixture("probabilities")]


@pytest.fixture()
def beliefs() -> list[BeliefSnapshot]:
    return [BeliefSnapshot.model_validate(r) for r in load_fixture("beliefs")]


@pytest.fixture()
def resources() -> list[Resource]:
    return [Resource.model_validate(r) for r in load_fixture("resources")]


@pytest.fixture()
def attachments() -> list[ResourceAttachment]:
    return [ResourceAttachment.model_validate(r) for r in load_fixture("attachments")]


# ── Store fixtures ──


@pytest.fixture()
async def content_store(tmp_path):
    from libs.storage_v2.lance_content_store import LanceContentStore

    store = LanceContentStore(str(tmp_path / "lance"))
    await store.initialize()
    return store
