"""Client for Gaia Server API."""

import httpx

from cli.package import load_all_claims, load_package_config


def publish_to_server(pkg_dir, server_url: str) -> dict:
    """Publish package to Gaia Server via POST /commits."""
    config = load_package_config(pkg_dir)
    claims = load_all_claims(pkg_dir)

    operations = []
    for claim in claims:
        if claim.get("premise") or claim.get("context"):
            operations.append(
                {
                    "op": "add_edge",
                    "tail": [{"node_id": pid} for pid in claim.get("premise", [])],
                    "head": [{"content": claim["content"], "keywords": []}],
                    "type": claim.get("type", "deduction"),
                    "reasoning": [{"content": claim.get("why", "")}] if claim.get("why") else [],
                }
            )

    pkg_name = config.get("package", {}).get("name", "unknown")
    pkg_version = config.get("package", {}).get("version", "0.1.0")
    payload = {
        "message": f"Publish {pkg_name} {pkg_version}",
        "operations": operations,
    }

    response = httpx.post(f"{server_url}/commits", json=payload)
    response.raise_for_status()
    return response.json()
