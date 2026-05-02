"""Spec §7 mode-specific report ranking + §15.4 next-edit ordering.

Each review mode reweights the **same** Diagnostic stream — there is no
mode-specific detection logic, only ordering. This keeps inquiry's read-only
contract (Non-Goals §2) while still letting agents see the most relevant
edits first.

The mapping in ``_MODE_RANK`` follows §7 verbatim:

* auto      — compile/validation errors → structural holes → focus → priors → beliefs → graph health
* formalize — provenance / explicit-vs-inferred / structural / prior holes
* explore   — focus weakness, support gaps, possible counterexamples, alternatives
* verify    — proof/computation/source citation, overconfident priors, weak supports
* publish   — exports + complete chains + structural + missing priors + render readiness

Mode is the *only* knob exposed to users. Diagnostic kinds that are not in a
mode's ranking still appear, just at the end (sorted by severity). This is
required so an unknown DiagnosticKind never silently drops off the report.
"""

from __future__ import annotations

from gaia.inquiry.diagnostics import Diagnostic, NextEdit


# Spec §7 — `kind` priority per mode. Lower number = higher priority.
# `severity` is a tiebreaker (error < warning < info).
_MODE_RANK: dict[str, dict[str, int]] = {
    "auto": {
        "compile_error": 0,
        "validation_error": 1,
        "validation_warning": 2,
        "structural_hole": 3,
        "focus_weakness": 4,
        "prior_hole": 5,
        "belief_regression": 6,
        "support_weak": 7,
        "orphaned_claim": 8,
        "background_only_claim": 9,
        "possible_duplicate_claim": 10,
        "stale_artifact": 11,
        "focus_low_posterior": 12,
        "unreviewed_warrant": 13,
        "prior_without_justification": 14,
        "rejected_warrant": 15,
        "blocked_warrant_path": 16,
        "focus_unsupported": 17,
        "large_belief_drop": 18,
        "overstrong_strategy_without_provenance": 19,
        "claim_with_evidence_but_no_focus_connection": 20,
    },
    "formalize": {
        "compile_error": 0,
        "validation_error": 1,
        "validation_warning": 2,
        "structural_hole": 3,
        "prior_hole": 4,
        "support_weak": 5,
        "orphaned_claim": 6,
        "background_only_claim": 7,
        "possible_duplicate_claim": 8,
        "focus_weakness": 9,
        "belief_regression": 10,
        "stale_artifact": 11,
        "prior_without_justification": 12,
        "unreviewed_warrant": 13,
        "rejected_warrant": 14,
        "focus_low_posterior": 15,
        "blocked_warrant_path": 16,
        "overstrong_strategy_without_provenance": 17,
        "focus_unsupported": 18,
        "large_belief_drop": 19,
        "claim_with_evidence_but_no_focus_connection": 20,
    },
    "explore": {
        "compile_error": 0,
        "focus_weakness": 1,
        "support_weak": 2,
        "structural_hole": 3,
        "validation_error": 4,
        "validation_warning": 5,
        "belief_regression": 6,
        "possible_duplicate_claim": 7,
        "orphaned_claim": 8,
        "background_only_claim": 9,
        "prior_hole": 10,
        "focus_low_posterior": 11,
        "rejected_warrant": 12,
        "unreviewed_warrant": 13,
        "stale_artifact": 14,
        "prior_without_justification": 15,
        "focus_unsupported": 16,
        "claim_with_evidence_but_no_focus_connection": 17,
        "blocked_warrant_path": 18,
        "large_belief_drop": 19,
        "overstrong_strategy_without_provenance": 20,
    },
    "verify": {
        "compile_error": 0,
        "validation_error": 1,
        "support_weak": 2,
        "prior_hole": 3,
        "belief_regression": 4,
        "validation_warning": 5,
        "structural_hole": 6,
        "focus_weakness": 7,
        "possible_duplicate_claim": 8,
        "orphaned_claim": 9,
        "background_only_claim": 10,
        "focus_low_posterior": 11,
        "prior_without_justification": 12,
        "stale_artifact": 13,
        "rejected_warrant": 14,
        "unreviewed_warrant": 15,
        "overstrong_strategy_without_provenance": 16,
        "large_belief_drop": 17,
        "blocked_warrant_path": 18,
        "focus_unsupported": 19,
        "claim_with_evidence_but_no_focus_connection": 20,
    },
    "publish": {
        "compile_error": 0,
        "validation_error": 1,
        "validation_warning": 2,
        "structural_hole": 3,
        "prior_hole": 4,
        "orphaned_claim": 5,
        "support_weak": 6,
        "background_only_claim": 7,
        "belief_regression": 8,
        "focus_weakness": 9,
        "possible_duplicate_claim": 10,
        "stale_artifact": 11,
        "prior_without_justification": 12,
        "unreviewed_warrant": 13,
        "rejected_warrant": 14,
        "focus_low_posterior": 15,
        "blocked_warrant_path": 16,
        "overstrong_strategy_without_provenance": 17,
        "focus_unsupported": 18,
        "large_belief_drop": 19,
        "claim_with_evidence_but_no_focus_connection": 20,
    },
}

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}

_UNKNOWN_KIND_RANK = 99  # appended after known kinds, sorted by severity only.


def supported_modes() -> tuple[str, ...]:
    return tuple(_MODE_RANK.keys())


def _key(mode: str):
    table = _MODE_RANK.get(mode, _MODE_RANK["auto"])

    def _k(d: Diagnostic | NextEdit):
        kind_rank = table.get(d.kind, _UNKNOWN_KIND_RANK)
        sev_rank = _SEVERITY_RANK.get(d.severity, 9)
        # Stable tiebreak on label so identical (kind, severity) sort deterministically.
        return (kind_rank, sev_rank, d.label)

    return _k


def rank_diagnostics(diagnostics: list[Diagnostic], mode: str) -> list[Diagnostic]:
    """Return a new list of diagnostics sorted by the mode's priority table.

    Always returns a copy. Unknown kinds are appended after known ones and
    sorted by severity only — they are never dropped.
    """
    return sorted(diagnostics, key=_key(mode))


def rank_next_edits(edits: list[NextEdit], mode: str) -> list[NextEdit]:
    """Same ranking applied to structured next-edits (kept in lock-step)."""
    return sorted(edits, key=_key(mode))
