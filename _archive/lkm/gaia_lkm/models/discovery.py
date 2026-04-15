"""Discovery data models for M6 Semantic Discovery.

These are pure value types (dataclasses) — output types from the clustering
pipeline, not storage models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SemanticCluster:
    """A group of semantically similar global variable nodes.

    Attributes:
        cluster_id: Unique identifier for this cluster.
        node_type: Knowledge type — one of "claim", "question", "setting", "action".
        gcn_ids: List of global canonical node IDs in this cluster.
        centroid_gcn_id: The GCN ID closest to the cluster centroid.
        avg_similarity: Mean pairwise cosine similarity within the cluster.
        min_similarity: Minimum pairwise cosine similarity within the cluster.
    """

    cluster_id: str
    node_type: str  # "claim" | "question" | "setting" | "action"
    gcn_ids: list[str]
    centroid_gcn_id: str
    avg_similarity: float
    min_similarity: float


@dataclass
class ClusteringStats:
    """Summary statistics from a clustering run.

    Attributes:
        total_variables_scanned: Number of global variable nodes examined.
        total_embeddings_computed: Number of embedding vectors fetched/computed.
        total_clusters: Number of clusters produced.
        cluster_size_distribution: Mapping of cluster size → count of clusters that size.
        elapsed_seconds: Wall-clock time for the full clustering run.
    """

    total_variables_scanned: int
    total_embeddings_computed: int
    total_clusters: int
    cluster_size_distribution: dict[int, int]
    elapsed_seconds: float


@dataclass
class ClusteringResult:
    """Full output of a semantic clustering run.

    Attributes:
        clusters: All SemanticCluster objects produced.
        stats: Aggregate statistics for the run.
        timestamp: UTC datetime when the run completed.
    """

    clusters: list[SemanticCluster]
    stats: ClusteringStats
    timestamp: datetime


@dataclass
class DiscoveryConfig:
    """Configuration for the semantic discovery pipeline.

    Attributes:
        embedding_api_url: HTTP endpoint for the embedding API.
        embedding_provider: Provider tag passed to the embedding API.
        embedding_dim: Dimensionality of embedding vectors.
        embedding_concurrency: Target RPS for embedding API (token bucket rate limiter).
        embedding_max_retries: Max retry attempts per embedding request.
        embedding_http_timeout: HTTP timeout in seconds for embedding calls.
        similarity_threshold: Minimum cosine similarity to form a cluster edge.
        faiss_k: Number of nearest neighbours to retrieve per FAISS query.
        max_cluster_size: Discard clusters larger than this (likely noise).
        exclude_same_factor: Skip pairs that share a factor node.
        faiss_index_type: FAISS index flavour ("flat" or "ivf").
    """

    # Embedding API
    embedding_api_url: str = "https://openapi.dp.tech/openapi/v1/test/vectorize"
    embedding_provider: str = "dashscope"
    embedding_dim: int = 512
    embedding_concurrency: int = 15  # worker count; each sleeps 1.5s → ~10 RPS (API limit 50)
    embedding_max_retries: int = 3
    embedding_http_timeout: int = 30
    # Clustering
    similarity_threshold: float = 0.85
    faiss_k: int = 100
    max_cluster_size: int = 20
    exclude_same_factor: bool = True
    faiss_index_type: str = "flat"
