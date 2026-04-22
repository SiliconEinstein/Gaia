"""Audit-question templates for Gaia Lang v6 review targets."""

from __future__ import annotations


class _MissingLabelDict(dict):
    def __missing__(self, key):
        return "?"


_TEMPLATES = {
    "derive": "Do the listed premises suffice to establish [@{conclusion_label}]?",
    "observe": "Is the observation of [@{conclusion_label}] reliable under the stated conditions?",
    "compute": "Is the computation of [@{conclusion_label}] correctly implemented?",
    "infer": (
        "Does [@{hypothesis_label}] predict [@{evidence_label}] at the stated "
        "conditional probabilities?"
    ),
    "equal": "Are [@{a_label}] and [@{b_label}] truly equivalent?",
    "contradict": "Do [@{a_label}] and [@{b_label}] truly contradict?",
}


def generate_audit_question(action_type: str, **labels) -> str:
    template = _TEMPLATES.get(action_type, "Is this reasoning step valid?")
    return template.format_map(_MissingLabelDict(labels))
