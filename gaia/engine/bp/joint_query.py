"""Joint distribution queries for Gaia factor-graph inference."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gaia.engine.bp.exact import exact_joint_over
from gaia.engine.bp.factor_graph import CROMWELL_EPS, FactorGraph
from gaia.engine.bp.junction_tree import JunctionTreeCalibration, calibrate_junction_tree
from gaia.engine.bp.mean_field import MeanFieldVI
from gaia.engine.bp.trw_bp import TRWBeliefPropagation

JointQueryMethod = Literal["exact", "junction_tree", "trw_bp", "mean_field"]
JointDistributionBasis = Literal[
    "exact_joint_distribution",
    "calibrated_clique_marginal",
    "approximate_joint_distribution",
    "variational_joint_distribution",
]

_NORMALIZATION_TOLERANCE = 1e-9
_EXACT_TOO_MANY_VARIABLES_MESSAGE = "Exact inference requires 2^n enumeration"


class JointQueryUnavailableError(RuntimeError):
    """Raised when a method cannot provide a requested joint distribution."""

    def __init__(
        self,
        method: JointQueryMethod,
        variables: Sequence[str],
        reason: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an unavailable joint-query error."""
        super().__init__(reason)
        self.method = method
        self.variables = list(variables)
        self.reason = reason
        self.diagnostics = diagnostics or {}


class JointDistribution(BaseModel):
    """A normalized joint table over a binary variable set."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    probabilities: list[float]
    method: JointQueryMethod
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_distribution(self) -> JointDistribution:
        expected = 1 << len(self.variables)
        if len(self.probabilities) != expected:
            raise ValueError(
                f"JointDistribution over {len(self.variables)} variables requires "
                f"{expected} probabilities, got {len(self.probabilities)}."
            )
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("JointDistribution variables must be unique.")
        if any(not isfinite(value) for value in self.probabilities):
            raise ValueError("JointDistribution probabilities must be finite.")
        if any(value < -_NORMALIZATION_TOLERANCE for value in self.probabilities):
            raise ValueError("JointDistribution probabilities must be non-negative.")
        total = sum(self.probabilities)
        if abs(total - 1.0) > _NORMALIZATION_TOLERANCE:
            raise ValueError(f"JointDistribution probabilities must sum to 1, got {total}.")
        self.probabilities = [
            0.0 if abs(value) < _NORMALIZATION_TOLERANCE else value
            for value in self.probabilities
        ]
        return self


class JointQueryUnavailable(BaseModel):
    """A method-specific joint query miss."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    method: JointQueryMethod
    reason: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    method: JointQueryMethod,
) -> JointDistribution:
    """Return a joint table over ``variables`` using one inference method."""
    requested = _normalized_variables(variables)
    _require_known_variables(graph, requested, method)

    if method == "exact":
        return _exact_joint_over(graph, requested)
    if method == "mean_field":
        return _mean_field_joint_over(graph, requested)
    if method == "junction_tree":
        return _junction_tree_joint_over(graph, requested)
    if method == "trw_bp":
        return _trw_bp_joint_over(graph, requested)

    raise ValueError(f"Unknown joint query method: {method!r}")


def compare_joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    methods: Sequence[JointQueryMethod] = ("exact", "junction_tree", "trw_bp", "mean_field"),
) -> list[JointDistribution | JointQueryUnavailable]:
    """Run several joint providers and collect unavailable methods explicitly."""
    requested = _normalized_variables(variables)
    results: list[JointDistribution | JointQueryUnavailable] = []
    for method in methods:
        try:
            results.append(joint_over(graph, requested, method=method))
        except JointQueryUnavailableError as error:
            results.append(
                JointQueryUnavailable(
                    variables=error.variables,
                    method=error.method,
                    reason=error.reason,
                    diagnostics=error.diagnostics,
                )
            )
    return results


