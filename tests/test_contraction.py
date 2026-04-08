"""Tests for gaia.bp.contraction (tensor-based CPT computation)."""

from __future__ import annotations

import numpy as np
import pytest

from gaia.bp.contraction import (
    contract_to_cpt,
    cpt_tensor_to_list,
    factor_to_tensor,
    strategy_cpt,
)
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS
