"""Compiler extension lowering stays out of Gaia Lang core."""

from __future__ import annotations

import importlib
import inspect

import gaia.engine.bayes as bayes
from gaia.engine.lang import Nat, Probability, Variable, parameter
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage


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
