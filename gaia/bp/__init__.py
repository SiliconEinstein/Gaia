"""BP engine — placeholder, re-exports from libs.inference until migration."""

from libs.inference.factor_graph import CROMWELL_EPS, FactorGraph
from libs.inference.bp import BeliefPropagation, BPDiagnostics

__all__ = ["FactorGraph", "CROMWELL_EPS", "BeliefPropagation", "BPDiagnostics"]
