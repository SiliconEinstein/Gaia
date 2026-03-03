# Plan 1: Review Pipeline Operator Layer

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the review pipeline framework and all operators (embedding, NN search, CC/CP join, verify, refine, BP) as independent, testable modules.

**Architecture:** A `Pipeline` orchestrator executes a chain of `Operator` instances, passing a shared `PipelineContext` between them. Each operator reads from and writes to the context. `ParallelStep` runs multiple operators concurrently. LLM-dependent operators (join, verify, refine) use a pluggable interface with stubs for Phase 1.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, existing inference_engine/bp.py, existing search_engine

---

### Task 1: PipelineContext Data Model

**Files:**
- Create: `services/review_pipeline/__init__.py`
- Create: `services/review_pipeline/context.py`
- Test: `tests/services/test_review_pipeline/__init__.py`
- Test: `tests/services/test_review_pipeline/test_context.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_context.py
from services.review_pipeline.context import PipelineContext, NewNodeInfo, JoinTree


def test_context_init_from_add_edge_ops():
    """Context extracts new node info from add_edge operations."""
    from libs.models import CommitRequest, AddEdgeOp, NewNode, NodeRef

    request = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise A"), NodeRef(node_id=100)],
                head=[NewNode(content="conclusion B")],
                type="paper-extract",
                reasoning=[{"title": "step1", "content": "because"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(request)
    assert len(ctx.new_nodes) == 2
    assert ctx.new_nodes[0].content == "premise A"
    assert ctx.new_nodes[0].op_index == 0
    assert ctx.new_nodes[0].position == "tail[0]"
    assert ctx.new_nodes[1].content == "conclusion B"
    assert ctx.new_nodes[1].position == "head[0]"
    assert ctx.cancelled is False


def test_context_init_from_modify_ops():
    """Context with only modify ops has no new nodes."""
    from libs.models import CommitRequest, ModifyNodeOp

    request = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    ctx = PipelineContext.from_commit_request(request)
    assert len(ctx.new_nodes) == 0
    assert ctx.affected_node_ids == [1]


def test_join_tree_model():
    tree = JoinTree(
        source_node_index=0,
        target_node_id=251,
        relation="partial_overlap",
        verified=False,
    )
    assert tree.source_node_index == 0
    assert tree.verified is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_context.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/__init__.py
"""Review pipeline — async operator-based review for commits."""

# services/review_pipeline/context.py
"""PipelineContext — shared state passed between pipeline operators."""

from __future__ import annotations

from pydantic import BaseModel

from libs.models import (
    AddEdgeOp,
    CommitRequest,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
)


class NewNodeInfo(BaseModel):
    """Metadata about a new node extracted from a commit operation."""
    content: str
    keywords: list[str] = []
    extra: dict = {}
    op_index: int
    position: str  # e.g. "tail[0]", "head[1]"


class JoinTree(BaseModel):
    """A discovered relationship between a new node and an existing node."""
    source_node_index: int  # index into PipelineContext.new_nodes
    target_node_id: int
    relation: str  # "equivalent", "partial_overlap", "subsumes", "subsumed_by"
    verified: bool = False
    reasoning: str = ""


class PipelineContext:
    """Shared mutable state flowing through the review pipeline."""

    def __init__(self) -> None:
        self.request: CommitRequest | None = None
        self.new_nodes: list[NewNodeInfo] = []
        self.affected_node_ids: list[int] = []
        self.embeddings: dict[int, list[float]] = {}  # new_node index -> vector
        self.nn_results: dict[int, list[tuple[int, float]]] = {}  # index -> [(node_id, sim)]
        self.cc_join_trees: list[JoinTree] = []
        self.cp_join_trees: list[JoinTree] = []
        self.verified_trees: list[JoinTree] = []
        self.bp_results: dict[int, float] = {}  # node_id -> belief
        self.cancelled: bool = False
        self.step_results: dict[str, dict] = {}  # step_name -> metadata

    @classmethod
    def from_commit_request(cls, request: CommitRequest) -> PipelineContext:
        ctx = cls()
        ctx.request = request
        for op_idx, op in enumerate(request.operations):
            if isinstance(op, AddEdgeOp):
                for i, item in enumerate(op.tail):
                    if isinstance(item, NewNode):
                        ctx.new_nodes.append(
                            NewNodeInfo(
                                content=item.content if isinstance(item.content, str) else str(item.content),
                                keywords=item.keywords,
                                extra=item.extra,
                                op_index=op_idx,
                                position=f"tail[{i}]",
                            )
                        )
                for i, item in enumerate(op.head):
                    if isinstance(item, NewNode):
                        ctx.new_nodes.append(
                            NewNodeInfo(
                                content=item.content if isinstance(item.content, str) else str(item.content),
                                keywords=item.keywords,
                                extra=item.extra,
                                op_index=op_idx,
                                position=f"head[{i}]",
                            )
                        )
            elif isinstance(op, ModifyNodeOp):
                ctx.affected_node_ids.append(op.node_id)
            elif isinstance(op, ModifyEdgeOp):
                ctx.affected_node_ids.append(op.edge_id)
        return ctx
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/ tests/services/test_review_pipeline/
git commit -m "feat: add PipelineContext data model for review pipeline"
```

