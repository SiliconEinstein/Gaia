"""Bayes peer-module public surface."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator

import pytest


def _drop_bayes_modules() -> None:
    for name in list(sys.modules):
        if name == "gaia.engine.lang.bayes" or name.startswith("gaia.engine.lang.bayes."):
            sys.modules.pop(name, None)
    lang_module = sys.modules.get("gaia.engine.lang")
    if lang_module is not None:
        lang_module.__dict__.pop("bayes", None)


@pytest.fixture(autouse=True)
def cleanup_bayes_modules() -> Generator[None, None, None]:
    yield
    _drop_bayes_modules()


def test_bayes_canonical_peer_module_imports() -> None:
    import gaia.engine.bayes as bayes
    from gaia.engine.bayes import data, likelihood, model
    from gaia.engine.bayes.dsl import data as dsl_data
    from gaia.engine.bayes.dsl import likelihood as dsl_likelihood
    from gaia.engine.bayes.dsl import model as dsl_model
    from gaia.engine.bayes.runtime import BayesInference, Likelihood, PredictiveModel
    from gaia.engine.lang.runtime.action import Reasoning

    assert data is dsl_data
    assert model is dsl_model
    assert likelihood is dsl_likelihood
    assert "data" in bayes.__all__
    assert issubclass(BayesInference, Reasoning)
    assert issubclass(PredictiveModel, BayesInference)
    assert issubclass(Likelihood, BayesInference)


def test_lang_bayes_shortcut_is_removed_before_v0_5_release() -> None:
    _drop_bayes_modules()

    with pytest.raises(ImportError, match="cannot import name 'bayes'"):
        from gaia.engine.lang import bayes  # noqa: F401


def test_lang_distribution_factories_delegate_to_peer_bayes_module() -> None:
    from gaia.engine.lang.runtime.distribution import Beta, Binomial, Normal

    assert Normal("x", mu=0.0, sigma=1.0).kind == "normal"
    assert Beta("p", alpha=1.0, beta=1.0).kind == "beta"
    assert Binomial("k", n=10, p=0.5).kind == "binomial"


def test_lang_bayes_legacy_namespace_is_removed_before_v0_5_release() -> None:
    _drop_bayes_modules()

    with pytest.raises(ModuleNotFoundError, match=r"gaia\.engine\.lang\.bayes"):
        importlib.import_module("gaia.engine.lang.bayes")


@pytest.mark.parametrize(
    "old_path",
    [
        "gaia.engine.lang.bayes.compiler",
        "gaia.engine.lang.bayes.verbs",
        "gaia.engine.lang.bayes.verbs.likelihood",
    ],
)
def test_lang_bayes_legacy_submodule_paths_are_removed_before_v0_5_release(old_path: str) -> None:
    _drop_bayes_modules()

    with pytest.raises(ModuleNotFoundError, match=r"gaia\.engine\.lang\.bayes"):
        importlib.import_module(old_path)
