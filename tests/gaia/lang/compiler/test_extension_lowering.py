"""Compiler extension lowering stays out of Gaia Lang core."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

import gaia.engine.bayes as bayes
from gaia.engine.lang import Binomial, Nat, Probability, Variable, parameter
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage


def _build_minimal_bayes_package(name: str) -> CollectedPackage:
    """Construct a CollectedPackage containing one Bayes model action."""
    with CollectedPackage(name=name, namespace="t") as pkg:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat)
        hypothesis = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h")
        bayes.model(
            hypothesis,
            observable=k,
            distribution=Binomial("k under h", n=10, p=theta),
            label="theta_model",
        )
    return pkg


def _collect_imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Return ``(module_path, lineno)`` tuples for every ``import`` statement.

    Both ``import X`` and ``from X import Y`` are reported; relative imports
    surface their ``module`` attribute (which is ``None`` for ``from . import``,
    skipped here because compile.py is not a package boundary).
    """
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
    return imports


def test_lang_compiler_has_no_direct_bayes_dependency() -> None:
    """``lang.compiler.compile`` must not import any extension package.

    Enforces the host ⊥ extension contract from the engine reorg spec
    (PR #617 §6) for the ``lang ⊥ bayes`` slice. Walks ``compile.py``'s AST
    and rejects any ``import`` / ``from ... import`` whose module path falls
    under ``gaia.engine.bayes`` (or any other declared extension namespace).

    Compared with the earlier string-match version, this:

    - ignores docstring / comment / string-constant mentions of ``bayes`` so
      the contract is about *real* dependencies, not lexical hygiene; and
    - centralizes the extension namespace list in one place so adding a new
      extension (causal, statistics, ...) is a single-line edit.

    .. note::

       This is intentionally a single-test, AST-walk enforcement of one slice
       of the host ⊥ extension contract. When the second extension lands,
       migrate to ``import-linter`` (or equivalent) so the full contract —
       including extension ⊥ extension — is declared in one config block
       rather than fanning out across N hand-written tests. See PR #617 §6
       for the full target dependency direction.
    """
    extension_namespaces = ("gaia.engine.bayes",)

    compile_module = importlib.import_module("gaia.engine.lang.compiler.compile")
    source = Path(inspect.getfile(compile_module)).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=compile_module.__file__ or "compile.py")

    offending: list[str] = []
    for module_path, lineno in _collect_imported_modules(tree):
        for forbidden in extension_namespaces:
            if module_path == forbidden or module_path.startswith(forbidden + "."):
                offending.append(f"{module_path} (line {lineno})")
                break

    assert not offending, (
        "gaia.engine.lang.compiler.compile must not import any extension "
        f"namespace (host ⊥ extension per spec §6); found imports of: {offending}"
    )


def test_bayes_registers_compiler_extension_when_imported() -> None:
    from gaia.engine.lang.compiler.extensions import registered_action_lowerers

    registered = {lowerer.name for lowerer in registered_action_lowerers()}

    assert "bayes" in registered


def test_bayes_actions_compile_through_registered_extension() -> None:
    with CollectedPackage(name="extension_bayes_pkg", namespace="t") as pkg:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat)
        hypothesis = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h")
        model_helper = bayes.model(
            hypothesis,
            observable=k,
            distribution=Binomial("k under h", n=10, p=theta),
            label="theta_model",
        )

    compiled = compile_package_artifact(pkg)
    helper_id = compiled.knowledge_ids_by_object[id(model_helper)]
    helper_ir = next(
        knowledge for knowledge in compiled.graph.knowledges if knowledge.id == helper_id
    )

    assert helper_ir.metadata["model"]["kind"] == "model"
    assert compiled.action_label_map["t:extension_bayes_pkg::action::theta_model"] == helper_id


# --------------------------------------------------------------------------- #
# M3 — locked-in failure mode when no lowerer claims a Bayes-shaped action.   #
# --------------------------------------------------------------------------- #