---

### Task 2: Pipeline Framework (Operator ABC, Pipeline, ParallelStep)

**Files:**
- Create: `services/review_pipeline/base.py`
- Test: `tests/services/test_review_pipeline/test_base.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_base.py
import pytest
from services.review_pipeline.base import Operator, Pipeline, ParallelStep
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, ModifyNodeOp


class IncrementOperator(Operator):
    """Test operator that appends its name to step_results."""
    def __init__(self, name: str):
        self.name = name

    async def execute(self, context: PipelineContext) -> PipelineContext:
        context.step_results[self.name] = {"done": True}
        return context


class FailingOperator(Operator):
    async def execute(self, context: PipelineContext) -> PipelineContext:
        raise ValueError("operator failed")


@pytest.fixture
def empty_context():
    req = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    return PipelineContext.from_commit_request(req)


async def test_pipeline_sequential(empty_context):
    pipeline = Pipeline(steps=[IncrementOperator("a"), IncrementOperator("b")])
    result = await pipeline.execute(empty_context)
    assert "a" in result.step_results
    assert "b" in result.step_results


async def test_pipeline_parallel_step(empty_context):
    pipeline = Pipeline(steps=[
        ParallelStep(IncrementOperator("x"), IncrementOperator("y")),
    ])
    result = await pipeline.execute(empty_context)
    assert "x" in result.step_results
    assert "y" in result.step_results


async def test_pipeline_skips_after_cancel(empty_context):
    empty_context.cancelled = True
    pipeline = Pipeline(steps=[IncrementOperator("a")])
    result = await pipeline.execute(empty_context)
    assert "a" not in result.step_results


async def test_pipeline_cancel_propagates(empty_context):
    pipeline = Pipeline(steps=[IncrementOperator("a"), IncrementOperator("b")])
    await pipeline.cancel()
    result = await pipeline.execute(empty_context)
    assert "a" not in result.step_results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_base.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/base.py
"""Pipeline framework — Operator ABC, Pipeline orchestrator, ParallelStep."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from services.review_pipeline.context import PipelineContext


class Operator(ABC):
    """Base class for all pipeline operators."""

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute operator logic, reading from and writing to context."""
        ...

    async def cancel(self) -> None:
        """Cancel a running operation. Override if cleanup is needed."""
        pass


class ParallelStep:
    """Run multiple operators concurrently on the same context."""

    def __init__(self, *operators: Operator) -> None:
        self._operators = list(operators)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if context.cancelled:
            return context
        await asyncio.gather(*(op.execute(context) for op in self._operators))
        return context

    async def cancel(self) -> None:
        await asyncio.gather(*(op.cancel() for op in self._operators))


class Pipeline:
    """Sequential pipeline that passes context through each step."""

    def __init__(self, steps: list[Operator | ParallelStep]) -> None:
        self._steps = steps
        self._cancelled = False

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if self._cancelled:
            context.cancelled = True
        for step in self._steps:
            if context.cancelled:
                break
            context = await step.execute(context)
        return context

    async def cancel(self) -> None:
        self._cancelled = True
        for step in self._steps:
            await step.cancel()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/base.py tests/services/test_review_pipeline/test_base.py
git commit -m "feat: add Pipeline framework with Operator ABC and ParallelStep"
```

