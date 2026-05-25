"""Tests for explorer-only depends_on → derive promotion at the checkpoint.

The supervisor's gap: a paper pulled via ``gaia pkg add --lkm-paper`` lands as a
dependency sub-package whose factors are emitted as INERT ``depends_on`` scaffolds
(recorded in the manifest, never lowered into BP). For *graph exploration* the
paper's internal reasoning should be live. These tests cover the two layers of the
fix:

* :func:`promote_actions_in_place` — the in-memory action-graph rewrite
  (``DependsOn`` → ``Derive``), including skipping a scaffold that cannot form a
  valid derive and folding provenance metadata into the derive rationale; and
* the **RISK proof + the fix**: that the orchestrator checkpoint
  (``_compile_and_infer``) (a) without promotion would leave a pulled dependency's
  factors out of BP entirely (root-only inference), and (b) WITH promotion +
  joint inference, the dependency's promoted derive moves its conclusion belief
  and the conclusion QID surfaces in the joint ``beliefs.json``.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.pr_gate


# --------------------------------------------------------------------------- #
# Layer 1 — promote_actions_in_place (pure action-graph rewrite)              #
# --------------------------------------------------------------------------- #


def test_promote_actions_rewrites_depends_on_to_derive():
    """A ``depends_on`` action becomes a ``Derive`` that enters BP (attaches reasoning)."""
    from gaia.engine.lang.dsl.scaffold import depends_on
    from gaia.engine.lang.runtime.action import DependsOn, Derive
    from gaia.engine.lang.runtime.knowledge import Claim
    from gaia.engine.lang.runtime.package import CollectedPackage
    from gaia.lkm_explorer.engine.promote import promote_actions_in_place

    with CollectedPackage("pkg", namespace="lkm") as pkg:
        premise = Claim("the premise", label="p1")
        conclusion = Claim("the conclusion", label="c1")
        depends_on(
            conclusion,
            given=[premise],
            rationale="because reasons",
            label="lkm_factor_0",
            metadata={"provider": "lkm", "paper_id": "42", "doi": None},
        )

    assert any(isinstance(a, DependsOn) for a in pkg.actions)
    promoted, skipped = promote_actions_in_place(pkg)

    assert (promoted, skipped) == (1, 0)
    # The scaffold is gone; a Derive took its place, preserving label + given.
    assert not any(isinstance(a, DependsOn) for a in pkg.actions)
    derives = [a for a in pkg.actions if isinstance(a, Derive)]
    assert len(derives) == 1
    d = derives[0]
    assert d.label == "lkm_factor_0"
    assert d.conclusion is conclusion
    assert d.given == (premise,)
    # provenance metadata is folded into the rationale (derive has no metadata=).
    assert "provenance:" in d.rationale and "paper_id" in d.rationale
    assert "because reasons" in d.rationale
    # A None metadata value is dropped from the folded provenance.
    assert "doi" not in d.rationale
    # The conclusion now carries the derive as reasoning — the BP-entry hook.
    assert any(r is d for r in conclusion.from_actions)


def test_promote_actions_skips_unpromotable_scaffold():
    """A scaffold with no given Claims cannot derive — it is skipped + counted."""
    from gaia.engine.lang.runtime.action import DependsOn, Derive
    from gaia.engine.lang.runtime.knowledge import Claim
    from gaia.engine.lang.runtime.package import CollectedPackage
    from gaia.lkm_explorer.engine.promote import promote_actions_in_place

    with CollectedPackage("pkg", namespace="lkm") as pkg:
        conclusion = Claim("the conclusion", label="c1")
        # Construct a malformed scaffold directly (no given) — the kind the
        # materializer would never emit, but promotion must tolerate.
        DependsOn(label="bad", conclusion=conclusion, given=())

    promoted, skipped = promote_actions_in_place(pkg)
    assert (promoted, skipped) == (0, 1)
    assert not any(isinstance(a, (DependsOn, Derive)) for a in pkg.actions)


# --------------------------------------------------------------------------- #
# Layer 2 — checkpoint joint inference proof (RISK + fix)                      #
# --------------------------------------------------------------------------- #


def _write_dep_package(dep_root: Path) -> None:
    """A dependency package with a high-prior premise → depends_on conclusion.

    Mirrors the shape ``lkm_materialize`` produces: claims + a ``depends_on``
    scaffold. The premise carries a strong prior so a *live* derive would pull the
    conclusion's belief well above the flat 0.5 — making the BP effect observable.
    """
    src = dep_root / "src" / "deppkg"
    src.mkdir(parents=True, exist_ok=True)
    (dep_root / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "deppkg-gaia"
            version = "0.1.0"
            requires-python = ">=3.12"
            dependencies = []

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["src/deppkg"]

            [tool.gaia]
            type = "knowledge-package"
            namespace = "lkm"

            [tool.gaia.source]
            provider = "lkm"
            kind = "paper"
            paper_id = "999"
            """
        ),
        encoding="utf-8",
    )
    (src / "__init__.py").write_text(
        textwrap.dedent(
            """\
            from gaia.engine.lang import claim, depends_on, register_prior

            premise = claim("strong premise", title="premise")
            conclusion = claim("dependent conclusion", title="conclusion")

            register_prior(premise, value=0.95, justification="test")

            lkm_factor_0 = depends_on(
                conclusion,
                given=[premise],
                rationale="paper factor",
                label="lkm_factor_0",
                metadata={"provider": "lkm", "paper_id": "999"},
            )

            __all__ = ["premise", "conclusion"]
            """
        ),
        encoding="utf-8",
    )


