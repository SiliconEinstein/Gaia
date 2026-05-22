"""ARA → Gaia deterministic projector (spec §7).

An ARA (agent research artifact) lays out a paper-shaped repository:

```
<host>/
  PAPER.md
  logic/
    claims.md
    problem.md
    experiments.md
    related_work.md
    solution/
  evidence/
    tables/
    figures/
  trace/
    exploration_tree.yaml
  src/
```

Spec §7.1 maps each ARA source category to a Gaia v0.5 DSL action.
This module implements the **safe subset**:

| ARA source                                            | Gaia output            |
|-------------------------------------------------------|------------------------|
| ``PAPER.md`` frontmatter                              | ``note(...)`` abstract |
| ``logic/claims.md`` ``Cxx`` blocks                    | ``claim(...)``         |
| ``logic/claims.md`` ``Proof: [Exx]`` lines            | ``depends_on(...)``    |
| ``evidence/tables/*.md``                              | ``observe(...)``       |
| ``logic/related_work.md`` ``Type: imports`` entries   | scholarly_reference    |
| Everything else                                       | ``note(...)``          |

The projector **never** emits ``derive`` / ``infer`` / ``equal`` /
``contradict`` / ``exclusive`` (spec §2.2 & §5.1) — those require a
human or agent decision recorded through the formalization queue.
Each ambiguous projection produces a queue item with the candidate
upgrade paths listed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.engine.codegen import Ref, render_call_statement, render_module
from gaia.engine.projector.api import (
    GeneratedFile,
    ProjectionResult,
    QueueItem,
    SourceMapRecord,
)
from gaia.engine.projector.host_kind import HostKind

__all__ = ["project_ara"]


_RW_BLOCK_RE = re.compile(
    r"^#{1,6}\s+(RW\d+)\s*[:.\-—]\s*(.+?)\s*$\n((?:(?!^#).+\n?)*)",
    re.MULTILINE,
)


# YAML-style frontmatter at the top of PAPER.md: ``---\nkey: value\n---``.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.+?)\n---\s*\n", re.DOTALL)


# Markdown pipe-table header on the first non-blank line.
_PIPE_TABLE_HEADER_RE = re.compile(r"^\|?\s*([^\n]+?)\s*\|?\s*$")


def _parse_paper_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse a YAML-shaped ``---`` block at the top of *text*.

    Restricted parser — we accept ``key: value`` and ``key: [a, b]``,
    skipping anything more complex. This is deliberate: full YAML
    would add a dependency for a corner that the ARM/ARA ecosystem
    uses sparingly. Unknown shapes are simply ignored and stay in the
    body for the abstract projector.

    Returns ``(metadata_dict, body_without_frontmatter)``. Empty
    metadata dict when no frontmatter is present.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text
    metadata: dict[str, Any] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue
        if raw_value.startswith("[") and raw_value.endswith("]"):
            metadata[key] = _parse_id_list(raw_value[1:-1])
        else:
            metadata[key] = raw_value.strip("\"'")
    body = text[match.end() :]
    return metadata, body


def _parse_pipe_table_columns(text: str) -> tuple[list[str], int]:
    """Return ``(column_headers, body_row_count)`` for a markdown pipe table.

    The first non-blank line is parsed as the column header; the
    optional separator line right under it (``|---|---|``) is
    skipped; everything else is counted as a body row. When the
    file is not a recognisable pipe table the function returns
    ``([], 0)`` rather than raising — the projector treats the file
    as plain narrative in that case.
    """
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        return [], 0
    headers = [cell.strip() for cell in lines[0].strip().strip("|").split("|")]
    headers = [h for h in headers if h]
    rest = lines[1:]
    # Skip a separator row ("|---|---|").
    if re.fullmatch(r"\|?\s*[:\-\s|]+\|?", rest[0]):
        rest = rest[1:]
    return headers, len(rest)


@dataclass
class _ClaimBlock:
    """One parsed ARA Cxx block from ``logic/claims.md``.

    Fields:
        cid: ARA identifier, e.g. ``"C01"``.
        heading: The text after ``## Cxx:`` on the heading line, used
            as the Gaia :attr:`Knowledge.title`. Usually a short
            sentence the paper uses to name the claim.
        content: The narrative body of the claim — paragraphs that
            follow the heading, with the structured ``Status:`` /
            ``Proof:`` / ``Reference:`` lines stripped out. Used as
            the Gaia :attr:`Knowledge.content`. Falls back to the
            heading itself when the body is empty.
        status: Lowercased value of the ``Status:`` line, if present.
        proof_refs: Evidence IDs from ``Proof: [Exx, Eyy]``.
        refutes: Optional list of other claim ids from a
            ``Refutes: [Cxx]`` line — used to seed contradict()
            queue candidates per spec §7.1.
    """

    cid: str
    heading: str
    content: str
    status: str | None
    proof_refs: list[str]
    refutes: list[str]


@dataclass
class _ExperimentBlock:
    """One parsed ARA Exx block from ``logic/experiments.md``.

    Ara paper §2.2 names this layer's purpose: ``experiments.md
    declares the verification plan``. Each experiment carries a
    ``Verifies:`` pointer back to one or more claims plus a
    ``Procedure`` and an ``Expected outcome``; the claim → experiment
    → evidence chain is what the paper calls the **forensic binding
    chain** (``every claim's proof chain flows claims.md →
    experiments.md → /evidence/``, §2.2 Evidence Layer).

    Fields:
        eid: ARA identifier, e.g. ``"E01"``.
        heading: Short title from the ``## Exx:`` line.
        content: Narrative body with the structured ``Verifies:`` /
            ``Procedure:`` / ``Expected outcome:`` lines stripped.
        verifies: Claim ids the experiment is the verification plan
            for, parsed from the ``Verifies: [C01, C02]`` line.
        procedure: Optional text from the ``Procedure:`` line — short
            recipe ("compute X on dataset Y").
        expected_outcome: Optional text from ``Expected outcome:`` —
            the directional prediction without revealing exact
            numbers (Ara §2.2 keeps numbers in /evidence only).
        evidence_refs: Optional file paths from ``Evidence:`` or
            ``Results:`` lines pointing at ``evidence/`` files; lets
            the projector build the experiment → evidence segment of
            the chain when the author was explicit.
    """

    eid: str
    heading: str
    content: str
    verifies: list[str]
    procedure: str | None
    expected_outcome: str | None
    evidence_refs: list[str]


@dataclass
class _RelatedWorkBlock:
    """One parsed ARA RWxx block from ``logic/related_work.md``."""

    rid: str
    title: str
    type_: str | None
    external_ids: list[str]


# A Cxx block header looks like "## C01: Some claim text" (with or without
# the colon, or as a section followed by status / proof lines).
_CLAIM_HEADING_RE = re.compile(r"^#{1,6}\s+(C\d+)\s*[:.\-—]\s*(.+?)\s*$", re.MULTILINE)
_STATUS_LINE_RE = re.compile(r"^Status\s*[:\-]\s*(\w+)\s*$", re.IGNORECASE | re.MULTILINE)
_PROOF_LINE_RE = re.compile(r"^Proof\s*[:\-]\s*\[([^\]]+)\]\s*$", re.IGNORECASE | re.MULTILINE)
_REFUTES_LINE_RE = re.compile(r"^Refutes\s*[:\-]\s*\[([^\]]+)\]\s*$", re.IGNORECASE | re.MULTILINE)
# Match any "Key: value" line we recognise so we can strip them from
# the body before treating what's left as narrative content.
_STRUCTURED_LINE_RE = re.compile(
    r"^(?:Status|Proof|Refutes|Reference|References|Tags?|Verifies|Procedure|Expected\s+outcome|Evidence|Results|Falsification)\s*[:\-].*$",
    re.IGNORECASE | re.MULTILINE,
)

_EXPERIMENT_HEADING_RE = re.compile(
    r"^#{1,6}\s+(E\d+)\s*[:.\-—]\s*(.+?)\s*$",
    re.MULTILINE,
)
_VERIFIES_LINE_RE = re.compile(
    r"^Verifies\s*[:\-]\s*\[([^\]]+)\]\s*$", re.IGNORECASE | re.MULTILINE
)
_PROCEDURE_LINE_RE = re.compile(r"^Procedure\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_EXPECTED_OUTCOME_LINE_RE = re.compile(
    r"^Expected\s+outcome\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
# Either `Evidence: [a.md, b.md]` (bracket list) or `Results: a.md` (single).
_EVIDENCE_REF_LINE_RE = re.compile(
    r"^(?:Evidence|Results)\s*[:\-]\s*(?:\[([^\]]+)\]|(\S.*?))\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_id_list(raw: str) -> list[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def _parse_experiments_md(text: str) -> list[_ExperimentBlock]:
    """Parse ``logic/experiments.md`` into ordered ``Exx`` blocks.

    Shape per Ara paper §2.2 + Appendix examples:

    .. code-block:: markdown

        ## E01: Verify that residual blocks help deep nets
        Verifies: [C02]
        Procedure: train plain-18 vs residual-18 on ImageNet for 90 epochs
        Expected outcome: residual top-1 >= plain top-1 at every depth
        Evidence: [evidence/tables/table2.md]

        Optional narrative body explaining the experimental setup.

    Each field is optional — ``Verifies:`` missing just means the
    experiment is not yet linked to a claim and the resulting
    ``_ExperimentBlock.verifies`` is empty.
    """
    blocks: list[_ExperimentBlock] = []
    matches = list(_EXPERIMENT_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_text = text[start:end].strip()

        verifies_match = _VERIFIES_LINE_RE.search(block_text)
        verifies = _parse_id_list(verifies_match.group(1)) if verifies_match else []

        procedure_match = _PROCEDURE_LINE_RE.search(block_text)
        procedure = procedure_match.group(1).strip() if procedure_match else None

        expected_match = _EXPECTED_OUTCOME_LINE_RE.search(block_text)
        expected_outcome = expected_match.group(1).strip() if expected_match else None

        evidence_refs: list[str] = []
        for ev_match in _EVIDENCE_REF_LINE_RE.finditer(block_text):
            bracket_form = ev_match.group(1)
            single_form = ev_match.group(2)
            if bracket_form is not None:
                evidence_refs.extend(_parse_id_list(bracket_form))
            elif single_form is not None:
                token = single_form.strip()
                if token:
                    evidence_refs.append(token)

        cleaned = _STRUCTURED_LINE_RE.sub("", block_text).strip()
        heading = match.group(2).strip()
        content = cleaned if cleaned else heading

        blocks.append(
            _ExperimentBlock(
                eid=match.group(1),
                heading=heading,
                content=content,
                verifies=verifies,
                procedure=procedure,
                expected_outcome=expected_outcome,
                evidence_refs=evidence_refs,
            )
        )
    return blocks


def _parse_claims_md(text: str) -> list[_ClaimBlock]:
    """Parse ``logic/claims.md`` into ordered claim blocks.

    The format is markdown-with-conventions: each claim is a section
    headed by ``## Cxx: <heading>``, optionally followed by
    ``Status:`` / ``Proof:`` / ``Refutes:`` structured lines and
    then a narrative body of one or more paragraphs.

    The structured lines are extracted into typed fields; what's left
    after their removal is treated as the narrative ``content`` (the
    actual scientific assertion). This split matters because the
    Gaia :func:`claim` expects ``content`` to be the assertion text
    and ``title`` to be a short label — duplicating the heading into
    both fields, as the previous draft did, lost the distinction.
    """
    blocks: list[_ClaimBlock] = []
    matches = list(_CLAIM_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block_text = text[start:end].strip()

        status_match = _STATUS_LINE_RE.search(block_text)
        proof_match = _PROOF_LINE_RE.search(block_text)
        refutes_match = _REFUTES_LINE_RE.search(block_text)
        proof_refs = _parse_id_list(proof_match.group(1)) if proof_match else []
        refutes = _parse_id_list(refutes_match.group(1)) if refutes_match else []

        # Body = the paragraphs left after the structured lines have
        # been stripped. Empty body → fall back to heading text.
        cleaned = _STRUCTURED_LINE_RE.sub("", block_text).strip()
        heading = match.group(2).strip()
        content = cleaned if cleaned else heading

        blocks.append(
            _ClaimBlock(
                cid=match.group(1),
                heading=heading,
                content=content,
                status=status_match.group(1).strip().lower() if status_match else None,
                proof_refs=proof_refs,
                refutes=refutes,
            )
        )
    return blocks


def _parse_related_work_md(text: str) -> list[_RelatedWorkBlock]:
    """Parse ``logic/related_work.md`` into RWxx blocks."""
    blocks: list[_RelatedWorkBlock] = []
    for match in _RW_BLOCK_RE.finditer(text):
        rid, title, body = match.group(1), match.group(2).strip(), match.group(3)
        type_match = re.search(r"^Type\s*[:\-]\s*(\w+)\s*$", body, re.IGNORECASE | re.MULTILINE)
        ids_match = re.search(
            r"^IDs?\s*[:\-]\s*\[([^\]]+)\]\s*$", body, re.IGNORECASE | re.MULTILINE
        )
        external_ids: list[str] = []
        if ids_match:
            for token in ids_match.group(1).split(","):
                token = token.strip()
                if token:
                    external_ids.append(token)
        blocks.append(
            _RelatedWorkBlock(
                rid=rid,
                title=title,
                type_=type_match.group(1).strip().lower() if type_match else None,
                external_ids=external_ids,
            )
        )
    return blocks


def _ara_label(cid: str) -> str:
    return f"ara_{cid.lower()}"


def _experiment_label(eid: str) -> str:
    """Label convention for ``logic/experiments.md`` Exx blocks.

    Distinct namespace from claims (``ara_cXX``) and evidence
    (``ara_evidence_*``) so cross-module imports never collide.
    """
    return f"ara_experiment_{eid.lower()}"


def _rw_label(rid: str) -> str:
    return f"ara_rw_{rid.lower()}"


def _evidence_label(rel: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", Path(rel).with_suffix("").as_posix().lower()).strip("_")
    return f"ara_evidence_{safe}"


_INIT_BODY = '''\
"""Deterministic ARA projection root.