---

### Task 3: EmbeddingOperator

**Files:**
- Create: `services/review_pipeline/operators/__init__.py`
- Create: `services/review_pipeline/operators/embedding.py`
- Test: `tests/services/test_review_pipeline/test_embedding_op.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_embedding_op.py
import pytest
from services.review_pipeline.operators.embedding import (
    EmbeddingModel,
    EmbeddingOperator,
    StubEmbeddingModel,
)
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode, NodeRef


@pytest.fixture
def context_with_new_nodes():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise A")],
                head=[NewNode(content="conclusion B")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    return PipelineContext.from_commit_request(req)


async def test_stub_embedding_model():
    model = StubEmbeddingModel(dim=128)
    vecs = await model.embed(["hello", "world"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 128
    assert all(isinstance(v, float) for v in vecs[0])


async def test_embedding_operator_generates_vectors(context_with_new_nodes):
    op = EmbeddingOperator(model=StubEmbeddingModel(dim=128))
    result = await op.execute(context_with_new_nodes)
    assert 0 in result.embeddings
    assert 1 in result.embeddings
    assert len(result.embeddings[0]) == 128


async def test_embedding_operator_skips_if_no_new_nodes():
    from libs.models import ModifyNodeOp
    req = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    ctx = PipelineContext.from_commit_request(req)
    op = EmbeddingOperator(model=StubEmbeddingModel(dim=128))
    result = await op.execute(ctx)
    assert len(result.embeddings) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_embedding_op.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/operators/__init__.py
"""Review pipeline operators."""

# services/review_pipeline/operators/embedding.py
"""EmbeddingOperator — generate embeddings for new nodes."""

from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod

from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext


class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        ...


class StubEmbeddingModel(EmbeddingModel):
    """Deterministic stub: hashes text to produce reproducible vectors."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            # Repeat digest bytes to fill dim floats
            raw = digest * ((self._dim * 4 // len(digest)) + 1)
            floats = list(struct.unpack(f"<{self._dim}f", raw[: self._dim * 4]))
            # Normalize to reasonable range
            mag = max(abs(f) for f in floats) or 1.0
            results.append([f / mag for f in floats])
        return results


class EmbeddingOperator(Operator):
    """Generate embeddings for all new nodes in the context."""

    def __init__(self, model: EmbeddingModel) -> None:
        self._model = model

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.new_nodes:
            return context
        texts = [node.content for node in context.new_nodes]
        vectors = await self._model.embed(texts)
        for i, vec in enumerate(vectors):
            context.embeddings[i] = vec
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_embedding_op.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/operators/ tests/services/test_review_pipeline/test_embedding_op.py
git commit -m "feat: add EmbeddingOperator with pluggable model interface"
```

---

### Task 4: NNSearchOperator