def _write_root_package(root: Path, dep_rel_path: str) -> None:
    """A minimal root exploration package depending on the dep BY PATH."""
    src = root / "src" / "rootpkg"
    src.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""\
            [project]
            name = "rootpkg-gaia"
            version = "0.1.0"
            requires-python = ">=3.12"
            dependencies = ["deppkg-gaia"]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["src/rootpkg"]

            [tool.gaia]
            type = "knowledge-package"
            namespace = "example"

            [tool.uv.sources]
            deppkg-gaia = {{ path = "{dep_rel_path}", editable = true }}
            """
        ),
        encoding="utf-8",
    )
    (src / "__init__.py").write_text(
        textwrap.dedent(
            """\
            from gaia.engine.lang import claim

            root_seed = claim("the root seed claim", title="seed")

            __all__ = ["root_seed"]
            """
        ),
        encoding="utf-8",
    )


def _compile_dep(dep_root: Path) -> None:
    """Compile the dependency to disk as the NEUTRAL (depends_on) artifact.

    This is the state ``pkg add --lkm-paper`` leaves: the dep's ``.gaia/ir.json``
    has NO strategy for the factor (it is in the manifest). The checkpoint must
    recompile-with-promotion to make it live.
    """
    from gaia.engine.ir import LocalCanonicalGraph
    from gaia.engine.packaging import (
        apply_package_priors,
        build_package_manifests,
        compile_loaded_package_artifact,
        load_gaia_package,
        write_compiled_artifacts,
    )

    loaded = load_gaia_package(str(dep_root))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()
    manifests = build_package_manifests(loaded, compiled)
    write_compiled_artifacts(
        loaded.pkg_path,
        ir,
        manifests=manifests,
        formalization_manifest=compiled.formalization_manifest,
    )
    # Sanity: the neutral compile records the factor as an inert depends_on
    # manifest record and NOT a strategy.
    graph = LocalCanonicalGraph(**ir)
    assert not graph.strategies, "neutral dep compile should have no strategy"
    deps = compiled.formalization_manifest["dependencies"]
    assert any(r.get("kind") == "depends_on" for r in deps)


def test_checkpoint_promotes_dependency_reasoning_into_bp(tmp_path: Path):
    """RISK proof + fix: a pulled dep's depends_on enters BP only via promotion.

    Builds a root package depending (by path) on a dep package carrying a
    high-prior premise → ``depends_on`` conclusion (the ``pkg add --lkm-paper``
    shape). Runs the orchestrator's ``_compile_and_infer``:

    * the dep's conclusion QID appears in the JOINT ``beliefs.json`` (root-only
      inference would never include a dependency node), and
    * its belief is pulled WELL above the flat 0.5 prior by the now-live derive
      from the strong premise — proving the promoted derive entered BP and moved
      belief.
    """
    from gaia.lkm_explorer.client.orchestrator import _compile_and_infer

    dep_root = tmp_path / "deppkg"
    root = tmp_path / "rootpkg"
    _write_dep_package(dep_root)
    _write_root_package(root, dep_rel_path="../deppkg")
    _compile_dep(dep_root)

    notes = _compile_and_infer(root)

    # The checkpoint reported the promotion.
    assert any("promoted" in n and "derive" in n for n in notes), notes

    beliefs_path = root / ".gaia" / "beliefs.json"
    assert beliefs_path.exists()
    payload = json.loads(beliefs_path.read_text(encoding="utf-8"))
    by_id = {b["knowledge_id"]: b["belief"] for b in payload["beliefs"]}

    concl_qid = "lkm:deppkg::conclusion"
    premise_qid = "lkm:deppkg::premise"
    # The dep nodes are in the JOINT beliefs (root-only inference would omit them).
    assert concl_qid in by_id, f"dep conclusion missing from joint beliefs: {sorted(by_id)}"
    assert premise_qid in by_id
    # The strong premise (prior ~0.95) pulled the conclusion's belief up via the
    # promoted derive — well above the flat 0.5 a non-live (depends_on) factor or
    # an unconnected node would sit at.
    assert by_id[premise_qid] > 0.9
    assert by_id[concl_qid] > 0.6, by_id[concl_qid]


def test_compile_and_infer_no_deps_is_root_only(tmp_path: Path):
    """With no -gaia deps, the checkpoint is plain root inference (no promotion)."""
    from gaia.lkm_explorer.client.orchestrator import _compile_and_infer

    root = tmp_path / "solo"
    src = root / "src" / "solo"
    src.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "solo-gaia"
            version = "0.1.0"
            requires-python = ">=3.12"
            dependencies = []

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["src/solo"]

            [tool.gaia]
            type = "knowledge-package"
            namespace = "example"
            """
        ),
        encoding="utf-8",
    )
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n\nseed = claim('a seed', title='seed')\n\n"
        "__all__ = ['seed']\n",
        encoding="utf-8",
    )

    notes = _compile_and_infer(root)
    # No deps -> no promotion note.
    assert not any("promoted" in n for n in notes)
    assert (root / ".gaia" / "beliefs.json").exists()
