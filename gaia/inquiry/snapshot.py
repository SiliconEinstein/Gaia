"""Review snapshot persistence — `.gaia/inquiry/reviews/<review_id>.json`.

Snapshots are the *only* durable IR footprint inquiry creates. They carry
exactly the fields needed by ``compute_semantic_diff``: a minimal IR dict plus
beliefs. This is the input spec §6 diffing rides on.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gaia.inquiry.state import inquiry_dir

_SAFE_MODE = re.compile(r"[^A-Za-z0-9._-]+")


def reviews_dir(pkg_path: str | Path) -> Path:
    d = inquiry_dir(pkg_path) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def mint_review_id(ir_hash: str | None, mode: str) -> str:
    """Round A3 — ``<iso-time>_<ir_hash[:8]>_<mode>``, filesystem-safe.

    Colons in the ISO timestamp are replaced with dashes so the id is usable
    as a path component on every platform.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    raw = ir_hash or "nohash"
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    short = _SAFE_MODE.sub("", raw)[:8] or "nohash"
    safe_mode = _SAFE_MODE.sub("", mode) or "auto"
    return f"{ts}_{short}_{safe_mode}"


def save_snapshot(
    pkg_path: str | Path,
    *,
    review_id: str,
    created_at: str,
    ir_hash: str | None,
    ir_dict: dict | None,
    beliefs: list[dict[str, Any]],
) -> Path:
    """Persist the minimal snapshot needed to diff future reviews."""
    base_dir = reviews_dir(pkg_path)
    path = base_dir / f"{review_id}.json"
    # 同秒且 ir_hash 不变会产生相同 review_id；追加递增后缀避免覆盖之前的 snapshot。
    if path.exists():
        n = 2
        while (base_dir / f"{review_id}-{n}.json").exists():
            n += 1
        review_id = f"{review_id}-{n}"
        path = base_dir / f"{review_id}.json"
    payload = {
        "review_id": review_id,
        "created_at": created_at,
        "ir_hash": ir_hash,
        "ir": ir_dict or {"knowledges": [], "strategies": [], "operators": []},
        "beliefs": list(beliefs),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_snapshot(pkg_path: str | Path, review_id: str) -> dict | None:
    path = reviews_dir(pkg_path) / f"{review_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_snapshots(pkg_path: str | Path) -> list[str]:
    """All review ids present on disk, newest first by filename."""
    d = reviews_dir(pkg_path)
    ids = [p.stem for p in d.glob("*.json")]
    ids.sort(reverse=True)
    return ids


def resolve_baseline(
    pkg_path: str | Path, since: str | None, state_last_id: str | None
) -> str | None:
    """Pick a baseline review id based on the --since selector.

    - None / "last" → most recent prior snapshot (excluding the current one)
    - "none" → no baseline
    - explicit id → that id (if snapshot file exists)
    """
    if since == "none":
        return None
    if since and since not in (None, "last"):
        snap = load_snapshot(pkg_path, since)
        return since if snap is not None else None
    if state_last_id:
        snap = load_snapshot(pkg_path, state_last_id)
        if snap is not None:
            return state_last_id
    ids = list_snapshots(pkg_path)
    return ids[0] if ids else None