**Files:**
- Create: `services/review_pipeline/operators/nn_search.py`
- Test: `tests/services/test_review_pipeline/test_nn_search_op.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_nn_search_op.py
import pytest
from unittest.mock import AsyncMock
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode
from libs.storage.vector_search.base import VectorSearchClient


@pytest.fixture
def context_with_embeddings():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NewNode(content="conclusion")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.embeddings = {0: [0.1] * 128, 1: [0.2] * 128}
    return ctx


async def test_nn_search_returns_neighbors(context_with_embeddings):
    mock_client = AsyncMock(spec=VectorSearchClient)
    mock_client.search.return_value = [(100, 0.1), (200, 0.2), (300, 0.3)]

    op = NNSearchOperator(vector_client=mock_client, k=20)
    result = await op.execute(context_with_embeddings)

    assert 0 in result.nn_results
    assert 1 in result.nn_results
    assert len(result.nn_results[0]) == 3
    assert result.nn_results[0][0] == (100, 0.1)
    assert mock_client.search.call_count == 2


async def test_nn_search_skips_if_no_embeddings():
    from libs.models import ModifyNodeOp
    req = CommitRequest(
        message="t",
        operations=[ModifyNodeOp(node_id=1, changes={"x": 1})],
    )
    ctx = PipelineContext.from_commit_request(req)
    mock_client = AsyncMock(spec=VectorSearchClient)
    op = NNSearchOperator(vector_client=mock_client, k=20)
    result = await op.execute(ctx)
    assert len(result.nn_results) == 0
    mock_client.search.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_nn_search_op.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/operators/nn_search.py
"""NNSearchOperator — find nearest neighbors for each new node embedding."""

from __future__ import annotations

from libs.storage.vector_search.base import VectorSearchClient
from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext


class NNSearchOperator(Operator):
    """Search k nearest neighbors for each new node's embedding."""

    def __init__(self, vector_client: VectorSearchClient, k: int = 20) -> None:
        self._client = vector_client
        self._k = k

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.embeddings:
            return context
        for idx, embedding in context.embeddings.items():
            results = await self._client.search(embedding, k=self._k)
            context.nn_results[idx] = results
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_nn_search_op.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/operators/nn_search.py tests/services/test_review_pipeline/test_nn_search_op.py
git commit -m "feat: add NNSearchOperator wrapping vector search client"
```

---

### Task 5: CC/CP Join Operators (stub)

**Files:**
- Create: `services/review_pipeline/operators/join.py`
- Test: `tests/services/test_review_pipeline/test_join_op.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_join_op.py
import pytest
from services.review_pipeline.operators.join import (
    CCJoinOperator,
    CPJoinOperator,
    JoinLLM,
    StubJoinLLM,
)
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode


@pytest.fixture
def context_with_nn():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NewNode(content="conclusion")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "because"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.embeddings = {0: [0.1] * 128, 1: [0.2] * 128}
    ctx.nn_results = {
        0: [(100, 0.05), (200, 0.1)],
        1: [(300, 0.02), (400, 0.15)],
    }
    return ctx


async def test_stub_join_llm():
    llm = StubJoinLLM()
    trees = await llm.find_joins("new content", [(100, "existing content")])
    assert isinstance(trees, list)


async def test_cc_join_produces_trees(context_with_nn):
    op = CCJoinOperator(join_llm=StubJoinLLM())
    result = await op.execute(context_with_nn)
    assert isinstance(result.cc_join_trees, list)


async def test_cp_join_produces_trees(context_with_nn):
    op = CPJoinOperator(join_llm=StubJoinLLM())
    result = await op.execute(context_with_nn)
    assert isinstance(result.cp_join_trees, list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_join_op.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/operators/join.py
"""CC/CP Join Operators — discover relationships between new and existing nodes.

Phase 1: StubJoinLLM returns empty results. Future phases plug in real LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.review_pipeline.base import Operator
from services.review_pipeline.context import JoinTree, PipelineContext


class JoinLLM(ABC):
    """Abstract interface for LLM-based join discovery."""

    @abstractmethod
    async def find_joins(
        self,
        new_content: str,
        candidates: list[tuple[int, str]],
    ) -> list[JoinTree]:
        """Find relationships between new content and candidate nodes.

        Args:
            new_content: Content of the new node.
            candidates: List of (node_id, content) pairs to compare against.

        Returns:
            List of discovered join trees.
        """
        ...


class StubJoinLLM(JoinLLM):
    """Always returns empty results. For testing and Phase 1."""

    async def find_joins(
        self,
        new_content: str,
        candidates: list[tuple[int, str]],
    ) -> list[JoinTree]:
        return []


class CCJoinOperator(Operator):
    """Discover conclusion-conclusion relationships."""

    def __init__(self, join_llm: JoinLLM | None = None) -> None:
        self._llm = join_llm or StubJoinLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.nn_results:
            return context
        # In future: load candidate node contents, call LLM to find CC joins
        # Phase 1: stub returns empty
        for idx in context.nn_results:
            candidates = [(nid, "") for nid, _ in context.nn_results[idx]]
            trees = await self._llm.find_joins(
                context.new_nodes[idx].content if idx < len(context.new_nodes) else "",
                candidates,
            )
            for tree in trees:
                tree.source_node_index = idx
            context.cc_join_trees.extend(trees)
        return context


class CPJoinOperator(Operator):
    """Discover conclusion-premise relationships."""

    def __init__(self, join_llm: JoinLLM | None = None) -> None:
        self._llm = join_llm or StubJoinLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not context.nn_results:
            return context
        for idx in context.nn_results:
            candidates = [(nid, "") for nid, _ in context.nn_results[idx]]
            trees = await self._llm.find_joins(
                context.new_nodes[idx].content if idx < len(context.new_nodes) else "",
                candidates,
            )
            for tree in trees:
                tree.source_node_index = idx
            context.cp_join_trees.extend(trees)
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_join_op.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/operators/join.py tests/services/test_review_pipeline/test_join_op.py
git commit -m "feat: add CC/CP JoinOperators with pluggable LLM interface"
```

