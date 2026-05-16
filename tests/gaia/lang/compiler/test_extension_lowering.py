"""Compiler extension lowering stays out of Gaia Lang core."""

from __future__ import annotations

import importlib
import inspect

import pytest

import gaia.engine.bayes as bayes
from gaia.engine.lang import Nat, Probability, Variable, parameter
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
            distribution=bayes.Binomial(n=10, p=theta),
            label="theta_model",
        )
    return pkg


def test_lang_compiler_has_no_direct_bayes_import_or_hook() -> None:
    compile_module = importlib.import_module("gaia.engine.lang.compiler.compile")
    source = inspect.getsource(compile_module)

    assert "gaia.engine.bayes" not in source
    assert "_lower_bayes_actions" not in source


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
            distribution=bayes.Binomial(n=10, p=theta),
            label="theta_model",
        )

    compiled = compile_package_artifact(pkg)
    helper_id = compiled.knowledge_ids_by_object[id(model_helper)]
    helper_ir = next(
        knowledge for knowledge in compiled.graph.knowledges if knowledge.id == helper_id
    )

    assert helper_ir.metadata["bayes"]["role"] == "prediction"
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
    """Calling ``register_bayes_lowerer`` repeatedly never raises."""
    from gaia.engine.bayes.compiler import register_bayes_lowerer

    register_bayes_lowerer()
    register_bayes_lowerer()
    register_bayes_lowerer()
