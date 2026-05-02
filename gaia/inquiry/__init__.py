"""gaia.inquiry — spec §10 public surface.

Thin wrapper over Gaia. This module does not run its own compiler, validator,
or inference engine; it composes the ones already in Gaia.
"""

from gaia.inquiry.anchor import SourceAnchor, find_anchors
from gaia.inquiry.diagnostics import (
    Diagnostic,
    NextEdit,
    format_diagnostics_as_next_edits,
    format_diagnostics_as_structured_edits,
    from_knowledge_breakdown,
    from_validation,
)
from gaia.inquiry.diff import ClaimDelta, SemanticDiff, empty_diff
from gaia.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.inquiry.proof_state import (
    HypothesisView,
    ObligationView,
    ProofContext,
    RejectionView,
    build_proof_context,
)
from gaia.inquiry.render import render_json, render_markdown, to_json_dict
from gaia.inquiry.review import ReviewReport, render_text, resolve_graph, run_review
from gaia.inquiry.state import (
    STATE_SCHEMA_VERSION,
    VALID_MODES,
    VALID_OBLIGATION_KINDS,
    InquiryState,
    SyntheticHypothesis,
    SyntheticObligation,
    SyntheticRejection,
    append_tactic_event,
    inquiry_dir,
    load_state,
    mint_qid,
    pop_focus_frame,
    push_focus_frame,
    read_tactic_log,
    save_state,
)

__all__ = [
    "STATE_SCHEMA_VERSION",
    "VALID_MODES",
    "VALID_OBLIGATION_KINDS",
    "ClaimDelta",
    "Diagnostic",
    "FocusBinding",
    "HypothesisView",
    "InquiryState",
    "NextEdit",
    "ObligationView",
    "ProofContext",
    "RejectionView",
    "ReviewReport",
    "SemanticDiff",
    "SourceAnchor",
    "SyntheticHypothesis",
    "SyntheticObligation",
    "SyntheticRejection",
    "append_tactic_event",
    "build_proof_context",
    "empty_diff",
    "find_anchors",
    "format_diagnostics_as_next_edits",
    "format_diagnostics_as_structured_edits",
    "from_knowledge_breakdown",
    "from_validation",
    "inquiry_dir",
    "render_json",
    "render_markdown",
    "load_state",
    "mint_qid",
    "pop_focus_frame",
    "push_focus_frame",
    "read_tactic_log",
    "render_text",
    "to_json_dict",
    "resolve_focus_target",
    "resolve_graph",
    "run_review",
    "save_state",
]
