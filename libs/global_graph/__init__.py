"""Global graph: cross-package canonicalization and global inference."""

from .canonicalize import canonicalize_package
from .models import (
    CanonicalBinding,
    CanonicalizationResult,
    GlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
)
from .serialize import load_global_graph, save_global_graph
from .similarity import compute_similarity_tfidf, cosine_similarity_vectors, find_best_match

__all__ = [
    "CanonicalBinding",
    "CanonicalizationResult",
    "GlobalCanonicalNode",
    "GlobalGraph",
    "GlobalInferenceState",
    "LocalCanonicalRef",
    "PackageRef",
    "canonicalize_package",
    "compute_similarity_tfidf",
    "cosine_similarity_vectors",
    "find_best_match",
    "load_global_graph",
    "save_global_graph",
]
