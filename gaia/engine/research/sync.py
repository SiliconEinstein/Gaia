"""Sync research artifacts into Gaia package source and inquiry state.

``.gaia/research`` is an audit/cache layer. This module is the narrow bridge
that takes review artifacts produced by ``gaia research`` and records durable
state in the existing package-native surfaces:

* authored DSL source for questions, notes, scaffold relations, materializations;
* ``.gaia/inquiry`` for active focus, synthetic hypotheses, and obligations.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gaia.cli.commands.author._authored import ensure_authored_submodule
from gaia.cli.commands.author._common import split_csv_refs
from gaia.cli.commands.author._writer import append_statement
from gaia.engine.inquiry.state import (
    SyntheticHypothesis,
    SyntheticObligation,
    append_tactic_event,
    load_state,
    mint_qid,
    save_state,
)
from gaia.engine.research.artifacts import ResearchPackage

JsonDict = dict[str, Any]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SLUG_RE = re.compile(r"[^A-Za-z0-9_]+")
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_READINESS_ORDER = {
    "ready_for_assess": 0,
    "needs_expand": 1,
    "needs_human_review": 2,
    "defer": 3,
}


@dataclass
class ResearchSyncResult:
    """Summary of package/inquiry writes performed for one research action."""

    dry_run: bool = False
    artifact_only: bool = False
    source_writes_enabled: bool = True
    questions_written: list[str] = field(default_factory=list)
    questions_skipped: list[str] = field(default_factory=list)
    notes_written: list[str] = field(default_factory=list)
    notes_skipped: list[str] = field(default_factory=list)
    candidate_relations_written: list[str] = field(default_factory=list)
    candidate_relations_skipped: list[str] = field(default_factory=list)
    materializations_written: list[str] = field(default_factory=list)
    materializations_skipped: list[str] = field(default_factory=list)
    obligations_added: list[str] = field(default_factory=list)
    obligations_skipped: int = 0
    hypotheses_added: list[str] = field(default_factory=list)
    hypotheses_skipped: int = 0
    focus_set: str | None = None

    @property
    def writes_source(self) -> bool:
        """Whether this sync is allowed to write package source."""
        return not self.artifact_only and self.source_writes_enabled and not self.dry_run

    @property
    def writes_inquiry(self) -> bool:
        """Whether this sync is allowed to mutate inquiry state."""
        return not self.artifact_only and not self.dry_run

    def to_payload(self) -> JsonDict:
        """Return a JSON-compatible summary for research events."""
        return {
            "dry_run": self.dry_run,
            "artifact_only": self.artifact_only,
            "writes_source": self.writes_source,
            "writes_inquiry": self.writes_inquiry,
            "questions_written": list(self.questions_written),
            "questions_skipped": list(self.questions_skipped),
            "notes_written": list(self.notes_written),
            "notes_skipped": list(self.notes_skipped),
            "candidate_relations_written": list(self.candidate_relations_written),
            "candidate_relations_skipped": list(self.candidate_relations_skipped),
            "materializations_written": list(self.materializations_written),
            "materializations_skipped": list(self.materializations_skipped),
            "obligations_added": list(self.obligations_added),
            "obligations_skipped": self.obligations_skipped,
            "hypotheses_added": list(self.hypotheses_added),
            "hypotheses_skipped": self.hypotheses_skipped,
            "focus_set": self.focus_set,
        }


def _source_root(pkg: ResearchPackage) -> Path:
    src_root = pkg.path / "src" / pkg.import_name
    if src_root.exists():
        return src_root
    return pkg.path / pkg.import_name


def _authored_init_path(pkg: ResearchPackage) -> Path:
    source_root = _source_root(pkg)
    return ensure_authored_submodule(source_root, source_root / "__init__.py")


def _short_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def _slug(value: object, *, max_len: int = 56) -> str:
    text = str(value or "").strip().lower()
    text = _SLUG_RE.sub("_", text).strip("_")
    if not text:
        text = "item"
    if text[0].isdigit():
        text = f"r_{text}"
    return text[:max_len].strip("_") or "item"


def _binding(prefix: str, seed: object) -> str:
    base = _slug(seed)
    return f"{prefix}_{base}_{_short_hash(seed)}"


def _binding_exists(path: Path, binding: str) -> bool:
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8")
    return re.search(rf"^\s*{re.escape(binding)}\s*=", source, flags=re.MULTILINE) is not None


def _research_metadata(kind: str, payload: JsonDict) -> JsonDict:
    return {"gaia_research": {"kind": kind, **payload}}


def _append_statement_once(
    pkg: ResearchPackage,
    *,
    binding: str,
    generated_code: str,
    required_imports: tuple[str, ...],
    result_list: list[str],
    skip_list: list[str],
    export: bool = False,
    sibling_imports: tuple[tuple[str, str], ...] = (),
    foreign_imports: tuple[tuple[str, str, str], ...] = (),
    source_writes: bool,
) -> None:
    target = _authored_init_path(pkg)
    if _binding_exists(target, binding):
        skip_list.append(binding)
        return
    if not source_writes:
        skip_list.append(binding)
        return
    append_statement(
        target,
        generated_code,
        new_label=binding,
        required_imports=required_imports,
        sibling_imports=sibling_imports,
        foreign_imports=foreign_imports,
        import_package_name=pkg.import_name,
        export=export,
    )
    result_list.append(binding)


def _add_hypothesis_once(
    pkg: ResearchPackage,
    *,
    content: str,
    scope_qid: str | None,
    anchor: JsonDict,
    result: ResearchSyncResult,
) -> None:
    if not result.writes_inquiry:
        result.hypotheses_skipped += 1
        return
    state = load_state(pkg.path)
    for existing in state.synthetic_hypotheses:
        if existing.content == content and existing.scope_qid == scope_qid:
            result.hypotheses_skipped += 1
            return
    hypothesis = SyntheticHypothesis(qid=mint_qid("hyp"), content=content, scope_qid=scope_qid)
    state.synthetic_hypotheses.append(hypothesis)
    save_state(pkg.path, state)
    append_tactic_event(
        pkg.path,
        "research.hypothesis.added",
        {"qid": hypothesis.qid, "scope_qid": scope_qid, "anchor": anchor},
    )
    result.hypotheses_added.append(hypothesis.qid)


def _add_obligation_once(
    pkg: ResearchPackage,
    *,
    target_qid: str,
    content: str,
    diagnostic_kind: str,
    anchor: JsonDict,
    result: ResearchSyncResult,
) -> None:
    if not result.writes_inquiry:
        result.obligations_skipped += 1
        return
    state = load_state(pkg.path)
    for existing in state.synthetic_obligations:
        if (
            existing.target_qid == target_qid
            and existing.content == content
            and existing.diagnostic_kind == diagnostic_kind
        ):
            result.obligations_skipped += 1
            return
    obligation = SyntheticObligation(
        qid=mint_qid("oblig"),
        target_qid=target_qid,
        content=content,
        diagnostic_kind=diagnostic_kind,
        anchor=anchor,
    )
    state.synthetic_obligations.append(obligation)
    save_state(pkg.path, state)
    append_tactic_event(
        pkg.path,
        "research.obligation.added",
        {
            "qid": obligation.qid,
            "target_qid": target_qid,
            "diagnostic_kind": diagnostic_kind,
            "anchor": anchor,
        },
    )
    result.obligations_added.append(obligation.qid)


def _set_focus(pkg: ResearchPackage, *, focus: str, kind: str, result: ResearchSyncResult) -> None:
    if not result.writes_inquiry:
        return
    state = load_state(pkg.path)
    if state.focus == focus and state.focus_kind == kind:
        result.focus_set = focus
        return
    if state.focus is not None:
        state.focus_stack.append(
            {
                "focus": state.focus,
                "focus_kind": state.focus_kind,
                "focus_resolved_id": state.focus_resolved_id,
            }
        )
    state.focus = focus
    state.focus_kind = kind
    state.focus_resolved_id = None
    save_state(pkg.path, state)
    append_tactic_event(pkg.path, "research.focus.set", {"focus": focus, "kind": kind})
    result.focus_set = focus


def _focus_sort_key(focus: JsonDict) -> tuple[int, int, str]:
    return (
        _PRIORITY_ORDER.get(str(focus.get("priority", "low")), 99),
        _READINESS_ORDER.get(str(focus.get("readiness", "defer")), 99),
        str(focus.get("id", "")),
    )


def _focuses_from_artifact(artifact: JsonDict) -> list[JsonDict]:
    raw_focuses = artifact.get("focuses", [])
    return [item for item in raw_focuses if isinstance(item, dict)]


def _accepted_focuses(focuses: list[JsonDict], *, max_questions: int) -> list[JsonDict]:
    accepted = [focus for focus in focuses if focus.get("status") == "accepted"]
    return sorted(accepted, key=_focus_sort_key)[:max_questions]


def _sync_accepted_focus_questions(
    pkg: ResearchPackage,
    focuses: list[JsonDict],
    *,
    result: ResearchSyncResult,
) -> list[str]:
    written_or_existing: list[str] = []
    for focus in focuses:
        focus_id = str(focus.get("id") or "focus")
        question = focus.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        binding = _binding("rq", focus_id)
        metadata = _research_metadata(
            "accepted_focus",
            {
                "focus_id": focus_id,
                "priority": focus.get("priority"),
                "readiness": focus.get("readiness"),
                "scope": focus.get("scope", {}),
                "coverage": focus.get("coverage", {}),
                "evidence_refs": focus.get("evidence_refs", []),
            },
        )
        code = (
            f"{binding} = question({question.strip()!r}, title={focus_id!r}, metadata={metadata!r})"
        )
        before_written = len(result.questions_written)
        _append_statement_once(
            pkg,
            binding=binding,
            generated_code=code,
            required_imports=("question",),
            result_list=result.questions_written,
            skip_list=result.questions_skipped,
            source_writes=result.writes_source,
        )
        if len(result.questions_written) > before_written or binding in result.questions_skipped:
            written_or_existing.append(binding)
    return written_or_existing


def _sync_candidate_focus_hypotheses(
    pkg: ResearchPackage,
    focuses: list[JsonDict],
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    for focus in focuses:
        if focus.get("status") == "accepted":
            continue
        question = focus.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=question.strip(),
            scope_qid=scope_qid,
            anchor={"kind": "candidate_focus", "id": focus.get("id")},
            result=result,
        )


def _sync_focus_coverage_gaps(
    pkg: ResearchPackage,
    gaps: object,
    *,
    target_qid: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(gaps, list):
        return
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        description = gap.get("description")
        if not isinstance(description, str) or not description.strip():
            continue
        _add_obligation_once(
            pkg,
            target_qid=target_qid,
            content=description.strip(),
            diagnostic_kind="focus_weakness",
            anchor={"kind": "focus_coverage_gap", "id": gap.get("id")},
            result=result,
        )


def sync_landscape_artifact(
    pkg: ResearchPackage,
    landscape: JsonDict,
    *,
    artifact_only: bool = False,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record broad/targeted landscape discoveries as inquiry scaffolds."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        artifact_only=artifact_only,
        source_writes_enabled=False,
    )
    if artifact_only or dry_run:
        return result

    target = landscape.get("target")
    if isinstance(target, dict):
        target_qid = str(target.get("id") or "research_landscape")
    else:
        target_qid = "research_landscape"

    focuses = landscape.get("candidate_focuses", [])
    if isinstance(focuses, list):
        for focus in focuses:
            if not isinstance(focus, dict):
                continue
            question = focus.get("question")
            if not isinstance(question, str) or not question.strip():
                continue
            _add_hypothesis_once(
                pkg,
                content=question.strip(),
                scope_qid=target_qid if target_qid != "research_landscape" else None,
                anchor={"kind": "landscape_focus", "id": focus.get("id")},
                result=result,
            )

    gaps = landscape.get("candidate_coverage_gaps", [])
    if isinstance(gaps, list):
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            description = gap.get("description") or gap.get("suggestion")
            if not isinstance(description, str) or not description.strip():
                continue
            _add_obligation_once(
                pkg,
                target_qid=target_qid,
                content=description.strip(),
                diagnostic_kind="focus_weakness",
                anchor={"kind": "landscape_gap", "id": gap.get("id")},
                result=result,
            )

    return result


def sync_focus_artifact(
    pkg: ResearchPackage,
    artifact: JsonDict,
    *,
    max_questions: int = 3,
    artifact_only: bool = False,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Write accepted focuses as package questions and inquiry state."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        artifact_only=artifact_only,
        source_writes_enabled=source_writes,
    )
    if artifact_only:
        return result

    focuses = _focuses_from_artifact(artifact)
    accepted = _accepted_focuses(focuses, max_questions=max_questions)
    written_or_existing = _sync_accepted_focus_questions(pkg, accepted, result=result)

    if written_or_existing:
        _set_focus(pkg, focus=written_or_existing[0], kind="question", result=result)

    scope_qid = written_or_existing[0] if written_or_existing else None
    _sync_candidate_focus_hypotheses(pkg, focuses, scope_qid=scope_qid, result=result)
    target_qid = written_or_existing[0] if written_or_existing else "research_focus"
    _sync_focus_coverage_gaps(
        pkg, artifact.get("coverage_gaps"), target_qid=target_qid, result=result
    )

    return result


def _review_markdown(review: JsonDict) -> str:
    parts: list[str] = []
    summary = review.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary.strip())
    sections = review.get("sections", [])
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            title = section.get("title")
            body = section.get("body")
            if isinstance(title, str) and title.strip():
                parts.append(f"## {title.strip()}")
            if isinstance(body, str) and body.strip():
                parts.append(body.strip())
    limitations = review.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines = [str(item).strip() for item in limitations if str(item).strip()]
        if lines:
            parts.append("## Limitations\n" + "\n".join(f"- {line}" for line in lines))
    return "\n\n".join(parts).strip()


def _assessment_package_ref_value_types(assessment: JsonDict) -> dict[str, str]:
    evidence_packet = assessment.get("evidence_packet")
    items = evidence_packet.get("items") if isinstance(evidence_packet, dict) else None
    if not isinstance(items, list):
        return {}

    refs: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        package_ref_payload = item.get("package_ref")
        if not isinstance(package_ref_payload, dict):
            continue
        ref = package_ref_payload.get("ref")
        value_type = package_ref_payload.get("value_type")
        if isinstance(ref, str) and ref and isinstance(value_type, str) and value_type:
            refs[ref] = value_type
    return refs


def _relation_claim_refs(
    relation: JsonDict,
    *,
    package_ref_value_types: dict[str, str] | None = None,
) -> tuple[list[str], tuple[tuple[str, str], ...], tuple[tuple[str, str, str], ...]]:
    raw_refs = relation.get("claim_refs", relation.get("claims"))
    if raw_refs is None:
        raw_refs = _package_ref_source_refs(relation)
    if not isinstance(raw_refs, list):
        return [], (), ()
    refs = [str(item).strip() for item in raw_refs if str(item).strip()]
    if len(refs) < 2:
        return [], (), ()
    value_types = package_ref_value_types or {}
    if any(value_types.get(ref) not in (None, "claim") for ref in refs):
        return [], (), ()
    tokens, error = split_csv_refs(",".join(refs))
    if error is not None:
        return [], (), ()
    sibling = tuple((item, "") for item in tokens.local)
    foreign = tuple((item.module, item.symbol, item.alias) for item in tokens.foreign_imports)
    return tokens.rendered, sibling, foreign


def _package_ref_source_refs(relation: JsonDict) -> list[str]:
    source_refs = relation.get("source_refs")
    if not isinstance(source_refs, list):
        return []
    refs: list[str] = []
    for ref in source_refs:
        if not isinstance(ref, dict) or ref.get("kind") != "package_ref":
            continue
        ref_id = ref.get("id")
        if isinstance(ref_id, str) and ref_id.strip():
            refs.append(ref_id.strip())
    return refs


def _candidate_relation_pattern(relation_type: str, claim_refs: list[str]) -> str | None:
    if relation_type == "opposes" and len(claim_refs) == 2:
        return "contradict"
    return None


def _sync_assessment_review_note(
    pkg: ResearchPackage,
    assessment: JsonDict,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    review = assessment.get("review")
    if not isinstance(review, dict):
        return
    content = _review_markdown(review)
    if not content:
        return
    binding = _binding("review", {"focus": focus_id, "summary": review.get("summary")})
    metadata = _research_metadata(
        "assessment_review",
        {"focus": focus_id, "language": review.get("language"), "depth": review.get("depth")},
    )
    code = (
        f"{binding} = note("
        f"{content!r}, title={('Assessment review: ' + focus_id)!r}, metadata={metadata!r})"
    )
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("note",),
        result_list=result.notes_written,
        skip_list=result.notes_skipped,
        source_writes=result.writes_source,
    )


def _sync_assessment_relation_hypothesis(
    pkg: ResearchPackage,
    relation: JsonDict,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    claim = relation.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        return
    content = f"{relation.get('type', 'relation')}: {claim.strip()}"
    _add_hypothesis_once(
        pkg,
        content=content,
        scope_qid=focus_id,
        anchor={
            "kind": "assessment_relation",
            "source_refs": relation.get("source_refs"),
        },
        result=result,
    )


def _sync_assessment_candidate_relation(
    pkg: ResearchPackage,
    relation: JsonDict,
    *,
    focus_id: str,
    package_ref_value_types: dict[str, str],
    result: ResearchSyncResult,
) -> None:
    claim_refs, sibling_imports, foreign_imports = _relation_claim_refs(
        relation,
        package_ref_value_types=package_ref_value_types,
    )
    if len(claim_refs) < 2:
        result.candidate_relations_skipped.append(
            str(relation.get("id") or relation.get("claim") or "relation")
        )
        return
    relation_type = str(relation.get("type") or "relation")
    binding = _binding(
        "candidate_relation",
        {
            "focus": focus_id,
            "type": relation_type,
            "claim_refs": claim_refs,
            "claim": relation.get("claim"),
        },
    )
    pattern = _candidate_relation_pattern(relation_type, claim_refs)
    metadata = _research_metadata(
        "assessment_candidate_relation",
        {
            "focus": focus_id,
            "relation_type": relation_type,
            "epistemic_status": relation.get("epistemic_status"),
            "source_refs": relation.get("source_refs", []),
        },
    )
    kwargs = [f"claims=[{', '.join(claim_refs)}]"]
    if pattern is not None:
        kwargs.append(f"pattern={pattern!r}")
    rationale = relation.get("rationale")
    if isinstance(rationale, str) and rationale.strip():
        kwargs.append(f"rationale={rationale.strip()!r}")
    kwargs.append(f"metadata={metadata!r}")
    code = f"{binding} = candidate_relation({', '.join(kwargs)})"
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("candidate_relation",),
        result_list=result.candidate_relations_written,
        skip_list=result.candidate_relations_skipped,
        sibling_imports=sibling_imports,
        foreign_imports=foreign_imports,
        source_writes=result.writes_source,
    )


def _sync_assessment_relations(
    pkg: ResearchPackage,
    relations: object,
    *,
    focus_id: str,
    package_ref_value_types: dict[str, str],
    result: ResearchSyncResult,
) -> None:
    if not isinstance(relations, list):
        return
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        _sync_assessment_relation_hypothesis(pkg, relation, focus_id=focus_id, result=result)
        _sync_assessment_candidate_relation(
            pkg,
            relation,
            focus_id=focus_id,
            package_ref_value_types=package_ref_value_types,
            result=result,
        )


def _sync_assessment_obligations(
    pkg: ResearchPackage,
    obligations: object,
    *,
    focus_id: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(obligations, list):
        return
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        content = obligation.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        raw_kind = str(obligation.get("kind") or "other")
        diagnostic_kind = "support_weak" if raw_kind == "needs_more_evidence" else "other"
        _add_obligation_once(
            pkg,
            target_qid=focus_id,
            content=content.strip(),
            diagnostic_kind=diagnostic_kind,
            anchor={
                "kind": "assessment_obligation",
                "source_refs": obligation.get("source_refs"),
            },
            result=result,
        )


def sync_assessment_artifact(
    pkg: ResearchPackage,
    assessment: JsonDict,
    *,
    artifact_only: bool = False,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record assessment review output as package/inquiry scaffolds."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        artifact_only=artifact_only,
        source_writes_enabled=source_writes,
    )
    if artifact_only:
        return result

    focus = assessment.get("focus")
    focus_id = str(focus.get("id") if isinstance(focus, dict) else "research_focus")
    package_ref_value_types = _assessment_package_ref_value_types(assessment)

    _sync_assessment_review_note(pkg, assessment, focus_id=focus_id, result=result)
    _sync_assessment_relations(
        pkg,
        assessment.get("relations"),
        focus_id=focus_id,
        package_ref_value_types=package_ref_value_types,
        result=result,
    )
    _sync_assessment_obligations(
        pkg,
        assessment.get("candidate_obligations"),
        focus_id=focus_id,
        result=result,
    )
    return result


def _source_assessment_focus_id(artifact: JsonDict) -> str:
    source_assessment = artifact.get("source_assessment")
    if isinstance(source_assessment, dict):
        focus_id = source_assessment.get("focus_id") or source_assessment.get("id")
        if isinstance(focus_id, str) and focus_id.strip():
            return focus_id.strip()
    return "research_proposal"


def _accepted_research_question_proposals(
    proposals: object,
    *,
    max_questions: int,
) -> list[JsonDict]:
    if not isinstance(proposals, list):
        return []
    accepted = [
        proposal
        for proposal in proposals
        if isinstance(proposal, dict)
        and proposal.get("status") == "accepted"
        and proposal.get("kind") == "research_question"
    ]
    return sorted(
        accepted,
        key=lambda proposal: (
            _PRIORITY_ORDER.get(str(proposal.get("priority", "low")), 99),
            str(proposal.get("id", "")),
        ),
    )[:max_questions]


def _sync_accepted_proposal_questions(
    pkg: ResearchPackage,
    proposals: list[JsonDict],
    *,
    source_focus_id: str,
    result: ResearchSyncResult,
) -> list[str]:
    written_or_existing: list[str] = []
    for proposal in proposals:
        proposal_id = str(proposal.get("id") or "proposal")
        question_text = proposal.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        binding = _binding("rq", proposal_id)
        metadata = _research_metadata(
            "accepted_proposal",
            {
                "proposal_id": proposal_id,
                "proposal_kind": proposal.get("kind"),
                "priority": proposal.get("priority"),
                "source_focus_id": source_focus_id,
                "source_refs": proposal.get("source_refs", []),
            },
        )
        code = (
            f"{binding} = question("
            f"{question_text.strip()!r}, title={proposal_id!r}, metadata={metadata!r})"
        )
        before_written = len(result.questions_written)
        _append_statement_once(
            pkg,
            binding=binding,
            generated_code=code,
            required_imports=("question",),
            result_list=result.questions_written,
            skip_list=result.questions_skipped,
            source_writes=result.writes_source,
        )
        if len(result.questions_written) > before_written or binding in result.questions_skipped:
            written_or_existing.append(binding)
    return written_or_existing


def _sync_proposal_hypotheses(
    pkg: ResearchPackage,
    hypotheses: object,
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(hypotheses, list):
        return
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        content = hypothesis.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=content.strip(),
            scope_qid=scope_qid,
            anchor={
                "kind": "proposal_hypothesis",
                "source_refs": hypothesis.get("source_refs"),
            },
            result=result,
        )


def _sync_unaccepted_proposals_as_hypotheses(
    pkg: ResearchPackage,
    proposals: object,
    *,
    scope_qid: str | None,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(proposals, list):
        return
    for proposal in proposals:
        if not isinstance(proposal, dict) or proposal.get("status") == "accepted":
            continue
        question_text = proposal.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        _add_hypothesis_once(
            pkg,
            content=question_text.strip(),
            scope_qid=scope_qid,
            anchor={"kind": "proposal_candidate", "id": proposal.get("id")},
            result=result,
        )


def _sync_proposal_obligations(
    pkg: ResearchPackage,
    obligations: object,
    *,
    target_qid: str,
    result: ResearchSyncResult,
) -> None:
    if not isinstance(obligations, list):
        return
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        content = obligation.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        raw_kind = str(obligation.get("kind") or "other")
        diagnostic_kind = "support_weak" if raw_kind == "needs_more_evidence" else "other"
        _add_obligation_once(
            pkg,
            target_qid=target_qid,
            content=content.strip(),
            diagnostic_kind=diagnostic_kind,
            anchor={
                "kind": "proposal_obligation",
                "source_refs": obligation.get("source_refs"),
            },
            result=result,
        )


def sync_proposal_artifact(
    pkg: ResearchPackage,
    proposal: JsonDict,
    *,
    max_questions: int = 3,
    artifact_only: bool = False,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Record accepted open-ended proposals as questions and inquiry state."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        artifact_only=artifact_only,
        source_writes_enabled=source_writes,
    )
    if artifact_only:
        return result

    source_focus_id = _source_assessment_focus_id(proposal)
    accepted_questions = _accepted_research_question_proposals(
        proposal.get("proposals"),
        max_questions=max_questions,
    )
    written_or_existing = _sync_accepted_proposal_questions(
        pkg,
        accepted_questions,
        source_focus_id=source_focus_id,
        result=result,
    )
    if written_or_existing:
        _set_focus(pkg, focus=written_or_existing[0], kind="question", result=result)

    scope_qid = written_or_existing[0] if written_or_existing else source_focus_id
    _sync_unaccepted_proposals_as_hypotheses(
        pkg,
        proposal.get("proposals"),
        scope_qid=scope_qid,
        result=result,
    )
    _sync_proposal_hypotheses(
        pkg,
        proposal.get("hypotheses"),
        scope_qid=scope_qid,
        result=result,
    )
    _sync_proposal_obligations(
        pkg,
        proposal.get("candidate_obligations"),
        target_qid=scope_qid,
        result=result,
    )
    return result


def sync_materialization(
    pkg: ResearchPackage,
    *,
    scaffold: str,
    by: list[str],
    rationale: str | None = None,
    artifact_only: bool = False,
    source_writes: bool = True,
    dry_run: bool = False,
) -> ResearchSyncResult:
    """Write an explicit ``materialize(...)`` link for a scaffold."""
    result = ResearchSyncResult(
        dry_run=dry_run,
        artifact_only=artifact_only,
        source_writes_enabled=source_writes,
    )
    if artifact_only:
        return result
    if not _IDENTIFIER_RE.match(scaffold):
        result.materializations_skipped.append(scaffold)
        return result
    clean_by = [item for item in by if _IDENTIFIER_RE.match(item)]
    if not clean_by or len(clean_by) != len(by):
        result.materializations_skipped.append(scaffold)
        return result
    binding = _binding("materialization", {"scaffold": scaffold, "by": clean_by})
    metadata = _research_metadata("materialization", {"scaffold": scaffold, "by": clean_by})
    kwargs = [f"by=[{', '.join(clean_by)}]"]
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    kwargs.append(f"metadata={metadata!r}")
    code = f"{binding} = materialize({scaffold}, {', '.join(kwargs)})"
    _append_statement_once(
        pkg,
        binding=binding,
        generated_code=code,
        required_imports=("materialize",),
        result_list=result.materializations_written,
        skip_list=result.materializations_skipped,
        sibling_imports=tuple((item, "") for item in clean_by),
        source_writes=result.writes_source,
    )
    return result


__all__ = [
    "ResearchSyncResult",
    "sync_assessment_artifact",
    "sync_focus_artifact",
    "sync_landscape_artifact",
    "sync_materialization",
    "sync_proposal_artifact",
]
