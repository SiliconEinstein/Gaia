"""FAISS-based semantic clustering with Union-Find.

Algorithm:
1. Normalize embeddings → FAISS IndexFlatIP (inner product = cosine similarity)
2. k-NN search (configurable k, default 100)
3. Union-Find merge: pairs with similarity > threshold are merged
4. Extract connected components → clusters
5. Enforce max_cluster_size by splitting large clusters
6. Compute centroid (closest member to mean vector) and pairwise similarity stats
"""

from __future__ import annotations

import uuid

import faiss
import numpy as np

from gaia.lkm.models.discovery import DiscoveryConfig, SemanticCluster


class _UnionFind:
    """Union-Find with path compression and union by rank."""

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: int, y: int) -> None:
        """Merge the sets containing x and y by rank."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1

    def components(self) -> dict[int, list[int]]:
        """Return {root: [member_indices]} for all components."""
        groups: dict[int, list[int]] = {}
        for i in range(len(self._parent)):
            root = self.find(i)
            groups.setdefault(root, []).append(i)
        return groups


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row in-place (returns a copy)."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (matrix / norms).astype(np.float32)


def _cosine_similarity_matrix(normed: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity for a batch of L2-normalized rows."""
    return (normed @ normed.T).astype(np.float64)


def _compute_cluster_stats(
    normed_rows: np.ndarray,
    gcn_ids: list[str],
) -> tuple[str, float, float]:
    """Return (centroid_gcn_id, avg_similarity, min_similarity) for a cluster.

    Args:
        normed_rows: L2-normalized embedding matrix for cluster members, shape (k, dim).
        gcn_ids: Ordered list of GCN IDs matching rows.

    Returns:
        Tuple of (centroid_gcn_id, avg_similarity, min_similarity).
    """
    k = len(gcn_ids)
    if k == 1:
        return gcn_ids[0], 1.0, 1.0

    # Centroid: mean of normalized rows, then find closest member
    mean_vec = normed_rows.mean(axis=0).astype(np.float32)
    mean_norm = np.linalg.norm(mean_vec)
    if mean_norm > 0:
        mean_vec = mean_vec / mean_norm
    sims_to_mean = (normed_rows @ mean_vec).astype(np.float64)
    centroid_idx = int(np.argmax(sims_to_mean))
    centroid_gcn_id = gcn_ids[centroid_idx]

    # Pairwise similarity (upper triangle only)
    sim_matrix = _cosine_similarity_matrix(normed_rows)
    upper_triangle = sim_matrix[np.triu_indices(k, k=1)]
    avg_similarity = float(upper_triangle.mean()) if len(upper_triangle) > 0 else 1.0
    min_similarity = float(upper_triangle.min()) if len(upper_triangle) > 0 else 1.0

    return centroid_gcn_id, avg_similarity, min_similarity


def _split_cluster(
    indices: list[int],
    max_size: int,
) -> list[list[int]]:
    """Split a list of indices into chunks of at most max_size.

    If the last chunk has only 1 element, merge it into the previous chunk
    (which may then exceed max_size by 1) to avoid silently dropping nodes.
    """
    chunks = []
    for start in range(0, len(indices), max_size):
        chunks.append(indices[start : start + max_size])
    # Merge lone remainder into previous chunk to avoid dropping it
    if len(chunks) >= 2 and len(chunks[-1]) == 1:
        chunks[-2].extend(chunks.pop())
    return chunks


def cluster_embeddings(
    gcn_ids: list[str],
    matrix: np.ndarray,  # (N, dim) float32
    config: DiscoveryConfig,
    factor_index: dict[str, set[str]] | None = None,  # {gcn_id: set(factor_ids)}
) -> list[SemanticCluster]:
    """Cluster embeddings using FAISS k-NN + Union-Find.

    Args:
        gcn_ids: Ordered list of global canonical node IDs, length N.
        matrix: Float32 embedding matrix of shape (N, dim).
        config: Discovery configuration (thresholds, k, max cluster size, etc.).
        factor_index: Optional mapping from gcn_id to its set of factor IDs.
            When config.exclude_same_factor is True, pairs sharing any factor
            are not merged.

    Returns:
        List of SemanticCluster objects (only clusters of size >= 2).
    """
    n = len(gcn_ids)
    if n == 0:
        return []

    # Step 1: L2-normalize
    normed = _l2_normalize(matrix.copy())

    # Step 2: Build FAISS IndexFlatIP and search k-NN
    dim = normed.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(normed)

    # Search k+1 because IndexFlatIP returns the query itself as the top hit
    k = min(config.faiss_k + 1, n)
    similarities, neighbor_indices = index.search(normed, k)
    # similarities shape: (N, k), neighbor_indices shape: (N, k)

    # Step 3: Union-Find merge
    uf = _UnionFind(n)

    for i in range(n):
        for j_idx in range(k):
            j = int(neighbor_indices[i, j_idx])
            if j == i:
                continue
            sim = float(similarities[i, j_idx])
            if sim <= config.similarity_threshold:
                # FAISS returns sorted descending, so remaining sims are lower
                break

            # Constraint: skip pairs sharing a factor
            if config.exclude_same_factor and factor_index is not None:
                fi = factor_index.get(gcn_ids[i], set())
                fj = factor_index.get(gcn_ids[j], set())
                if fi & fj:  # non-empty intersection
                    continue

            uf.union(i, j)

    # Step 4: Extract connected components
    components = uf.components()

    # Step 5: Enforce max_cluster_size by splitting
    raw_groups: list[list[int]] = []
    for members in components.values():
        if len(members) < 2:
            continue
        if len(members) <= config.max_cluster_size:
            raw_groups.append(members)
        else:
            raw_groups.extend(_split_cluster(members, config.max_cluster_size))

    # Step 6: Build SemanticCluster objects
    clusters: list[SemanticCluster] = []
    for group in raw_groups:
        if len(group) < 2:
            continue
        member_ids = [gcn_ids[i] for i in group]
        member_normed = normed[group]

        centroid_gcn_id, avg_sim, min_sim = _compute_cluster_stats(member_normed, member_ids)

        clusters.append(
            SemanticCluster(
                cluster_id=f"cl_{uuid.uuid4().hex[:12]}",
                node_type="",
                gcn_ids=member_ids,
                centroid_gcn_id=centroid_gcn_id,
                avg_similarity=avg_sim,
                min_similarity=min_sim,
            )
        )

    return clusters