---

### Task 6: Verify + Refine Operators (stub)

**Files:**
- Create: `services/review_pipeline/operators/verify.py`
- Test: `tests/services/test_review_pipeline/test_verify_op.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_verify_op.py
import pytest
from services.review_pipeline.operators.verify import (
    JoinTreeVerifyOperator,
    RefineOperator,
    VerifyAgainOperator,
    VerifyLLM,
    StubVerifyLLM,
)
from services.review_pipeline.context import JoinTree, PipelineContext
from libs.models import CommitRequest, ModifyNodeOp


@pytest.fixture
def context_with_trees():
    req = CommitRequest(
        message="t",
        operations=[ModifyNodeOp(node_id=1, changes={"x": 1})],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.cc_join_trees = [
        JoinTree(source_node_index=0, target_node_id=100, relation="partial_overlap"),
        JoinTree(source_node_index=0, target_node_id=200, relation="equivalent"),
    ]
    ctx.cp_join_trees = [
        JoinTree(source_node_index=1, target_node_id=300, relation="subsumes"),
    ]
    return ctx


async def test_verify_marks_trees(context_with_trees):
    op = JoinTreeVerifyOperator(verify_llm=StubVerifyLLM())
    result = await op.execute(context_with_trees)
    # Stub auto-verifies all trees
    all_trees = result.cc_join_trees + result.cp_join_trees
    assert all(t.verified for t in all_trees)


async def test_refine_passes_through(context_with_trees):
    op = RefineOperator()
    result = await op.execute(context_with_trees)
    assert len(result.cc_join_trees) == 2


async def test_verify_again_filters(context_with_trees):
    # Mark one as verified, one not
    context_with_trees.cc_join_trees[0].verified = True
    context_with_trees.cc_join_trees[1].verified = False
    context_with_trees.cp_join_trees[0].verified = True

    op = VerifyAgainOperator(verify_llm=StubVerifyLLM())
    result = await op.execute(context_with_trees)
    assert len(result.verified_trees) == 3  # stub verifies all
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_verify_op.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/operators/verify.py
"""Verify and Refine operators for join trees.

Phase 1: StubVerifyLLM auto-verifies all trees.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.review_pipeline.base import Operator
from services.review_pipeline.context import JoinTree, PipelineContext


class VerifyLLM(ABC):
    @abstractmethod
    async def verify(self, trees: list[JoinTree]) -> list[JoinTree]:
        """Verify join trees, setting verified=True/False on each."""
        ...


class StubVerifyLLM(VerifyLLM):
    """Auto-verifies all trees. For testing and Phase 1."""

    async def verify(self, trees: list[JoinTree]) -> list[JoinTree]:
        for tree in trees:
            tree.verified = True
        return trees


class JoinTreeVerifyOperator(Operator):
    """First-pass verification of discovered join trees."""

    def __init__(self, verify_llm: VerifyLLM | None = None) -> None:
        self._llm = verify_llm or StubVerifyLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        all_trees = context.cc_join_trees + context.cp_join_trees
        if all_trees:
            await self._llm.verify(all_trees)
        return context


class RefineOperator(Operator):
    """Refine join trees — Phase 1: pass-through."""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        return context


class VerifyAgainOperator(Operator):
    """Second verification pass. Collects all verified trees into verified_trees."""

    def __init__(self, verify_llm: VerifyLLM | None = None) -> None:
        self._llm = verify_llm or StubVerifyLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        all_trees = context.cc_join_trees + context.cp_join_trees
        if all_trees:
            await self._llm.verify(all_trees)
        context.verified_trees = [t for t in all_trees if t.verified]
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_verify_op.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/operators/verify.py tests/services/test_review_pipeline/test_verify_op.py
git commit -m "feat: add Verify/Refine operators with pluggable LLM interface"
```

