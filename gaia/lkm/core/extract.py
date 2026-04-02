"""Paper XML extraction: parse reasoning chain XMLs → LKM local nodes.

Extracts from 3 XML files per paper:
- review.xml: premises with prior_probability
- reasoning_chain.xml: reasoning steps + conclusions
- select_conclusion.xml: research problem + conclusion summaries

Deterministic: same XML → same output.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from gaia.lkm.models import (
    FactorParamRecord,
    LocalFactorNode,
    LocalVariableNode,
    ParameterizationSource,
    PriorRecord,
    Step,
    compute_content_hash,
)


@dataclass
class ExtractionResult:
    """Output of extracting a paper's XMLs."""

    local_variables: list[LocalVariableNode] = field(default_factory=list)
    local_factors: list[LocalFactorNode] = field(default_factory=list)
    prior_records: list[PriorRecord] = field(default_factory=list)
    factor_param_records: list[FactorParamRecord] = field(default_factory=list)
    param_sources: list[ParameterizationSource] = field(default_factory=list)
    package_id: str = ""
    version: str = "1.0.0"


def _text(elem: ET.Element) -> str:
    """Extract all text content from an element, including tail text of children."""
    return "".join(elem.itertext()).strip()


def _qid(metadata_id: str, name: str) -> str:
    return f"paper:{metadata_id}::{name}"


def _lfac_id(metadata_id: str, conclusion_id: str) -> str:
    payload = f"paper:{metadata_id}::factor_c{conclusion_id}"
    return f"lfac_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _extract_review(
    review_xml: str, metadata_id: str, package_id: str, version: str
) -> tuple[list[LocalVariableNode], list[PriorRecord], dict[str, list[str]]]:
    """Parse review.xml → premise variables + prior records.

    Returns (variables, priors, conclusion_premises_map).
    conclusion_premises_map: {conclusion_id: [premise_qid, ...]}
    """
    root = ET.fromstring(review_xml)
    variables = []
    priors = []
    conclusion_premises: dict[str, list[str]] = {}

    for premise in root.iter("premise"):
        name = premise.get("name", premise.get("id", ""))
        content = _text(premise)
        conclusion_id = premise.get("conclusion_id", "")
        prior_prob = premise.get("prior_probability")

        qid = _qid(metadata_id, name)
        ch = compute_content_hash("claim", content, [])

        variables.append(
            LocalVariableNode(
                id=qid,
                type="claim",
                visibility="public",
                content=content,
                content_hash=ch,
                parameters=[],
                source_package=package_id,
                version=version,
            )
        )

        if prior_prob:
            priors.append(
                PriorRecord(
                    variable_id=qid,
                    value=float(prior_prob),
                    source_id=f"extract_paper_{metadata_id}",
                    created_at=datetime.now(timezone.utc),
                )
            )

        if conclusion_id:
            conclusion_premises.setdefault(conclusion_id, []).append(qid)

    return variables, priors, conclusion_premises


def _extract_reasoning_chain(
    reasoning_xml: str,
    metadata_id: str,
    package_id: str,
    version: str,
    conclusion_premises: dict[str, list[str]],
) -> tuple[list[LocalVariableNode], list[LocalFactorNode]]:
    """Parse reasoning_chain.xml → conclusion variables + strategy factors."""
    root = ET.fromstring(reasoning_xml)
    variables = []
    factors = []

    for cr in root.iter("conclusion_reasoning"):
        conclusion_id = cr.get("conclusion_id", "")

        # Extract reasoning steps
        steps = []
        reasoning_elem = cr.find("reasoning")
        if reasoning_elem is not None:
            for step_elem in reasoning_elem.findall("step"):
                steps.append(Step(reasoning=_text(step_elem)))

        # Extract conclusion
        conclusion_elem = cr.find("conclusion")
        if conclusion_elem is not None:
            content = _text(conclusion_elem)
            qid = _qid(metadata_id, f"conclusion_{conclusion_id}")
            ch = compute_content_hash("claim", content, [])

            variables.append(
                LocalVariableNode(
                    id=qid,
                    type="claim",
                    visibility="public",
                    content=content,
                    content_hash=ch,
                    parameters=[],
                    source_package=package_id,
                    version=version,
                )
            )

            # Create strategy factor: premises → conclusion
            premises = conclusion_premises.get(conclusion_id, [])
            if premises:
                factors.append(
                    LocalFactorNode(
                        id=_lfac_id(metadata_id, conclusion_id),
                        factor_type="strategy",
                        subtype="infer",
                        premises=premises,
                        conclusion=qid,
                        steps=steps if steps else None,
                        source_package=package_id,
                        version=version,
                    )
                )

    return variables, factors


def _extract_problem(
    select_xml: str, metadata_id: str, package_id: str, version: str
) -> list[LocalVariableNode]:
    """Parse select_conclusion.xml → research problem as question variable."""
    root = ET.fromstring(select_xml)
    variables = []

    problem_elem = root.find(".//problem")
    if problem_elem is not None:
        content = _text(problem_elem)
        if content:
            qid = _qid(metadata_id, "problem")
            ch = compute_content_hash("question", content, [])
            variables.append(
                LocalVariableNode(
                    id=qid,
                    type="question",
                    visibility="public",
                    content=content,
                    content_hash=ch,
                    parameters=[],
                    source_package=package_id,
                    version=version,
                )
            )

    return variables


def extract(
    review_xml: str,
    reasoning_chain_xml: str,
    select_conclusion_xml: str,
    metadata_id: str,
) -> ExtractionResult:
    """Extract a paper's 3 XMLs → LKM local nodes + parameters.

    Args:
        review_xml: Content of review.xml
        reasoning_chain_xml: Content of reasoning_chain.xml
        select_conclusion_xml: Content of select_conclusion.xml
        metadata_id: Unique paper identifier (e.g. "363056a0")

    Returns:
        ExtractionResult with local_variables, local_factors, prior_records, etc.
    """
    package_id = f"paper:{metadata_id}"
    version = "1.0.0"
    result = ExtractionResult(package_id=package_id, version=version)

    # 1. Extract premises + priors from review.xml
    premise_vars, priors, conclusion_premises = _extract_review(
        review_xml, metadata_id, package_id, version
    )
    result.local_variables.extend(premise_vars)
    result.prior_records.extend(priors)

    # 2. Extract conclusions + factors from reasoning_chain.xml
    conclusion_vars, factors = _extract_reasoning_chain(
        reasoning_chain_xml, metadata_id, package_id, version, conclusion_premises
    )
    result.local_variables.extend(conclusion_vars)
    result.local_factors.extend(factors)

    # 3. Extract research problem from select_conclusion.xml
    problem_vars = _extract_problem(select_conclusion_xml, metadata_id, package_id, version)
    result.local_variables.extend(problem_vars)

    # 4. Create ParameterizationSource
    result.param_sources.append(
        ParameterizationSource(
            source_id=f"extract_paper_{metadata_id}",
            source_class="heuristic",
            model="xml_extract_v1",
            created_at=datetime.now(timezone.utc),
        )
    )

    return result