Generated by `gaia build init --embedded` / `gaia pkg mount`.
Re-export every projected fragment so the embedded loader picks them
up through `__all__` and stamps them as exported in IR.
"""

from .claims import *  # noqa: F401,F403
from .evidence import *  # noqa: F401,F403
from .experiments import *  # noqa: F401,F403
from .narrative import *  # noqa: F401,F403
from .paper import *  # noqa: F401,F403
from .related_work import *  # noqa: F401,F403
from .trace import *  # noqa: F401,F403

from .claims import __all__ as _claims_all
from .evidence import __all__ as _evidence_all
from .experiments import __all__ as _experiments_all
from .narrative import __all__ as _narrative_all
from .paper import __all__ as _paper_all
from .related_work import __all__ as _rw_all
from .trace import __all__ as _trace_all

__all__ = [
    *_paper_all,
    *_claims_all,
    *_experiments_all,
    *_evidence_all,
    *_narrative_all,
    *_rw_all,
    *_trace_all,
]
'''


def _slug(text: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return safe or "x"


def _read_text_or_empty(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _truncate(text: str, limit: int = 400) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "\u2026"


def _render_paper_module(
    paper_path_rel: str,
    metadata: dict[str, Any],
    abstract: str,
) -> str:
    """Render ``gaia/from_ara/paper.py`` from PAPER.md frontmatter + body."""
    if not metadata and not abstract:
        statements = [
            render_call_statement(
                target_label="ara_paper_placeholder",
                func_name="note",
                positional=["PAPER.md is absent — no ARA paper identity captured."],
            )
        ]
        labels = ["ara_paper_placeholder"]
    else:
        title = metadata.get("title") or "ARA paper"
        statements = [
            render_call_statement(
                target_label="ara_paper",
                func_name="note",
                positional=[abstract or f"ARA paper: {title}"],
                keywords={
                    "metadata": {
                        "ara_source": paper_path_rel,
                        "ara_paper_metadata": {k: v for k, v in metadata.items() if v is not None},
                    }
                },
            )
        ]
        labels = ["ara_paper"]
    return render_module(
        docstring="Deterministic projection of `PAPER.md` (frontmatter + abstract).",
        engine_imports=("note",),
        statements=statements,
        all_labels=labels,
    )


def _render_narrative_module(entries: list[tuple[str, str, str]]) -> str:
    """Render ``gaia/from_ara/narrative.py`` from problem/experiments notes.

    ``entries`` is a list of ``(label, source_path, body)`` tuples,
    typically one per ``logic/problem.md`` and ``logic/experiments.md``
    file actually present in the host.
    """
    statements: list[str] = []
    labels: list[str] = []
    for label, source_path, body in entries:
        labels.append(label)
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="note",
                positional=[_truncate(body)],
                keywords={"metadata": {"ara_source": source_path}},
            )
        )
    if not entries:
        labels.append("_ara_narrative_placeholder")
        statements.append(
            render_call_statement(
                target_label="_ara_narrative_placeholder",
                func_name="note",
                positional=["No ARA narrative files (problem.md, experiments.md) found."],
            )
        )
    return render_module(
        docstring=(
            "Deterministic projection of narrative ARA files "
            "(`logic/problem.md`, `logic/experiments.md`)."
        ),
        engine_imports=("note",),
        statements=statements,
        all_labels=labels,
    )


def _render_experiments_module(
    experiments_path: Path,
    blocks: list[_ExperimentBlock],
    *,
    resolvable_evidence_refs: set[str] | None = None,
) -> str:
    """Render ``gaia/from_ara/experiments.py`` as one note per Exx block.

    Each experiment is a ``note(...)`` so it sits between the claim
    (Cognitive Layer) and the evidence (Evidence Layer) — i.e. the
    middle hop of the ``claims.md → experiments.md → /evidence/``
    forensic binding chain the Ara paper §2.2 defines.

    The ``Verifies:`` list and the optional ``Procedure:`` / ``Expected
    outcome:`` / ``Evidence:`` fields are written into the note's
    metadata so an agent or reviewer can iterate without re-parsing
    the original markdown.

    When ``resolvable_evidence_refs`` is supplied the renderer also
    emits ``depends_on(experiment, given=[evidence_file])`` edges for
    each ``Evidence:`` ref that resolves to a real file under
    ``evidence/`` — this completes the experiment → evidence segment
    of the forensic chain. Refs that do NOT resolve to a real file
    are kept in ``metadata['ara_evidence_refs']`` only (no fabricated
    edges into thin air).

    Empty experiments.md (or absent file) still produces a valid
    placeholder so the module is importable and the synthetic loader's
    re-export chain stays connected.
    """
    resolvable_evidence_refs = resolvable_evidence_refs or set()
    statements: list[str] = []
    labels: list[str] = []
    referenced_evidence_labels: list[str] = []
    seen_evidence_labels: set[str] = set()
    for block in blocks:
        label = _experiment_label(block.eid)
        labels.append(label)
        metadata: dict[str, Any] = {
            "ara_id": block.eid,
            "ara_source": f"{experiments_path.as_posix()}#{block.eid}",
            # Distinguish experiments from falsifiable scientific
            # claims in the IR. We MUST use claim() here (not note())
            # because depends_on / infer / derive all require Claim
            # arguments — that is the only Gaia knowledge type that
            # participates in dependency edges. A reviewer reading
            # the IR uses this `ara_kind` flag to tell the two apart.
            "ara_kind": "verification_plan",
        }
        if block.verifies:
            metadata["ara_verifies"] = list(block.verifies)
        if block.procedure is not None:
            metadata["ara_procedure"] = block.procedure
        if block.expected_outcome is not None:
            metadata["ara_expected_outcome"] = block.expected_outcome
        if block.evidence_refs:
            metadata["ara_evidence_refs"] = list(block.evidence_refs)
        keywords: dict[str, Any] = {"metadata": metadata}
        if block.heading and block.heading != block.content:
            keywords["title"] = block.heading
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="claim",
                positional=[block.content],
                keywords=keywords,
            )
        )
        # experiment -> evidence segment of the forensic chain.
        for ref in block.evidence_refs:
            if ref not in resolvable_evidence_refs:
                continue
            ev_label = _evidence_label(ref)
            if ev_label not in seen_evidence_labels:
                seen_evidence_labels.add(ev_label)
                referenced_evidence_labels.append(ev_label)
            link_label = f"{label}_depends_on_{ev_label[len('ara_evidence_') :]}"
            labels.append(link_label)
            statements.append(
                render_call_statement(
                    target_label=link_label,
                    func_name="depends_on",
                    positional=[Ref(label)],
                    keywords={
                        "given": [Ref(ev_label)],
                        "rationale": (
                            f"ARA experiment {block.eid} cites evidence file `{ref}`; "
                            "the projector connects experiment -> evidence as the second "
                            "hop of the forensic chain without classifying the warrant "
                            "type."
                        ),
                        "metadata": {
                            "projection_confidence": "programmatic",
                            "ara_evidence_ref": ref,
                        },
                    },
                )
            )
    if not blocks:
        labels.append("_ara_experiments_placeholder")
        statements.append(
            render_call_statement(
                target_label="_ara_experiments_placeholder",
                func_name="note",
                positional=["No Exx blocks parsed from logic/experiments.md."],
            )
        )
    extra_imports: tuple[str, ...] = ()
    if referenced_evidence_labels:
        extra_imports = (f"from .evidence import {', '.join(sorted(referenced_evidence_labels))}",)
    engine_imports = (
        ("claim", "depends_on", "note") if referenced_evidence_labels else ("claim", "note")
    )
    return render_module(
        docstring=(
            "Deterministic projection of `logic/experiments.md` Exx blocks.\n\n"
            "Each Exx becomes a `note(...)` carrying the Verifies / "
            "Procedure / Expected outcome / Evidence fields as metadata. "
            "This module is the middle hop of the Ara forensic binding "
            "chain claims.md -> experiments.md -> /evidence/."
        ),
        engine_imports=engine_imports,
        extra_imports=extra_imports,
        statements=statements,
        all_labels=labels,
    )


def _render_trace_module(entries: list[dict[str, Any]]) -> str:
    """Render ``gaia/from_ara/trace.py`` from ``trace/exploration_tree.yaml`` dead_ends."""
    statements: list[str] = []
    labels: list[str] = []
    for entry in entries:
        label = entry["label"]
        labels.append(label)
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="note",
                positional=[entry["text"]],
                keywords={
                    "metadata": {
                        "ara_trace_node_id": entry["node_id"],
                        "ara_source": entry["source"],
                        "ara_trace_kind": "dead_end",
                    }
                },
            )
        )
    if not entries:
        labels.append("_ara_trace_placeholder")
        statements.append(
            render_call_statement(
                target_label="_ara_trace_placeholder",
                func_name="note",
                positional=["No ARA trace dead-end branches found."],
            )
        )
    return render_module(
        docstring=(
            "Deterministic projection of `trace/exploration_tree.yaml` "
            "dead-end branches (spec §7.1)."
        ),
        engine_imports=("note",),
        statements=statements,
        all_labels=labels,
    )


def _parse_dead_ends(text: str) -> list[dict[str, str]]:
    """Pull ``dead_end`` nodes out of a simple ``exploration_tree.yaml``.

    Recognises the textual shape:

    .. code-block:: yaml

        - id: T01
          dead_end: true
          note: "Why we stopped this branch."

    Avoids adding a PyYAML dependency by walking the file
    line-by-line. Shapes more complex than this are best handled by
    the future `--formalize` step.
    """
    nodes: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current.get("dead_end") == "true":
                nodes.append(current)
            current = {}
            stripped = stripped[2:].strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in {"id", "node_id"}:
            current["node_id"] = value
        elif key == "dead_end":
            current["dead_end"] = value
        elif key in {"note", "reason", "rationale"}:
            current["note"] = value
    if current.get("dead_end") == "true":
        nodes.append(current)
    return nodes


def _render_claim_module(  # noqa: C901 — branchy due to three-segment vs two-segment fallback
    claims_path: Path,
    blocks: list[_ClaimBlock],
    *,
    experiment_eids: set[str] | None = None,
) -> str:
    """Render the ``gaia/from_ara/claims.py`` module body.

    Cross-module wiring is driven by whether the host has an
    ``experiments.md`` block for the referenced Exx:

    - **Three-segment chain** (``claims.md → experiments.md →
      evidence/`` per Ara paper §2.2): when the referenced Exx IS
      defined in experiments.md, this module imports the experiment
      label from ``.experiments`` and emits
      ``depends_on(claim, given=[experiment])``. The
      experiment → evidence segment is emitted by
      :func:`_render_experiments_module` so the whole chain stays
      connected.

    - **Two-segment fallback** (``claims.md → evidence/`` direct):
      when the referenced Exx is NOT defined in experiments.md (or
      the file is absent), this module imports the placeholder
      evidence label from ``.evidence`` and emits
      ``depends_on(claim, given=[evidence_placeholder])`` like the
      pre-experiments-aware version. This keeps minimal-ARA hosts
      (no experiments.md) working unchanged.
    """
    experiment_eids = experiment_eids or set()
    evidence_labels: list[str] = []
    experiment_labels: list[str] = []
    seen_evidence: set[str] = set()
    seen_experiments: set[str] = set()
    for block in blocks:
        for eid in block.proof_refs:
            if eid in experiment_eids:
                label = _experiment_label(eid)
                if label not in seen_experiments:
                    seen_experiments.add(label)
                    experiment_labels.append(label)
            else:
                label = _evidence_label(eid)
                if label not in seen_evidence:
                    seen_evidence.add(label)
                    evidence_labels.append(label)

    statements: list[str] = []
    labels: list[str] = []
    for block in blocks:
        label = _ara_label(block.cid)
        labels.append(label)
        metadata: dict[str, Any] = {
            "ara_id": block.cid,
            "ara_source": f"{claims_path.as_posix()}#{block.cid}",
        }
        if block.status:
            metadata["ara_status"] = block.status
        if block.refutes:
            metadata["ara_refutes"] = list(block.refutes)
        # heading vs content: heading is the short label from
        # ``## Cxx:``, content is the narrative body. When the body
        # is empty we already fell back to heading in _parse_claims_md.
        keywords: dict[str, Any] = {"metadata": metadata}
        if block.heading and block.heading != block.content:
            keywords["title"] = block.heading
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="claim",
                positional=[block.content],
                keywords=keywords,
            )
        )
        for eid in block.proof_refs:
            link_label = f"{label}_depends_on_{eid.lower()}"
            labels.append(link_label)
            # Pick the target by whether the host has an Exx block for
            # this id. With experiments.md: three-segment chain via
            # the experiment label; without: two-segment direct to the
            # evidence placeholder.
            if eid in experiment_eids:
                target_ref = Ref(_experiment_label(eid))
                rationale = (
                    f"ARA {block.cid} cites {eid} (defined in logic/experiments.md); "
                    "the projector connects claim -> experiment as the first hop of "
                    "the claims.md -> experiments.md -> /evidence/ forensic chain "
                    "without classifying the warrant type."
                )
            else:
                target_ref = Ref(_evidence_label(eid))
                rationale = (
                    f"ARA {block.cid} cites {eid}, but the projector does not "
                    "classify the warrant type."
                )
            statements.append(
                render_call_statement(
                    target_label=link_label,
                    func_name="depends_on",
                    positional=[Ref(label)],
                    keywords={
                        "given": [target_ref],
                        "rationale": rationale,
                        "metadata": {"projection_confidence": "programmatic"},
                    },
                )
            )
    if not blocks:
        statements.append(
            render_call_statement(
                target_label="_ara_claims_placeholder",
                func_name="note",
                positional=["No Cxx blocks parsed from logic/claims.md."],
            )
        )
        labels.append("_ara_claims_placeholder")

    extra_imports_list: list[str] = []
    if evidence_labels:
        extra_imports_list.append(f"from .evidence import {', '.join(evidence_labels)}")
    if experiment_labels:
        extra_imports_list.append(f"from .experiments import {', '.join(experiment_labels)}")
    return render_module(
        docstring="Deterministic projection of `logic/claims.md` Cxx blocks.",
        engine_imports=("claim", "depends_on", "note"),
        extra_imports=tuple(extra_imports_list),
        statements=statements,
        all_labels=labels,
    )


def _render_evidence_module(
    host: Path,
    evidence_files: list[Path],
    referenced_eids: list[str],
) -> str:
    """Render ``gaia/from_ara/evidence.py`` as an ``observe(...)`` collection.

    Two sources feed the module:

    1. Actual files under ``evidence/`` — projected as ``observe(...)``
       with ``source_refs=[<host-relative path>]``.
    2. ``Exx`` IDs referenced from ``logic/claims.md`` ``Proof: [Exx]``
       lines that do **not** have a matching file. Each gets a stub
       ``observe(...)`` so the ``depends_on`` records in ``claims.py``
       can reference it without an unresolved name. Spec §11
       guarantees deterministic output, and the stub keeps that
       guarantee even when the host's evidence folder is partial.
    """
    statements: list[str] = []
    labels: list[str] = []
    emitted: set[str] = set()

    for ev in evidence_files:
        rel = ev.relative_to(host).as_posix()
        label = _evidence_label(rel)
        if label in emitted:
            continue
        emitted.add(label)
        labels.append(label)
        # Try to pull markdown-table structure out so the generated
        # observe() rationale describes column shape. For non-table
        # files (csv, json, plain text) we fall back to the generic
        # stub. Table structure (headers, row count) is also written
        # into the source_map record so downstream tooling can read it
        # without re-parsing the file.
        content_line = (
            f"Evidence file `{rel}` reports a result. Replace this stub with a "
            "numeric observation once the table is parsed."
        )
        rationale_line = "Programmatic projection of an ARA evidence file."
        if ev.suffix.lower() == ".md":
            try:
                headers, row_count = _parse_pipe_table_columns(ev.read_text(encoding="utf-8"))
            except OSError:
                headers, row_count = [], 0
            if headers:
                content_line = (
                    f"Evidence table `{rel}` with columns "
                    f"{', '.join(headers)} ({row_count} body rows). Replace this "
                    "stub with a structured observation once the table is parsed."
                )
                rationale_line = (
                    f"Programmatic projection of an ARA evidence table "
                    f"(columns={headers}, rows={row_count})."
                )
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="observe",
                positional=[content_line],
                keywords={
                    "source_refs": [rel],
                    "rationale": rationale_line,
                },
            )
        )

    for eid in referenced_eids:
        label = _evidence_label(eid)
        if label in emitted:
            continue
        emitted.add(label)
        labels.append(label)
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="observe",
                positional=[
                    f"ARA evidence reference `{eid}` cited from logic/claims.md. "
                    "No matching file under evidence/ — replace with a structured "
                    "observation once the source is resolved."
                ],
                keywords={
                    "source_refs": [f"logic/claims.md#{eid}"],
                    "rationale": ("Programmatic placeholder for an unresolved ARA evidence id."),
                },
            )
        )

    if not labels:
        labels.append("_ara_evidence_placeholder")
        statements.append(
            render_call_statement(
                target_label="_ara_evidence_placeholder",
                func_name="note",
                positional=["No ARA evidence files found."],
            )
        )

    return render_module(
        docstring="Deterministic projection of `evidence/` files into `observe(...)` records.",
        engine_imports=("note", "observe"),
        statements=statements,
        all_labels=labels,
    )


# Mapping from related_work `Type:` to richer projection metadata. Per
# Ara paper §2.2: "imports inject prior definitions, bounds propagate
# constraints to hyperparameter search, and baseline entries enable
# automatic regression detection". `extends` is paper-style "builds on";
# `refutes` is the contradict candidate. Unknown types fall back to the
# generic source_only scholarly reference.
_RELATED_WORK_TYPE_KIND: dict[str, str] = {
    "imports": "dependency",
    "extends": "dependency",
    "bounds": "dependency_with_constraints",
    "baseline": "baseline",
    "refutes": "candidate_contradict",
}


def _related_work_kind(type_: str | None) -> str:
    if not isinstance(type_, str):
        return "source_only"
    return _RELATED_WORK_TYPE_KIND.get(type_.lower(), "source_only")


def _render_related_work_module(rw_path: Path | None, blocks: list[_RelatedWorkBlock]) -> str:
    """Render ``gaia/from_ara/related_work.py``.

    Per spec §14.1, ARA related-work entries are **not** automatically
    Gaia package references. We project them as ``note(...)`` records
    carrying the ``Type``/``IDs`` metadata plus a derived
    ``related_work_kind`` field (see :data:`_RELATED_WORK_TYPE_KIND`)
    so an agent or reviewer can branch on the typed-edge semantics
    Ara §2.2 describes without re-parsing the ``Type:`` string. An
    explicit ``gaia pkg add`` is still the only path to a real
    registry binding.
    """
    del rw_path  # path only enters as a comment; nothing structural to do
    statements: list[str] = []
    labels: list[str] = []
    for block in blocks:
        label = _rw_label(block.rid)
        labels.append(label)
        kind = _related_work_kind(block.type_)
        metadata: dict[str, Any] = {
            "ara_rw_id": block.rid,
            "registry_binding_state": "source_only",
            "related_work_kind": kind,
        }
        if block.type_:
            metadata["related_work_type"] = block.type_
        if block.external_ids:
            metadata["external_ids"] = list(block.external_ids)
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="note",
                positional=[block.title],
                keywords={"metadata": metadata},
            )
        )
    if not blocks:
        labels.append("_ara_rw_placeholder")
        statements.append(
            render_call_statement(
                target_label="_ara_rw_placeholder",
                func_name="note",
                positional=["No RWxx blocks found in logic/related_work.md."],
            )
        )

    return render_module(
        docstring=(
            "Deterministic projection of `logic/related_work.md` RWxx entries.\n\n"
            "See spec §14.1: scholarly references are NOT auto-converted to "
            "`gaia pkg add` dependencies — the projector emits notes only."
        ),
        engine_imports=("note",),
        statements=statements,
        all_labels=labels,
    )


def project_ara(host: Path, *, seeds: list[Path]) -> ProjectionResult:  # noqa: C901
    """Project an ARA host into Gaia DSL.

    Always emits four files under ``gaia/from_ara/``:
    ``__init__.py``, ``claims.py``, ``evidence.py``,
    ``related_work.py``. Even when a section is empty (no claims, no
    tables) we emit a placeholder ``note(...)`` so the module is
    importable and the embedded loader has a non-empty package to
    walk.

    Explicit ``seeds`` (user-named host files) are projected through
    the generic ``note(...)`` rule on top of the ARA-native output,
    matching the spec §11 algorithm — the deterministic rules run
    first, the seeds add scaffold-mode follow-ups for anything the
    typed rules did not cover.
    """
    files: list[GeneratedFile] = []
    source_map: list[SourceMapRecord] = []
    queue: list[QueueItem] = []

    files.append(GeneratedFile(path="gaia/from_ara/__init__.py", body=_INIT_BODY))

    # ---- PAPER.md frontmatter --------------------------------------- #
    paper_path_rel = "PAPER.md"
    paper_text = _read_text_or_empty(host / paper_path_rel)
    paper_meta, paper_body = _parse_paper_frontmatter(paper_text)
    files.append(
        GeneratedFile(
            path="gaia/from_ara/paper.py",
            body=_render_paper_module(paper_path_rel, paper_meta, _truncate(paper_body)),
        )
    )
    if paper_text:
        source_map.append(
            SourceMapRecord(
                source_id="ARA:PAPER",
                source_path=paper_path_rel,
                gaia_label="ara_paper",
                gaia_record_kind="note",
                generated_file="gaia/from_ara/paper.py",
                projection_rule="ara.paper_md.v1",
                requires_review=False,
                extras={"frontmatter_keys": sorted(paper_meta)},
            )
        )

    # ---- logic/experiments.md (Exx blocks) -------------------------- #
    # Parsed FIRST so the claim renderer knows which Proof: ids
    # have an experiment block — when they do, the claim links to
    # the experiment (three-segment chain); when they don't, it
    # falls back to linking directly to an evidence placeholder.
    experiments_path_rel = "logic/experiments.md"
    experiments_path = host / experiments_path_rel
    experiment_blocks: list[_ExperimentBlock] = []
    if experiments_path.is_file():
        experiment_blocks = _parse_experiments_md(experiments_path.read_text(encoding="utf-8"))
    experiment_eids = {b.eid for b in experiment_blocks}
    # Discover which Evidence: refs from experiments actually exist
    # on disk under evidence/ so we only emit experiment->evidence
    # depends_on edges for resolvable targets (no fabricated edges).
    resolvable_evidence_refs: set[str] = set()
    evidence_dir_for_exp = host / "evidence"
    if evidence_dir_for_exp.is_dir() and experiment_blocks:
        on_disk = {
            p.relative_to(host).as_posix() for p in evidence_dir_for_exp.rglob("*") if p.is_file()
        }
        for exp in experiment_blocks:
            for ref in exp.evidence_refs:
                if ref in on_disk:
                    resolvable_evidence_refs.add(ref)
    files.append(
        GeneratedFile(
            path="gaia/from_ara/experiments.py",
            body=_render_experiments_module(
                Path(experiments_path_rel),
                experiment_blocks,
                resolvable_evidence_refs=resolvable_evidence_refs,
            ),
        )
    )

    claims_path_rel = "logic/claims.md"
    claims_path = host / claims_path_rel
    claim_blocks: list[_ClaimBlock] = []
    if claims_path.is_file():
        claim_blocks = _parse_claims_md(claims_path.read_text(encoding="utf-8"))
    files.append(
        GeneratedFile(
            path="gaia/from_ara/claims.py",
            body=_render_claim_module(
                Path(claims_path_rel),
                claim_blocks,
                experiment_eids=experiment_eids,
            ),
        )
    )
    for index, block in enumerate(claim_blocks, start=1):
        label = _ara_label(block.cid)
        flagged_for_review = block.status == "refuted" or bool(block.refutes)
        extras: dict[str, Any] = {}
        if block.status:
            extras["ara_status"] = block.status
        if block.refutes:
            extras["ara_refutes"] = list(block.refutes)
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:{block.cid}",
                source_path=claims_path_rel,
                source_anchor=block.cid,
                gaia_label=label,
                gaia_record_kind="claim",
                generated_file="gaia/from_ara/claims.py",
                projection_rule="ara.claim_block.v1",
                requires_review=flagged_for_review,
                queue_id=f"FQC{index:03d}" if flagged_for_review else None,
                extras=extras,
            )
        )
        if flagged_for_review:
            reason_parts: list[str] = []
            if block.status == "refuted":
                reason_parts.append(
                    "ARA claim is marked Status: refuted; reviewer must decide "
                    "whether to materialise a contradict() against the refuter."
                )
            if block.refutes:
                reason_parts.append(
                    "ARA claim explicitly refutes: "
                    + ", ".join(block.refutes)
                    + " — propose contradict() between this claim and each target."
                )
            queue.append(
                QueueItem(
                    queue_id=f"FQC{index:03d}",
                    source_id=f"ARA:{block.cid}",
                    source_refs=[f"{claims_path_rel}#{block.cid}"]
                    + [f"{claims_path_rel}#{rid}" for rid in block.refutes],
                    current_gaia_record=label,
                    current_action="claim",
                    candidate_actions=["contradict", "exclusive"],
                    reason_review_needed=" ".join(reason_parts) or "Refuted ARA claim.",
                )
            )
        for j, eid in enumerate(block.proof_refs, start=1):
            link_label = f"{label}_depends_on_{eid.lower()}"
            qid = f"FQP{index:03d}{j}"
            target_is_experiment = eid in experiment_eids
            if target_is_experiment:
                projection_rule = "ara.claim_proof_experiment_chain.v1"
                source_refs = [
                    f"{claims_path_rel}#{block.cid}",
                    f"{experiments_path_rel}#{eid}",
                ]
                reason = (
                    "ARA Proof links claim to its verification experiment; reviewer "
                    "must classify the claim<-experiment warrant type."
                )
            else:
                projection_rule = "ara.claim_proof_scaffold.v1"
                source_refs = [
                    f"{claims_path_rel}#{block.cid}",
                    f"evidence/{eid}",
                ]
                reason = "ARA Proof links evidence to claim but does not classify warrant type."
            source_map.append(
                SourceMapRecord(
                    source_id=f"ARA:{block.cid}->{eid}",
                    source_path=claims_path_rel,
                    source_anchor=f"{block.cid}.Proof",
                    gaia_label=link_label,
                    gaia_record_kind="depends_on",
                    generated_file="gaia/from_ara/claims.py",
                    projection_rule=projection_rule,
                    requires_review=True,
                    queue_id=qid,
                )
            )
            queue.append(
                QueueItem(
                    queue_id=qid,
                    source_id=f"ARA:{block.cid}->{eid}",
                    source_refs=source_refs,
                    current_gaia_record=link_label,
                    current_action="depends_on",
                    candidate_actions=["infer", "derive"],
                    reason_review_needed=reason,
                )
            )

    # ---- experiments.md source_map records ------------------------- #
    # One source_map record per Exx; the experiment->evidence
    # depends_on edges themselves are emitted by
    # _render_experiments_module (above). Together they close the
    # claim -> experiment -> evidence forensic chain in the IR
    # without committing any warrant type.
    for exp in experiment_blocks:
        exp_label = _experiment_label(exp.eid)
        # gaia_record_kind = "claim" because experiments are projected
        # as claim() with metadata.ara_kind = "verification_plan" so
        # they can participate in depends_on / infer / derive edges.
        # See _render_experiments_module for the rationale.
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:EXPERIMENT:{exp.eid}",
                source_path=experiments_path_rel,
                source_anchor=exp.eid,
                gaia_label=exp_label,
                gaia_record_kind="claim",
                generated_file="gaia/from_ara/experiments.py",
                projection_rule="ara.experiment_block.v1",
                requires_review=False,
                extras={
                    "ara_kind": "verification_plan",
                    "ara_verifies": list(exp.verifies),
                    "ara_evidence_refs": list(exp.evidence_refs),
                },
            )
        )

    evidence_dir = host / "evidence"
    evidence_files: list[Path] = []
    if evidence_dir.is_dir():
        evidence_files = sorted(
            p
            for p in evidence_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".csv", ".tsv", ".json", ".txt"}
        )
    # Only emit a placeholder evidence stub for Exx that DON'T have
    # an experiment block — those that do are already wired through
    # the three-segment chain (claim -> experiment[-> evidence]).
    # Exx without an experiment block keep the two-segment fallback
    # (claim -> evidence placeholder).
    referenced_eids: list[str] = []
    seen_eids: set[str] = set()
    for block in claim_blocks:
        for eid in block.proof_refs:
            if eid in experiment_eids:
                continue
            if eid not in seen_eids:
                seen_eids.add(eid)
                referenced_eids.append(eid)
    files.append(
        GeneratedFile(
            path="gaia/from_ara/evidence.py",
            body=_render_evidence_module(host, evidence_files, referenced_eids),
        )
    )
    for ev in evidence_files:
        rel = ev.relative_to(host).as_posix()
        label = _evidence_label(rel)
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:EVIDENCE:{rel}",
                source_path=rel,
                gaia_label=label,
                gaia_record_kind="observe",
                generated_file="gaia/from_ara/evidence.py",
                projection_rule="ara.evidence_file.v1",
                requires_review=True,
            )
        )
    # Source-map entries for the placeholder observe() stubs we
    # emitted for ``Proof: [Exx]`` references with no matching file.
    # Downstream tooling (e.g. `gaia pkg formalize`) needs to find them
    # in the source_map by gaia_label to resolve cross-module imports.
    for eid in referenced_eids:
        label = _evidence_label(eid)
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:EVIDENCE:placeholder:{eid}",
                source_path=claims_path_rel,
                source_anchor=eid,
                gaia_label=label,
                gaia_record_kind="observe",
                generated_file="gaia/from_ara/evidence.py",
                projection_rule="ara.evidence_placeholder.v1",
                requires_review=True,
            )
        )

    rw_path_rel = "logic/related_work.md"
    rw_path = host / rw_path_rel
    rw_blocks: list[_RelatedWorkBlock] = []
    if rw_path.is_file():
        rw_blocks = _parse_related_work_md(rw_path.read_text(encoding="utf-8"))
    files.append(
        GeneratedFile(
            path="gaia/from_ara/related_work.py",
            body=_render_related_work_module(Path(rw_path_rel), rw_blocks),
        )
    )
    # Per Ara paper §2.2 the `Type:` field carries machine-actionable
    # semantics: `imports`/`extends` inject prior definitions,
    # `bounds` propagates constraints, `baseline` enables automatic
    # regression detection, `refutes` proposes a contradict. We map
    # each kind to a tailored queue item with distinct
    # ``candidate_actions`` so the formalize step can pick the right
    # upgrade path. Spec §14.1 still forbids auto-conversion to
    # `gaia pkg add` without a registry resolver, so all queue items
    # stay open until a reviewer / agent acts.
    rw_queue_candidates_by_kind: dict[str, list[str]] = {
        "dependency": ["gaia_pkg_add", "candidate_relation"],
        "dependency_with_constraints": ["gaia_pkg_add", "candidate_relation"],
        "baseline": ["baseline_regression_check", "gaia_pkg_add"],
        "candidate_contradict": ["contradict", "candidate_relation"],
        "source_only": ["gaia_pkg_add", "candidate_relation"],
    }
    rw_queue_reason_by_kind: dict[str, str] = {
        "dependency": (
            "ARA related-work entry typed `imports`/`extends` — proposes a "
            "registry dependency once an exact Gaia registry match exists "
            "(spec §14.1)."
        ),
        "dependency_with_constraints": (
            "ARA related-work entry typed `bounds` — proposes a registry "
            "dependency that should propagate constraints to hyperparameter "
            "search (Ara paper §2.2; spec §14.1)."
        ),
        "baseline": (
            "ARA related-work entry typed `baseline` — schedule automatic "
            "regression detection against the cited work (Ara paper §2.2)."
        ),
        "candidate_contradict": (
            "ARA related-work entry typed `refutes` — propose `contradict()` "
            "between the local conclusion and the cited work once a target "
            "claim is identified (spec §14.1)."
        ),
        "source_only": (
            "ARA related-work entry — registry binding requires reviewer confirmation (spec §14.1)."
        ),
    }
    for index, rw_block in enumerate(rw_blocks, start=1):
        label = _rw_label(rw_block.rid)
        qid = f"FQRW{index:03d}"
        kind = _related_work_kind(rw_block.type_)
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:{rw_block.rid}",
                source_path=rw_path_rel,
                source_anchor=rw_block.rid,
                gaia_label=label,
                gaia_record_kind="scholarly_reference",
                generated_file="gaia/from_ara/related_work.py",
                projection_rule="ara.related_work.v1",
                requires_review=True,
                queue_id=qid,
                extras={
                    "related_work_type": rw_block.type_,
                    "related_work_kind": kind,
                    "external_ids": rw_block.external_ids,
                    "registry_binding": {"state": "source_only"},
                },
            )
        )
        queue.append(
            QueueItem(
                queue_id=qid,
                source_id=f"ARA:{rw_block.rid}",
                source_refs=[f"{rw_path_rel}#{rw_block.rid}"],
                current_gaia_record=label,
                current_action="note",
                candidate_actions=rw_queue_candidates_by_kind[kind],
                reason_review_needed=rw_queue_reason_by_kind[kind],
            )
        )

    # ---- narrative files (problem.md / experiments.md) ------------- #
    narrative_entries: list[tuple[str, str, str]] = []
    for narrative_name in ("logic/problem.md", "logic/experiments.md"):
        text_value = _read_text_or_empty(host / narrative_name)
        if not text_value.strip():
            continue
        label = f"ara_{_slug(Path(narrative_name).stem)}"
        narrative_entries.append((label, narrative_name, text_value))
        source_map.append(
            SourceMapRecord(
                source_id=f"ARA:NARRATIVE:{narrative_name}",
                source_path=narrative_name,
                gaia_label=label,
                gaia_record_kind="note",
                generated_file="gaia/from_ara/narrative.py",
                projection_rule="ara.narrative.v1",
                requires_review=False,
            )
        )
    files.append(
        GeneratedFile(
            path="gaia/from_ara/narrative.py",
            body=_render_narrative_module(narrative_entries),
        )
    )

    # ---- trace/exploration_tree.yaml dead_end branches -------------- #
    trace_path_rel = "trace/exploration_tree.yaml"
    trace_text = _read_text_or_empty(host / trace_path_rel)
    trace_entries: list[dict[str, Any]] = []
    if trace_text:
        for index, node in enumerate(_parse_dead_ends(trace_text), start=1):
            node_id = node.get("node_id", f"node{index}")
            label = f"ara_trace_{_slug(node_id)}"
            entry_text = node.get("note") or f"ARA trace dead-end at node `{node_id}`."
            trace_entries.append(
                {
                    "label": label,
                    "text": entry_text,
                    "node_id": node_id,
                    "source": trace_path_rel,
                }
            )
            qid = f"FQT{index:03d}"
            source_map.append(
                SourceMapRecord(
                    source_id=f"ARA:TRACE:{node_id}",
                    source_path=trace_path_rel,
                    source_anchor=node_id,
                    gaia_label=label,
                    gaia_record_kind="note",
                    generated_file="gaia/from_ara/trace.py",
                    projection_rule="ara.trace_dead_end.v1",
                    requires_review=True,
                    queue_id=qid,
                )
            )
            queue.append(
                QueueItem(
                    queue_id=qid,
                    source_id=f"ARA:TRACE:{node_id}",
                    source_refs=[f"{trace_path_rel}#{node_id}"],
                    current_gaia_record=label,
                    current_action="note",
                    candidate_actions=["contradict", "exclusive"],
                    reason_review_needed=(
                        "ARA trace records a dead-end exploration node; reviewer must "
                        "decide whether it refutes a formal claim."
                    ),
                )
            )
    files.append(
        GeneratedFile(
            path="gaia/from_ara/trace.py",
            body=_render_trace_module(trace_entries),
        )
    )

    # Add the generic seed projector output on top for explicit --from files.
    if seeds:
        from gaia.engine.projector.generic import project_generic

        generic = project_generic(host, kind=HostKind.ARA, seeds=seeds)
        files.extend(generic.files)
        source_map.extend(generic.source_map)
        # Renumber generic queue ids so they don't collide with ours.
        for q in generic.queue:
            q.queue_id = f"FQH{len(queue) + 1:04d}"
            queue.append(q)

    return ProjectionResult(
        host_kind=HostKind.ARA,
        files=files,
        source_map=source_map,
        queue=queue,
    )
