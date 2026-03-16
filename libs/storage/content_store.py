"""ContentStore ABC — LanceDB backend contract for full content and metadata."""

from abc import ABC, abstractmethod

from libs.storage.models import (
    BeliefSnapshot,
    CanonicalBinding,
    Chain,
    FactorNode,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    Module,
    Package,
    PackageSubmissionArtifact,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
)


class ContentStore(ABC):
    """LanceDB — full content, metadata, and BM25 search."""

    # ── Schema setup ──

    @abstractmethod
    async def initialize(self) -> None:
        """Create or verify all required tables/schemas."""

    # ── Delete ──

    @abstractmethod
    async def delete_package(self, package_id: str) -> None:
        """Delete all data belonging to a package (idempotent re-publish)."""

    @abstractmethod
    async def commit_package(self, package_id: str, version: str) -> None:
        """Flip a package's status from 'preparing' to 'committed' (= 'merged')."""

    @abstractmethod
    async def get_committed_packages(self) -> set[tuple[str, str]]:
        """Return (package_id, version) pairs with status='merged'. Used for visibility."""

    # ── Write ──

    @abstractmethod
    async def write_package(self, package: Package, modules: list[Module]) -> None:
        """Write a package and its modules."""

    @abstractmethod
    async def write_knowledge(self, knowledge_items: list[Knowledge]) -> None:
        """Write knowledge items (skip duplicates by (knowledge_id, version))."""

    @abstractmethod
    async def write_chains(self, chains: list[Chain]) -> None:
        """Write reasoning chains."""

    @abstractmethod
    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None:
        """Append probability records."""

    @abstractmethod
    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None:
        """Append belief snapshots from a BP run."""

    @abstractmethod
    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None:
        """Write resource metadata and attachment links."""

    # ── Read ──

    @abstractmethod
    async def get_knowledge(
        self, knowledge_id: str, version: int | None = None
    ) -> Knowledge | None:
        """Get a knowledge item by id. If version is None, return the latest version."""

    @abstractmethod
    async def get_knowledge_versions(self, knowledge_id: str) -> list[Knowledge]:
        """Get all versions of a knowledge item, ordered by version ascending."""

    @abstractmethod
    async def get_package(self, package_id: str) -> Package | None:
        """Get a package by id."""

    @abstractmethod
    async def get_module(self, module_id: str) -> Module | None:
        """Get a module by id."""

    @abstractmethod
    async def get_chains_by_module(self, module_id: str) -> list[Chain]:
        """Get all chains belonging to a module."""

    @abstractmethod
    async def get_probability_history(
        self, chain_id: str, step_index: int | None = None
    ) -> list[ProbabilityRecord]:
        """Get probability records for a chain, optionally filtered by step_index."""

    @abstractmethod
    async def get_belief_history(self, knowledge_id: str) -> list[BeliefSnapshot]:
        """Get belief snapshots for a knowledge item, ordered by computed_at."""

    @abstractmethod
    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]:
        """Get resources attached to a target entity."""

    # ── Search ──

    @abstractmethod
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredKnowledge]:
        """Full-text BM25 search over knowledge content."""

    # ── BP bulk load ──

    @abstractmethod
    async def list_knowledge(self) -> list[Knowledge]:
        """Load all knowledge items for BP factor graph construction."""

    @abstractmethod
    async def list_chains(self) -> list[Chain]:
        """Load all chains for BP factor graph construction."""

    # ── Factors ──

    @abstractmethod
    async def write_factors(self, factors: list[FactorNode]) -> None:
        """Write factor nodes from Graph IR."""

    @abstractmethod
    async def list_factors(self) -> list[FactorNode]:
        """Load all factors for BP factor graph construction."""

    @abstractmethod
    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]:
        """Get factors belonging to a specific package."""

    # ── Canonical bindings ──

    @abstractmethod
    async def write_canonical_bindings(self, bindings: list[CanonicalBinding]) -> None: ...

    @abstractmethod
    async def get_canonical_bindings(
        self, package: str, version: str
    ) -> list[CanonicalBinding]: ...

    # ── Global canonical nodes ──

    @abstractmethod
    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None: ...

    @abstractmethod
    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None: ...

    # ── Global inference state ──

    @abstractmethod
    async def update_inference_state(self, state: GlobalInferenceState) -> None: ...

    @abstractmethod
    async def get_inference_state(self) -> GlobalInferenceState | None: ...

    # ── Submission artifacts ──

    @abstractmethod
    async def write_submission_artifact(self, artifact: PackageSubmissionArtifact) -> None: ...

    @abstractmethod
    async def get_submission_artifact(
        self, package: str, commit_hash: str
    ) -> PackageSubmissionArtifact | None: ...