---

### Task 7: BPOperator

**Files:**
- Create: `services/review_pipeline/operators/bp.py`
- Test: `tests/services/test_review_pipeline/test_bp_op.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_bp_op.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.context import PipelineContext
from libs.models import CommitRequest, AddEdgeOp, NewNode, Node, HyperEdge


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(return_value=({1, 2, 3}, {10}))
    storage.graph.get_hyperedge = AsyncMock(
        return_value=HyperEdge(id=10, type="paper-extract", tail=[1, 2], head=[3])
    )
    storage.lance = MagicMock()
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="a", prior=0.9),
            Node(id=2, type="paper-extract", content="b", prior=0.8),
            Node(id=3, type="paper-extract", content="c", prior=0.5),
        ]
    )
    return storage


@pytest.fixture
def context_with_affected_nodes():
    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="p")],
                head=[NewNode(content="c")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "x"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.affected_node_ids = [1, 2, 3]
    return ctx


async def test_bp_operator_computes_beliefs(mock_storage, context_with_affected_nodes):
    op = BPOperator(storage=mock_storage)
    result = await op.execute(context_with_affected_nodes)
    assert len(result.bp_results) > 0
    assert all(0 <= v <= 1 for v in result.bp_results.values())


async def test_bp_operator_skips_without_graph():
    storage = MagicMock()
    storage.graph = None
    req = CommitRequest(
        message="t",
        operations=[],
    )
    ctx = PipelineContext.from_commit_request(req)
    ctx.affected_node_ids = [1]
    op = BPOperator(storage=storage)
    result = await op.execute(ctx)
    assert len(result.bp_results) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_bp_op.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/operators/bp.py
"""BPOperator — run belief propagation on affected subgraph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph
from services.review_pipeline.base import Operator
from services.review_pipeline.context import PipelineContext

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager


class BPOperator(Operator):
    """Run local belief propagation on the subgraph around affected nodes."""

    def __init__(self, storage: StorageManager, hops: int = 3) -> None:
        self._storage = storage
        self._hops = hops
        self._bp = BeliefPropagation()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if not self._storage.graph:
            return context

        seed_ids = context.affected_node_ids
        if not seed_ids:
            return context

        node_ids, edge_ids = await self._storage.graph.get_subgraph(
            seed_ids, hops=self._hops
        )
        if not edge_ids:
            return context

        edges = []
        for eid in edge_ids:
            edge = await self._storage.graph.get_hyperedge(eid)
            if edge:
                edges.append(edge)

        nodes = await self._storage.lance.load_nodes_bulk(list(node_ids))
        fg = FactorGraph.from_subgraph(nodes, edges)
        beliefs = self._bp.run(fg)
        context.bp_results = beliefs
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_bp_op.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/review_pipeline/operators/bp.py tests/services/test_review_pipeline/test_bp_op.py
git commit -m "feat: add BPOperator wrapping belief propagation engine"
```

---

### Task 8: Full Pipeline Assembly + Integration Test

**Files:**
- Create: `services/review_pipeline/pipeline.py`
- Test: `tests/services/test_review_pipeline/test_pipeline_integration.py`

**Step 1: Write the failing test**