def test_compile_raises_when_registry_empty_and_discovery_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Bayes action with no lowerer in scope must raise ``ValueError`` loud.

    This documents the failure contract: rather than silently dropping the
    action's IR contribution, the compiler reaches its ``Unsupported action
    type`` branch. Auto-discovery (exercised in the next test) is what keeps
    this from happening in normal compile flows.

    Note: ``compile.py`` imports ``discover_and_register_extensions`` by name,
    so the no-op patch is applied on the compile module's namespace rather
    than on ``extensions`` itself.
    """
    from gaia.engine.lang.compiler import compile as compile_mod
    from gaia.engine.lang.compiler import extensions

    monkeypatch.setattr(extensions, "_ACTION_LOWERERS", {})
    monkeypatch.setattr(compile_mod, "discover_and_register_extensions", lambda: None)

    pkg = _build_minimal_bayes_package("registry_empty_pkg")

    with pytest.raises(ValueError, match="Unsupported action type"):
        compile_package_artifact(pkg)


# --------------------------------------------------------------------------- #
# M1 — compile_package_artifact auto-discovers first-party extensions even   #
# when the registry has been wiped (e.g. fresh subprocess that never did     #
# ``import gaia.engine.bayes`` explicitly).                                   #
# --------------------------------------------------------------------------- #


def test_compile_auto_discovers_first_party_extensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gaia.engine.lang.compiler import extensions

    monkeypatch.setattr(extensions, "_ACTION_LOWERERS", {})

    pkg = _build_minimal_bayes_package("auto_discovery_pkg")

    compiled = compile_package_artifact(pkg)
    assert compiled.action_label_map["t:auto_discovery_pkg::action::theta_model"]
    assert "bayes" in {lowerer.name for lowerer in extensions.registered_action_lowerers()}


# --------------------------------------------------------------------------- #
# M2 — duplicate-registration guard.                                          #
# --------------------------------------------------------------------------- #


def test_register_action_lowerer_rejects_duplicate_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gaia.engine.lang.compiler import extensions
    from gaia.engine.lang.compiler.extensions import register_action_lowerer

    monkeypatch.setattr(extensions, "_ACTION_LOWERERS", {})

    register_action_lowerer("noop", handles=lambda _a: False, lower=lambda _c: None)
    with pytest.raises(ValueError, match="already registered"):
        register_action_lowerer("noop", handles=lambda _a: False, lower=lambda _c: None)


def test_register_action_lowerer_override_replaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gaia.engine.lang.compiler import extensions
    from gaia.engine.lang.compiler.extensions import (
        register_action_lowerer,
        registered_action_lowerers,
    )

    monkeypatch.setattr(extensions, "_ACTION_LOWERERS", {})

    def first(_c: object) -> object:  # pragma: no cover - identity sentinel only
        return None

    def second(_c: object) -> object:  # pragma: no cover - identity sentinel only
        return None

    register_action_lowerer("repl", handles=lambda _a: False, lower=first)
    register_action_lowerer(
        "repl",
        handles=lambda _a: True,
        lower=second,
        override=True,
    )

    by_name = {lowerer.name: lowerer for lowerer in registered_action_lowerers()}
    assert by_name["repl"].lower is second


def test_register_bayes_lowerer_is_idempotent() -> None:
    """Calling ``register_bayes_lowerer`` repeatedly never raises.

    Identity-aware idempotency: each call sees the official Bayes pair
    already in the registry and returns early without re-inserting.
    """
    from gaia.engine.bayes.compiler import register_bayes_lowerer

    register_bayes_lowerer()
    register_bayes_lowerer()
    register_bayes_lowerer()


def test_register_bayes_lowerer_raises_on_conflicting_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign ``"bayes"`` registration must surface as a conflict.

    Without identity-aware idempotency, ``register_bayes_lowerer`` would
    return early on *any* existing ``"bayes"`` entry, masking the exact
    accidental-replacement scenario the duplicate-name guard on
    :func:`register_action_lowerer` exists to surface. Worst case: the
    foreign lowerer uses ``handles=lambda _: True`` with a no-op ``lower``,
    so :func:`is_registered_action` returns ``True`` for Bayes actions and
    the compiler skips them — producing silently-incomplete IR.
    """
    from gaia.engine.bayes.compiler import register_bayes_lowerer
    from gaia.engine.lang.compiler import extensions
    from gaia.engine.lang.compiler.extensions import register_action_lowerer

    monkeypatch.setattr(extensions, "_ACTION_LOWERERS", {})
    register_action_lowerer("bayes", handles=lambda _a: False, lower=lambda _c: None)

    with pytest.raises(ValueError, match="different handler/lowerer pair"):
        register_bayes_lowerer()
