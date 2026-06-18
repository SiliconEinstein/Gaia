"""gaia.engine.inquiry — spec §10 public surface.

Thin wrapper over Gaia. This module does not run its own compiler, validator,
or inference engine; it composes the ones already in Gaia.
"""

from gaia.engine.inquiry.anchor import SourceAnchor, find_anchors
from gaia.engine.inquiry.check_core import (
    HoleEntry,
    KnowledgeBreakdown,
    analyze_knowledge_breakdown,
    find_possible_duplicate_claims,
)
from gaia.engine.inquiry.diagnostics import (
    Diagnostic,
    NextEdit,
    format_diagnostics_as_next_edits,
    format_diagnostics_as_structured_edits,
    from_knowledge_breakdown,
    from_validation,
)
from gaia.engine.inquiry.diff import ClaimDelta, SemanticDiff, empty_diff
from gaia.engine.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.engine.inquiry.proof_state import (
    HypothesisView,
    ObligationView,
    ProofContext,
    RejectionView,
    build_proof_context,
)
from gaia.engine.inquiry.render import render_json, render_markdown, to_json_dict
from gaia.engine.inquiry.review import ReviewReport, render_text, resolve_graph, run_review
from gaia.engine.inquiry.review_manifest import load_or_generate_review_manifest
from gaia.engine.inquiry.state import (
    RESEARCH_PUBLIC_STATE_API,
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
    "RESEARCH_PUBLIC_STATE_API",
    "STATE_SCHEMA_VERSION",
    "VALID_MODES",
    "VALID_OBLIGATION_KINDS",
    "ClaimDelta",
    "Diagnostic",
    "FocusBinding",
    "HoleEntry",
    "HypothesisView",
    "InquiryState",
    "KnowledgeBreakdown",
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
    "analyze_knowledge_breakdown",
    "append_tactic_event",
    "build_proof_context",
    "empty_diff",
    "find_anchors",
    "find_possible_duplicate_claims",
    "format_diagnostics_as_next_edits",
    "format_diagnostics_as_structured_edits",
    "from_knowledge_breakdown",
    "from_validation",
    "inquiry_dir",
    "load_or_generate_review_manifest",
    "load_state",
    "mint_qid",
    "pop_focus_frame",
    "push_focus_frame",
    "read_tactic_log",
    "render_json",
    "render_markdown",
    "render_text",
    "resolve_focus_target",
    "resolve_graph",
    "run_review",
    "save_state",
    "to_json_dict",
]
