"""Generate manifest.json summarizing all GitHub output artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def generate_manifest(
    ir: dict,
    exported_ids: set[str],
    wiki_pages: list[str],
    *,
    assets: list[str] | None = None,
    sections: list[str] | None = None,
) -> str:
    """Return a JSON string describing the generated GitHub output.

    Fields:
    - package_name: from IR
    - generated_at: ISO-8601 UTC timestamp
    - wiki_pages: list of wiki page filenames
    - pages_sections: one ``<module>.md`` per unique module (or explicit override)
    - assets: list of asset filenames
    - exported_conclusions: list of exported knowledge labels
    - total_claims: count of claim-type knowledge nodes (excluding helpers)
    - total_beliefs: count of non-helper knowledge nodes
    - readme_placeholders: list of placeholder markers for future expansion
    """
    # Derive sections from unique modules unless explicitly provided
    if sections is not None:
        pages_sections = list(sections)
    else:
        seen: set[str] = set()
        pages_sections: list[str] = []
        for k in ir.get("knowledges", []):
            mod = k.get("module")
            if mod and mod not in seen:
                seen.add(mod)
                pages_sections.append(f"{mod}.md")

    # Build exported conclusions list (labels)
    knowledge_by_id = {k["id"]: k for k in ir.get("knowledges", [])}
    exported_conclusions: list[str] = []
    for eid in sorted(exported_ids):
        k = knowledge_by_id.get(eid)
        if k:
            exported_conclusions.append(k.get("label", eid))
        else:
            exported_conclusions.append(eid)

    # Count non-helper nodes
    non_helper = [k for k in ir.get("knowledges", []) if not k.get("label", "").startswith("__")]
    total_claims = sum(1 for k in non_helper if k.get("type") == "claim")
    total_beliefs = len(non_helper)

    manifest = {
        "package_name": ir.get("package_name", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wiki_pages": wiki_pages,
        "pages_sections": pages_sections,
        "assets": assets or [],
        "exported_conclusions": exported_conclusions,
        "total_claims": total_claims,
        "total_beliefs": total_beliefs,
        "readme_placeholders": [],
    }

    return json.dumps(manifest, indent=2, ensure_ascii=False)
