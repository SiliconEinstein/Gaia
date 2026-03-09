from .engine import InferenceEngine

# Re-export from libs.inference so existing `from services.inference_engine.bp`
# and `from services.inference_engine.factor_graph` imports keep working during
# the transition period.
from libs.inference.bp import BeliefPropagation, InconsistentGraphError  # noqa: F401
from libs.inference.factor_graph import FactorGraph  # noqa: F401

__all__ = ["InferenceEngine", "BeliefPropagation", "FactorGraph", "InconsistentGraphError"]
