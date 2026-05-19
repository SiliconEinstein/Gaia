"""Pre-push hook: ensure IR_SCHEMA_SNAPSHOT_HASH matches current IR hash.

Fires when IR Pydantic models have changed (computed hash differs from
snapshot) without a corresponding bump of IR_SCHEMA_VERSION and update
to IR_SCHEMA_SNAPSHOT_HASH.

Spec ref: PR #620 §6 + 协作单 四·Q5 R2 dispatch (double-write).
"""

from __future__ import annotations

import sys

from gaia._meta import (
    IR_SCHEMA_SNAPSHOT_HASH,
    IR_SCHEMA_VERSION,
    compute_current_ir_hash,
)


def main() -> int:
    """Exit non-zero if the current IR hash drifts from the committed snapshot."""
    current = compute_current_ir_hash()
    if current == IR_SCHEMA_SNAPSHOT_HASH:
        return 0
    print(
        f"[FAIL] IR schema hash changed.\n"
        f"  snapshot: {IR_SCHEMA_SNAPSHOT_HASH}\n"
        f"  current:  {current}\n"
        f"  current IR_SCHEMA_VERSION: {IR_SCHEMA_VERSION}\n"
        f"\n"
        f"Action — if this is a field add/remove/rename in gaia/engine/ir/:\n"
        f"  1. Bump IR_SCHEMA_VERSION to the next ir-vN in gaia/_meta.py\n"
        f"  2. Update IR_SCHEMA_SNAPSHOT_HASH to {current!r}\n"
        f"  3. Add the new version to ALLOWED_IR_VERSIONS\n"
        f"\n"
        f"Action — if a refactor unexpectedly changed schema serialization:\n"
        f"  audit the diff; if schema is intentionally stable, update only\n"
        f"  IR_SCHEMA_SNAPSHOT_HASH to {current!r} (no version bump).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
