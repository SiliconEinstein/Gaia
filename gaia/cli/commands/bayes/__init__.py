"""``gaia bayes`` subcommand group — Bayesian-modelling cli surface.

Exposes :mod:`gaia.engine.bayes` through structured cli verbs. Mirrors
the engine's authoring surface:

* ``bayes model``     — declare a predictive model linking a hypothesis
                        Claim to a Variable observable and a Distribution.
* ``bayes compare``   — compare observed data against one or more
                        predictive models.
* ``bayes <dist>``    — declare a Distribution literal as a standalone
                        binding so subsequent ``bayes model`` /
                        ``observe`` invocations can reference it by
                        name. ``<dist>`` is one of the 11 v0.5 shipping
                        distributions (Binomial / BetaBinomial / Normal
                        / LogNormal / Beta / Exponential / Gamma /
                        StudentT / Cauchy / ChiSquared / Poisson).

**Namespace choice: top-level ``gaia bayes <verb>``.** The engine's
bayes surface is a coherent sub-domain (its own ``gaia.engine.bayes``
package), so giving it a top-level cli group mirrors the engine
organisation. ``bayes model`` / ``bayes compare`` reads naturally;
flat-under-author would have produced ``author bayes-model`` which
felt forced.

All bayes verbs share the same JSON envelope + pre-write + post-write
pipeline as the ``gaia author`` family via the runner in
:mod:`gaia.cli.commands.author._runner`. The distribution-literal verbs
build a ``Distribution(...)`` binding; the structural verbs ``model``
and ``compare`` produce helper Claim bindings the same way the
engine's ``bayes.model`` / ``bayes.compare`` do.
"""

from __future__ import annotations

from gaia.cli.commands.bayes.compare import compare_command
from gaia.cli.commands.bayes.distributions import (
    beta_command,
    betabinomial_command,
    binomial_command,
    cauchy_command,
    chisquared_command,
    exponential_command,
    gamma_command,
    lognormal_command,
    normal_command,
    poisson_command,
    studentt_command,
)
from gaia.cli.commands.bayes.model import model_command

__all__ = [
    "beta_command",
    "betabinomial_command",
    "binomial_command",
    "cauchy_command",
    "chisquared_command",
    "compare_command",
    "exponential_command",
    "gamma_command",
    "lognormal_command",
    "model_command",
    "normal_command",
    "poisson_command",
    "studentt_command",
]
