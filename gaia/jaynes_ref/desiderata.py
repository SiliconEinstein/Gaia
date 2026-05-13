"""Optional Jaynes-desiderata audits over an InformationSet.

Structural validation is done at InformationSet.__post_init__. This module
adds *semantic* audits that do not raise but return advisories, plus a
Cromwell-clamp helper. All functions are side-effect-free unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from gaia.jaynes_ref.information import CROMWELL_EPS, InformationSet


@dataclass(frozen=True)
class AuditReport:
    """Non-fatal Jaynes-desiderata observations.

    * d1_warnings: likelihood fold targets a hard-evidence variable
      (class II on class I — duplicate source of information).
    * d3_class_v: variables in the universe with no information.
    * d4_near_boundary: unary priors within Cromwell ε of 0 or 1
      (author may have meant hard evidence).
    * d5_precheck: constraints whose allowed set is incompatible with
      the current hard evidence — Z will be 0 at inference time.
    * d2_duplicate_constraints: structurally identical constraints
      (dedup.py gives canonical keys; this field just flags the count).
    """

    d1_warnings: list[str] = field(default_factory=list)
    d3_class_v: list[str] = field(default_factory=list)
    d4_near_boundary: list[str] = field(default_factory=list)
    d5_precheck: list[str] = field(default_factory=list)
    d2_duplicate_constraints: int = 0

    def is_clean(self) -> bool:
        """Check if desiderata validation passed without errors."""
        return not (
            self.d1_warnings
            or self.d4_near_boundary
            or self.d5_precheck
            or self.d2_duplicate_constraints
        )


def audit(info: InformationSet, *, cromwell_eps: float = CROMWELL_EPS) -> AuditReport:
    """Run all semantic audits. Never raises — returns observations."""
    d1: list[str] = []
    d4: list[str] = []
    d5: list[str] = []

    for lk in info.likelihoods:
        if lk.variable in info.hard_evidence:
            d1.append(
                f"Likelihood on variable {lk.variable!r} which is pinned by hard evidence "
                f"({info.hard_evidence[lk.variable]}): class II is redundant with class I (D1)."
            )

    for v, pi in info.unary_priors.items():
        if pi < cromwell_eps or pi > 1.0 - cromwell_eps:
            d4.append(
                f"unary_priors[{v!r}]={pi:g} is within Cromwell ε={cromwell_eps:g} of a "
                f"logical bound; consider moving to hard_evidence (D4)."
            )

    for c in info.constraints:
        vars_all_pinned = all(v in info.hard_evidence for v in c.variables)
        if not vars_all_pinned:
            continue
        pinned_tuple = tuple(info.hard_evidence[v] for v in c.variables)
        if pinned_tuple not in c.allowed:
            d5.append(
                f"Constraint {c.label or c.variables!r}: hard_evidence {pinned_tuple} "
                f"is not in its allowed set — Z will be 0 at inference (D5 precheck)."
            )

    from gaia.jaynes_ref.dedup import canonical_constraint_key

    seen: dict = {}
    dup = 0
    for c in info.constraints:
        key = canonical_constraint_key(c)
        if key in seen:
            dup += 1
        seen[key] = True

    return AuditReport(
        d1_warnings=d1,
        d3_class_v=sorted(info.free_variables()),
        d4_near_boundary=d4,
        d5_precheck=d5,
        d2_duplicate_constraints=dup,
    )


def apply_cromwell_clamp(info: InformationSet, eps: float = CROMWELL_EPS) -> InformationSet:
    """Return a new InformationSet with unary_priors clamped to [eps, 1-eps].

    Class IV only. Class I (hard_evidence) stays strictly {0, 1} and
    class III CPTs / constraints are NOT clamped (they are exact
    assertions, per Jaynes).
    """
    clamped = {v: min(1.0 - eps, max(eps, pi)) for v, pi in info.unary_priors.items()}
    return replace(info, unary_priors=clamped)
