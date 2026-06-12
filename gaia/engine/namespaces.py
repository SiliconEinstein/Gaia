"""Public ownership registry for package-local ``.gaia`` namespaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GaiaNamespace:
    """One package-local ``.gaia`` subtree and its owning component."""

    name: str
    path: str
    owner: str
    lifecycle: str
    description: str


RESEARCH_NAMESPACE = ".gaia/research"

GAIA_NAMESPACE_REGISTRY: dict[str, GaiaNamespace] = {
    "ir": GaiaNamespace(
        name="ir",
        path=".gaia/ir.json",
        owner="gaia-core",
        lifecycle="compiled",
        description="Compiled LocalCanonicalGraph emitted by Gaia core.",
    ),
    "research": GaiaNamespace(
        name="research",
        path=RESEARCH_NAMESPACE,
        owner="gaia-research",
        lifecycle="external-plugin",
        description=(
            "Research run artifacts owned by the external gaia-research package. "
            "Gaia core reserves the namespace but should not create canonical "
            "research state there after the split."
        ),
    ),
}


def namespace_record(name: str) -> GaiaNamespace | None:
    """Return the registered ``.gaia`` namespace record, if any."""
    return GAIA_NAMESPACE_REGISTRY.get(name)


def namespace_path(name: str) -> str:
    """Return the registered ``.gaia`` path or raise for unknown namespaces."""
    record = namespace_record(name)
    if record is None:
        raise KeyError(f"unknown .gaia namespace {name!r}")
    return record.path
