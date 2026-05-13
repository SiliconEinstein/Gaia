"""InformationSet — the Jaynes information state I as a single datum.

Every piece of information the author asserts lives in exactly one of the
five fields below. What is NOT in the set is not information (desideratum
D3); those variables remain class-V (MaxEnt free).

Structural validation only — semantic desiderata (D1 completeness, D2
structural dedup, Cromwell clamp) live in jaynes_ref.desiderata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.jaynes_ref.constraints import CPT, Likelihood, LogicalConstraint, WeightedFactor

# Cromwell floor for class-IV soft priors. NOT enforced at construction —
# used only by the optional desiderata.apply_cromwell_clamp step.
# Class-I hard evidence stays strictly {0, 1}; class-III CPT entries and
# logical constraints are exact assertions, not soft priors, so this ε
# does not apply to them.
CROMWELL_EPS = 1e-3


@dataclass
class InformationSet:
    """Jaynes information set I, partitioned into five classes.

    Attributes:
        variables: Universe of discourse — all propositional variables.
            Binary, each ∈ {0, 1}. A variable present here but absent
            from every other field is class-V (MaxEnt free).
        hard_evidence: Class I — var = 0|1 as logical δ assertion.
        unary_priors: Class IV — π = P(x=1), strictly in (0, 1).
            Values of 0 or 1 must move to hard_evidence (D4: logical
            assertions use δ, not soft priors).
        likelihoods: Class II — single-variable likelihood ratios.
            Folded into class IV during exact inference; kept separately
            so the audit trail can recover the pre-update prior.
        cpts: Class III — conditional probability tables P(child|parents).
        constraints: Deterministic logical potentials ψ: {0,1}^k → {0,1}.
        weighted_factors: Non-normalised non-negative factors (e.g. pairwise potentials).
    """

    variables: set[str] = field(default_factory=set)
    hard_evidence: dict[str, int] = field(default_factory=dict)
    unary_priors: dict[str, float] = field(default_factory=dict)
    likelihoods: list[Likelihood] = field(default_factory=list)
    cpts: list[CPT] = field(default_factory=list)
    constraints: list[LogicalConstraint] = field(default_factory=list)
    weighted_factors: list[WeightedFactor] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate information state after initialization."""
        self.validate()

    # ------------------------------------------------------------------
    # Validation — structural only
    # ------------------------------------------------------------------

    def validate(self) -> None:  # noqa: C901
        """Re-run structural validation after any mutation."""
        for v in self.variables:
            if not isinstance(v, str) or not v:
                raise ValueError(f"variables must be non-empty strs, got {v!r}")

        for v, val in self.hard_evidence.items():
            if v not in self.variables:
                raise ValueError(f"hard_evidence references undeclared variable {v!r}")
            if val not in (0, 1):
                raise ValueError(f"hard_evidence[{v!r}] must be 0 or 1, got {val!r}")

        for v, pi in self.unary_priors.items():
            if v not in self.variables:
                raise ValueError(f"unary_priors references undeclared variable {v!r}")
            if not (0.0 < pi < 1.0):
                raise ValueError(
                    f"unary_priors[{v!r}]={pi} must be strictly in (0, 1). "
                    f"For π=0 or π=1 use hard_evidence (class I, δ)."
                )

        # D1 structural check: no variable may be in both hard_evidence and
        # unary_priors. Same datum in two channels is a D1 violation even
        # if the values happen to agree.
        overlap = set(self.hard_evidence) & set(self.unary_priors)
        if overlap:
            raise ValueError(
                f"D1 violation: variables {sorted(overlap)} appear in both "
                f"hard_evidence (class I) and unary_priors (class IV). "
                f"Each variable may be informed by at most one channel."
            )

        for lk in self.likelihoods:
            if lk.variable not in self.variables:
                raise ValueError(f"likelihood references undeclared variable {lk.variable!r}")

        for cpt in self.cpts:
            if cpt.child not in self.variables:
                raise ValueError(f"CPT.child {cpt.child!r} is undeclared")
            for p in cpt.parents:
                if p not in self.variables:
                    raise ValueError(f"CPT.parent {p!r} is undeclared")

        for c in self.constraints:
            for v in c.variables:
                if v not in self.variables:
                    raise ValueError(f"LogicalConstraint variable {v!r} is undeclared")

        for wf in self.weighted_factors:
            for v in wf.variables:
                if v not in self.variables:
                    raise ValueError(f"WeightedFactor variable {v!r} is undeclared")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def declare(self, *vars: str) -> None:
        """Register one or more variables in the universe."""
        for v in vars:
            if not isinstance(v, str) or not v:
                raise ValueError(f"variable id must be a non-empty str, got {v!r}")
            self.variables.add(v)

    def free_variables(self) -> set[str]:
        """Class-V variables: declared but informed by no field.

        CPT.parents do NOT count as declared information on the parent —
        only CPT.child does (the CPT constrains the child given parents).
        """
        informed = set(self.hard_evidence) | set(self.unary_priors)
        for lk in self.likelihoods:
            informed.add(lk.variable)
        for cpt in self.cpts:
            informed.add(cpt.child)
        return self.variables - informed
