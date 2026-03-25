"""LocalParameterization — transient container, not part of Graph IR contract.

This is a temporary parameter container from CLI build/review output.
It is consumed by canonicalize to produce global PriorRecord/FactorParamRecord,
then discarded. It is NOT persisted.
"""

from pydantic import BaseModel


class LocalParameterization(BaseModel):
    """Temporary parameter container from CLI build/review. Not persisted."""

    graph_hash: str  # binds to a specific LocalCanonicalGraph
    node_priors: dict[str, float] = {}  # lcn_id → prior
    factor_parameters: dict[str, float] = {}  # factor_id → conditional_probability
