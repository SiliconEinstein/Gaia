"""Structural validation for knowledge packages."""


def validate_package(claims: list[dict]) -> list[str]:
    """Validate claims and return list of error messages (empty = valid)."""
    errors = []
    ids = set()
    all_ids = {c.get("id") for c in claims if c.get("id") is not None}

    for c in claims:
        cid = c.get("id")
        if cid is None:
            errors.append(f"Claim missing 'id': {c}")
            continue
        if cid in ids:
            errors.append(f"Duplicate claim ID: {cid}")
        ids.add(cid)

        if not c.get("content"):
            errors.append(f"Claim {cid} missing 'content'")

        # Check premise references exist
        for pid in c.get("premise", []):
            if pid not in all_ids:
                errors.append(f"Claim {cid}: premise {pid} not found")

        # Check context references exist
        for cid_ref in c.get("context", []):
            if cid_ref not in all_ids:
                errors.append(f"Claim {cid}: context {cid_ref} not found")

    # Cycle detection (simple DFS)
    adj = {}
    for c in claims:
        cid = c.get("id")
        if cid is not None:
            adj[cid] = c.get("premise", []) + c.get("context", [])

    visited = set()
    in_stack = set()

    def has_cycle(node):
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for dep in adj.get(node, []):
            if dep in all_ids and has_cycle(dep):
                return True
        in_stack.discard(node)
        return False

    for nid in all_ids:
        if has_cycle(nid):
            errors.append(f"Cycle detected involving claim {nid}")
            break

    return errors