def _normalized_variables(variables: Sequence[str]) -> list[str]:
    requested = list(variables)
    if not requested:
        raise ValueError("joint_over requires at least one variable.")
    if not all(isinstance(variable, str) and variable for variable in requested):
        raise ValueError("joint_over variables must be non-empty strings.")
    if len(set(requested)) != len(requested):
        raise ValueError("joint_over variables must be unique.")
    return requested


def _require_known_variables(
    graph: FactorGraph,
    variables: Sequence[str],
    method: JointQueryMethod,
) -> None:
    missing = [variable for variable in variables if variable not in graph.variables]
    if missing:
        raise JointQueryUnavailableError(
            method,
            variables,
            f"unknown variables in factor graph: {missing!r}",
            diagnostics={"missing": missing},
        )


def _exact_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    try:
        probs = exact_joint_over(graph, variables)
    except ValueError as error:
        if _EXACT_TOO_MANY_VARIABLES_MESSAGE not in str(error):
            raise
        raise JointQueryUnavailableError(
            "exact",
            variables,
            str(error),
            diagnostics={"exception": type(error).__name__},
        ) from error
    return JointDistribution(
        variables=variables,
        probabilities=[float(value) for value in probs.tolist()],
        method="exact",
        is_exact=True,
        basis="exact_joint_distribution",
    )


def _junction_tree_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    calibration = calibrate_junction_tree(graph)

    requested = set(variables)
    for clique, var_list, table in zip(
        calibration.cliques,
        calibration.clique_var_lists,
        calibration.calibrated,
        strict=True,
    ):
        if requested <= clique:
            probabilities = _marginalize_table_to_variables(table, var_list, variables)
            return JointDistribution(
                variables=variables,
                probabilities=probabilities,
                method="junction_tree",
                is_exact=True,
                basis="calibrated_clique_marginal",
                diagnostics={
                    "treewidth": calibration.treewidth,
                    "clique_size": len(var_list),
                    "source_clique": var_list,
                },
            )

    if not graph.factors:
        return _independent_junction_tree_joint_over(calibration, variables)

    raise JointQueryUnavailableError(
        "junction_tree",
        variables,
        "requested variables are not contained in a single calibrated clique",
        diagnostics={
            "treewidth": calibration.treewidth,
            "available_cliques": [sorted(clique) for clique in calibration.cliques],
        },
    )


def _independent_junction_tree_joint_over(
    calibration: JunctionTreeCalibration,
    variables: list[str],
) -> JointDistribution:
    singleton_tables = {
        var_list[0]: table
        for clique, var_list, table in zip(
            calibration.cliques,
            calibration.clique_var_lists,
            calibration.calibrated,
            strict=True,
        )
        if len(clique) == 1 and len(var_list) == 1
    }
    missing = [variable for variable in variables if variable not in singleton_tables]
    if missing:
        raise JointQueryUnavailableError(
            "junction_tree",
            variables,
            "requested variables are not contained in calibrated singleton priors",
            diagnostics={
                "treewidth": calibration.treewidth,
                "missing": missing,
                "available_cliques": [sorted(clique) for clique in calibration.cliques],
            },
        )

    probabilities: list[float] = []
    for assignment_index in range(1 << len(variables)):
        probability = 1.0
        for bit, variable in enumerate(variables):
            table = singleton_tables[variable]
            value = (assignment_index >> bit) & 1
            probability *= float(table[(value,)])
        probabilities.append(probability)

    total = sum(probabilities)
    if total <= 0.0:
        raise ValueError("independent joint table has zero total mass")
    probabilities = [probability / total for probability in probabilities]

    diagnostics: dict[str, Any] = {
        "treewidth": calibration.treewidth,
        "clique_size": 1,
        "source_cliques": [[variable] for variable in variables],
    }
    if len(variables) == 1:
        diagnostics["source_clique"] = [variables[0]]
        diagnostics.pop("source_cliques")

    return JointDistribution(
        variables=variables,
        probabilities=probabilities,
        method="junction_tree",
        is_exact=True,
        basis="calibrated_clique_marginal",
        diagnostics=diagnostics,
    )


