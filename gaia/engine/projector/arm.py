"""ARM → Gaia deterministic projector (spec §6).

An ARM (agent-ready manuscript) bundle is a structured zip / directory
that holds the paper, its reproducible execution, and an optional
knowledge layer:

```
<host>/
  arm_manifest.json
  knowledge/claims.json          # optional structured claims
  characterization.json          # optional metrics report
  execution/                     # scripts / notebooks / Dockerfile
  trace/                         # agent execution logs
  rag/, skills/, sub_agent/
```

Spec §6.1 maps each source class to a Gaia v0.5 action. The safe
subset implemented here:

| ARM source                                         | Gaia output    |
|----------------------------------------------------|----------------|
| ``arm_manifest.json`` identity                     | ``note(...)``  |
| ``knowledge/claims.json`` entries                  | ``claim(...)`` |
| ``characterization.json`` ``metrics`` entries      | ``observe(...)`` |
| anything else                                      | ``note(...)``  |

Just like the ARA projector, this module never emits ``derive`` /
``infer`` / ``contradict`` — those require explicit user/agent
acceptance recorded through the formalization queue.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from gaia.engine.codegen import render_call_statement, render_module
from gaia.engine.projector.api import (
    GeneratedFile,
    ProjectionResult,
    QueueItem,
    SourceMapRecord,
)
from gaia.engine.projector.host_kind import HostKind

__all__ = ["project_arm"]


_INIT_BODY = '''\
"""Deterministic ARM projection root."""

from .manifest import *  # noqa: F401,F403
from .claims import *  # noqa: F401,F403
from .characterization import *  # noqa: F401,F403

from .manifest import __all__ as _manifest_all
from .claims import __all__ as _claims_all
from .characterization import __all__ as _char_all

__all__ = [*_manifest_all, *_claims_all, *_char_all]
'''


def _safe_label(prefix: str, raw: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_") or "x"
    return f"{prefix}_{safe}"


def _render_manifest_module(manifest: dict[str, Any]) -> str:
    title = manifest.get("title") or manifest.get("name") or "ARM bundle"
    metadata = {
        k: v for k, v in manifest.items() if isinstance(v, (str, int, float, bool, list, dict))
    }
    statement = render_call_statement(
        target_label="arm_manifest_summary",
        func_name="note",
        positional=[f"ARM bundle: {title}"],
        keywords={"metadata": metadata},
    )
    return render_module(
        docstring="Deterministic projection of `arm_manifest.json` identity fields.",
        engine_imports=("note",),
        statements=[statement],
        all_labels=["arm_manifest_summary"],
    )


def _render_claims_module(claims: list[dict[str, Any]]) -> str:
    statements: list[str] = []
    labels: list[str] = []
    for entry in claims:
        cid = entry.get("id") or entry.get("claim_id") or entry.get("name")
        text = entry.get("content") or entry.get("text") or entry.get("title")
        if not isinstance(cid, str) or not isinstance(text, str):
            continue
        label = _safe_label("arm_claim", cid)
        labels.append(label)
        title = entry.get("title")
        meta: dict[str, str] = {
            "arm_id": cid,
            "source": "knowledge/claims.json",
        }
        if isinstance(entry.get("status"), str):
            meta["arm_status"] = entry["status"]
        keywords: dict[str, Any] = {}
        if isinstance(title, str):
            keywords["title"] = title
        keywords["metadata"] = meta
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="claim",
                positional=[text],
                keywords=keywords,
            )
        )
    if not labels:
        labels.append("_arm_claims_placeholder")
        statements.append(
            render_call_statement(
                target_label="_arm_claims_placeholder",
                func_name="note",
                positional=["knowledge/claims.json is absent or empty."],
            )
        )
    return render_module(
        docstring="Deterministic projection of `knowledge/claims.json` entries.",
        engine_imports=("claim", "note"),
        statements=statements,
        all_labels=labels,
    )


def _render_characterization_module(metrics: list[dict[str, Any]]) -> str:
    statements: list[str] = []
    labels: list[str] = []
    for entry in metrics:
        name = entry.get("name") or entry.get("id")
        value = entry.get("value")
        if not isinstance(name, str):
            continue
        label = _safe_label("arm_metric", name)
        labels.append(label)
        content = f"Reported metric `{name}`"
        if value is not None:
            content += f" = {value}"
        meta_value: Any = value
        # `observe()` only accepts JSON-shaped metadata values; coerce
        # anything fancier through repr so the literal is unambiguous.
        if not isinstance(meta_value, (str, int, float, bool, type(None), list, dict)):
            meta_value = repr(meta_value)
        statements.append(
            render_call_statement(
                target_label=label,
                func_name="observe",
                positional=[content],
                keywords={
                    "source_refs": [f"characterization.json#/metrics/{name}"],
                    "rationale": ("Programmatic projection of an ARM characterization metric."),
                    "metadata": {"arm_metric": name, "value": meta_value},
                },
            )
        )
    if not labels:
        labels.append("_arm_char_placeholder")
        statements.append(
            render_call_statement(
                target_label="_arm_char_placeholder",
                func_name="note",
                positional=["characterization.json is absent or empty."],
            )
        )
    return render_module(
        docstring="Deterministic projection of `characterization.json` metrics.",
        engine_imports=("note", "observe"),
        statements=statements,
        all_labels=labels,
    )


def project_arm(host: Path, *, seeds: list[Path]) -> ProjectionResult:  # noqa: C901
    """Project an ARM bundle into Gaia DSL.

    Always emits ``gaia/from_arm/`` with four files
    (``__init__.py``, ``manifest.py``, ``claims.py``,
    ``characterization.py``) so the embedded loader sees a complete
    package even when the bundle is partial.
    """
    files: list[GeneratedFile] = []
    source_map: list[SourceMapRecord] = []
    queue: list[QueueItem] = []

    files.append(GeneratedFile(path="gaia/from_arm/__init__.py", body=_INIT_BODY))

    arm_manifest: dict[str, Any] = {}
    manifest_path = host / "arm_manifest.json"
    if manifest_path.is_file():
        try:
            arm_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            arm_manifest = {}
    files.append(
        GeneratedFile(
            path="gaia/from_arm/manifest.py",
            body=_render_manifest_module(arm_manifest if isinstance(arm_manifest, dict) else {}),
        )
    )
    if arm_manifest:
        source_map.append(
            SourceMapRecord(
                source_id="ARM:manifest",
                source_path="arm_manifest.json",
                gaia_label="arm_manifest_summary",
                gaia_record_kind="note",
                generated_file="gaia/from_arm/manifest.py",
                projection_rule="arm.manifest.v1",
                requires_review=False,
            )
        )

    claims_path = host / "knowledge" / "claims.json"
    claims_entries: list[dict[str, Any]] = []
    if claims_path.is_file():
        try:
            raw = json.loads(claims_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = []
        if isinstance(raw, list):
            claims_entries = [e for e in raw if isinstance(e, dict)]
        elif isinstance(raw, dict) and isinstance(raw.get("claims"), list):
            claims_entries = [e for e in raw["claims"] if isinstance(e, dict)]
    files.append(
        GeneratedFile(
            path="gaia/from_arm/claims.py",
            body=_render_claims_module(claims_entries),
        )
    )
    for index, entry in enumerate(claims_entries, start=1):
        cid = entry.get("id") or entry.get("claim_id") or entry.get("name")
        if not isinstance(cid, str):
            continue
        label = _safe_label("arm_claim", cid)
        qid = f"FQAC{index:03d}"
        source_map.append(
            SourceMapRecord(
                source_id=f"ARM:{cid}",
                source_path="knowledge/claims.json",
                source_anchor=f"/claims/{index - 1}",
                gaia_label=label,
                gaia_record_kind="claim",
                generated_file="gaia/from_arm/claims.py",
                projection_rule="arm.knowledge_claim.v1",
                requires_review=True,
                queue_id=qid,
            )
        )
        queue.append(
            QueueItem(
                queue_id=qid,
                source_id=f"ARM:{cid}",
                source_refs=[f"knowledge/claims.json#/claims/{index - 1}"],
                current_gaia_record=label,
                current_action="claim",
                candidate_actions=["depends_on", "infer"],
                reason_review_needed=("ARM claim has evidence refs but no explicit warrant type."),
            )
        )

    metrics_path = host / "characterization.json"
    metrics: list[dict[str, Any]] = []
    if metrics_path.is_file():
        try:
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        if isinstance(raw, dict) and isinstance(raw.get("metrics"), list):
            metrics = [e for e in raw["metrics"] if isinstance(e, dict)]
        elif isinstance(raw, list):
            metrics = [e for e in raw if isinstance(e, dict)]
    files.append(
        GeneratedFile(
            path="gaia/from_arm/characterization.py",
            body=_render_characterization_module(metrics),
        )
    )
    for entry in metrics:
        name = entry.get("name") or entry.get("id")
        if not isinstance(name, str):
            continue
        label = _safe_label("arm_metric", name)
        source_map.append(
            SourceMapRecord(
                source_id=f"ARM:METRIC:{name}",
                source_path="characterization.json",
                source_anchor=f"/metrics/{name}",
                gaia_label=label,
                gaia_record_kind="observe",
                generated_file="gaia/from_arm/characterization.py",
                projection_rule="arm.characterization_metric.v1",
                requires_review=False,
            )
        )

    if seeds:
        from gaia.engine.projector.generic import project_generic

        generic = project_generic(host, kind=HostKind.ARM, seeds=seeds)
        files.extend(generic.files)
        source_map.extend(generic.source_map)
        for q in generic.queue:
            q.queue_id = f"FQH{len(queue) + 1:04d}"
            queue.append(q)

    return ProjectionResult(
        host_kind=HostKind.ARM,
        files=files,
        source_map=source_map,
        queue=queue,
    )