```python
# tests/services/test_review_pipeline/test_pipeline_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.review_pipeline.pipeline import build_review_pipeline, ReviewPipelineConfig
from services.review_pipeline.context import PipelineContext
from services.review_pipeline.operators.embedding import StubEmbeddingModel
from services.review_pipeline.operators.join import StubJoinLLM
from services.review_pipeline.operators.verify import StubVerifyLLM
from libs.models import (
    CommitRequest, AddEdgeOp, ModifyNodeOp, NewNode, Node, HyperEdge,
)


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(return_value=({1, 2}, {10}))
    storage.graph.get_hyperedge = AsyncMock(
        return_value=HyperEdge(id=10, type="paper-extract", tail=[1], head=[2])
    )
    storage.lance = MagicMock()
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="a", prior=0.9),
            Node(id=2, type="paper-extract", content="b", prior=0.8),
        ]
    )
    storage.vector = AsyncMock()
    storage.vector.search = AsyncMock(return_value=[(1, 0.1), (2, 0.2)])
    return storage


async def test_full_pipeline_add_edge(mock_storage):
    """Full pipeline runs all steps for add_edge operations."""
    config = ReviewPipelineConfig(
        embedding_model=StubEmbeddingModel(dim=128),
        join_llm=StubJoinLLM(),
        verify_llm=StubVerifyLLM(),
    )
    pipeline = build_review_pipeline(config, mock_storage)

    req = CommitRequest(
        message="test",
        operations=[
            AddEdgeOp(
                tail=[NewNode(content="premise")],
                head=[NewNode(content="conclusion")],
                type="paper-extract",
                reasoning=[{"title": "r", "content": "x"}],
            )
        ],
    )
    ctx = PipelineContext.from_commit_request(req)
    result = await pipeline.execute(ctx)

    assert len(result.embeddings) == 2
    assert len(result.nn_results) == 2
    assert not result.cancelled


async def test_pipeline_modify_only_runs_bp(mock_storage):
    """Modify-only commits skip embedding/join, only run BP."""
    config = ReviewPipelineConfig(
        embedding_model=StubEmbeddingModel(dim=128),
        join_llm=StubJoinLLM(),
        verify_llm=StubVerifyLLM(),
    )
    pipeline = build_review_pipeline(config, mock_storage)

    req = CommitRequest(
        message="test",
        operations=[ModifyNodeOp(node_id=1, changes={"status": "deleted"})],
    )
    ctx = PipelineContext.from_commit_request(req)
    result = await pipeline.execute(ctx)

    assert len(result.embeddings) == 0
    assert len(result.nn_results) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_review_pipeline/test_pipeline_integration.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/review_pipeline/pipeline.py
"""Build configured review pipelines from components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from services.review_pipeline.base import Operator, ParallelStep, Pipeline
from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.operators.embedding import EmbeddingModel, EmbeddingOperator
from services.review_pipeline.operators.join import CCJoinOperator, CPJoinOperator, JoinLLM
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.operators.verify import (
    JoinTreeVerifyOperator,
    RefineOperator,
    VerifyAgainOperator,
    VerifyLLM,
)

if TYPE_CHECKING:
    from libs.storage.manager import StorageManager


@dataclass
class ReviewPipelineConfig:
    embedding_model: EmbeddingModel
    join_llm: JoinLLM | None = None
    verify_llm: VerifyLLM | None = None
    nn_k: int = 20
    bp_hops: int = 3


def build_review_pipeline(
    config: ReviewPipelineConfig,
    storage: StorageManager,
) -> Pipeline:
    """Build the full review pipeline.

    The pipeline is: Embedding → NN Search → CC/CP Join (parallel) →
    Verify → Refine → Verify Again → BP.

    Operators that find no input data (e.g. no new_nodes) are no-ops.
    """
    return Pipeline(steps=[
        EmbeddingOperator(model=config.embedding_model),
        NNSearchOperator(vector_client=storage.vector, k=config.nn_k),
        ParallelStep(
            CCJoinOperator(join_llm=config.join_llm),
            CPJoinOperator(join_llm=config.join_llm),
        ),
        JoinTreeVerifyOperator(verify_llm=config.verify_llm),
        RefineOperator(),
        VerifyAgainOperator(verify_llm=config.verify_llm),
        BPOperator(storage=storage, hops=config.bp_hops),
    ])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_review_pipeline/test_pipeline_integration.py -v`
Expected: PASS

**Step 5: Run all pipeline tests**

Run: `pytest tests/services/test_review_pipeline/ -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add services/review_pipeline/pipeline.py tests/services/test_review_pipeline/test_pipeline_integration.py
git commit -m "feat: add review pipeline assembly with full operator chain"
```