def _marginalize_table_to_variables(
    table: dict[tuple[int, ...], float],
    table_variables: list[str],
    variables: list[str],
) -> list[float]:
    indices = [table_variables.index(variable) for variable in variables]
    probabilities = [0.0 for _ in range(1 << len(variables))]
    for assignment, probability in table.items():
        out_index = 0
        for bit, table_index in enumerate(indices):
            out_index |= assignment[table_index] << bit
        probabilities[out_index] += float(probability)
    total = sum(probabilities)
    if total <= 0.0:
        raise ValueError("marginalized joint table has zero total mass")
    return [probability / total for probability in probabilities]


def _probability_list_to_assignment_table(
    probabilities: list[float],
    variables: list[str],
) -> dict[tuple[int, ...], float]:
    table: dict[tuple[int, ...], float] = {}
    for assignment_index, probability in enumerate(probabilities):
        values = tuple((assignment_index >> bit) & 1 for bit in range(len(variables)))
        table[values] = float(probability)
    return table


def _trw_bp_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    result = TRWBeliefPropagation().run(graph)
    requested = set(variables)
    factor_joint_tables = result.diagnostics.factor_joint_tables
    available_scopes = [list(table["variables"]) for table in factor_joint_tables]

    covering_tables = [
        table for table in factor_joint_tables if requested <= set(table["variables"])
    ]
    covering_tables.sort(key=lambda table: (len(table["variables"]), table["factor_index"]))

    for table in covering_tables:
        table_variables = list(table["variables"])
        assignment_table = _probability_list_to_assignment_table(
            list(table["probabilities"]),
            table_variables,
        )
        probabilities = _marginalize_table_to_variables(
            assignment_table,
            table_variables,
            variables,
        )
        return JointDistribution(
            variables=variables,
            probabilities=probabilities,
            method="trw_bp",
            is_exact=False,
            basis="approximate_joint_distribution",
            diagnostics={
                "source_factor_index": table["factor_index"],
                "source_factor_id": table["factor_id"],
                "source_factor_variables": table_variables,
                "source_factor_rho": table["rho"],
                "converged": result.diagnostics.converged,
                "iterations_run": result.diagnostics.iterations_run,
                "max_change_at_stop": result.diagnostics.max_change_at_stop,
                "available_scopes": available_scopes,
                "factor_joint_table_count": len(factor_joint_tables),
                "cromwell_eps": CROMWELL_EPS,
            },
        )

    raise JointQueryUnavailableError(
        "trw_bp",
        variables,
        "requested variables are not contained in a single factor-scope pseudo-joint",
        diagnostics={
            "available_scopes": available_scopes,
            "converged": result.diagnostics.converged,
            "iterations_run": result.diagnostics.iterations_run,
            "max_change_at_stop": result.diagnostics.max_change_at_stop,
            "factor_joint_table_count": len(factor_joint_tables),
        },
    )


def _mean_field_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    result = MeanFieldVI().run(graph)
    missing = [variable for variable in variables if variable not in result.beliefs]
    if missing:
        raise JointQueryUnavailableError(
            "mean_field",
            variables,
            f"mean_field result missing variables: {missing!r}",
            diagnostics={"missing": missing},
        )

    probabilities: list[float] = []
    for assignment_index in range(1 << len(variables)):
        probability = 1.0
        for bit, variable in enumerate(variables):
            belief = result.beliefs[variable]
            value = (assignment_index >> bit) & 1
            probability *= belief if value == 1 else (1.0 - belief)
        probabilities.append(float(probability))

    return JointDistribution(
        variables=variables,
        probabilities=probabilities,
        method="mean_field",
        is_exact=False,
        basis="variational_joint_distribution",
        diagnostics={
            "converged": result.diagnostics.converged,
            "iterations_run": result.diagnostics.iterations_run,
            "max_change_at_stop": result.diagnostics.max_change_at_stop,
            "cromwell_eps": CROMWELL_EPS,
        },
    )
