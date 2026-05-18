"""``gaia bayes model`` — append a ``bayes.model(...)`` predictive-model statement.

Maps to ``gaia.engine.bayes.dsl.model.model``:

.. code-block:: python

    bayes.model(
        hypothesis: Claim,
        *,
        observable: Variable,
        distribution: Distribution,
        background=None,
        rationale="",
        label=None,
        metadata=None,
    )

Cli surface:

* ``--hypothesis <ident>`` — identifier of the hypothesis Claim.
* ``--observable <ident>`` — identifier of the Variable being predicted.
* ``--distribution <ident>`` — identifier of the Distribution binding
  (created via ``bayes binomial`` / ``bayes normal`` / etc.).
* ``--background <csv>`` — optional comma-separated background Knowledge
  identifiers (forwarded to ``background=[...]``).
* ``--rationale <str>`` — optional natural-language justification.
* ``--label <ident>`` — identifier the helper Claim binds to.
"""

from __future__ import annotations

import re
from typing import Any

import typer

from gaia.cli.commands.author._common import (
    build_sibling_imports,
    emit_syntax_error,
    normalize_file_option,
    parse_metadata,
    split_csv_idents,
    validate_identifier_flag,
)
from gaia.cli.commands.author._formula_sandbox import (
    FormulaSandboxError,
    validate_formula_expr,
)
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op

# Detect when ``--distribution`` carries an inline Distribution
# expression (e.g. ``Binomial("k under H", n=395, p=3/4)``) instead of a bare
# identifier. The cli accepts both shapes: bare-identifier routes
# through pre-write reference resolution; inline-expression routes
# through the formula sandbox.
_BARE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _render_model_statement(
    *,
    label: str,
    hypothesis: str,
    observable: str,
    distribution: str,
    background: list[str],
    rationale: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Render the proposed ``bayes.model(...)`` statement."""
    args = [hypothesis]
    kwargs = [f"observable={observable}", f"distribution={distribution}"]
    if background:
        kwargs.append(f"background=[{', '.join(background)}]")
    if rationale:
        kwargs.append(f"rationale={rationale!r}")
    kwargs.append(f"label={label!r}")
    if metadata:
        kwargs.append(f"metadata={metadata!r}")
    return f"{label} = bayes.model({', '.join(args)}, {', '.join(kwargs)})"


def model_command(
    label: str = typer.Option(
        ..., "--label", help="Identifier the predictive-model helper Claim binds to."
    ),
    hypothesis: str = typer.Option(
        ...,
        "--hypothesis",
        help="Identifier of the hypothesis Claim being modelled.",
    ),
    observable: str = typer.Option(
        ...,
        "--observable",
        help="Identifier of the Variable the model predicts.",
    ),
    distribution: str = typer.Option(
        ...,
        "--distribution",
        help=(
            "Distribution binding. Accepts either (a) a bare identifier "
            "of a Distribution binding (created via `bayes binomial` / "
            "`bayes normal` / ...) — resolved in module scope, or "
            "(b) an inline Distribution expression like "
            "`Binomial('k under H', n=395, p=3/4)` — validated via the formula "
            "sandbox and emitted verbatim into the `distribution=` slot."
        ),
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=("Relative path under src/<import_name>/ to write into. Default: `__init__.py`."),
    ),
    background: str | None = typer.Option(
        None,
        "--background",
        help="Comma-separated identifiers passed as the background kwarg.",
    ),
    rationale: str | None = typer.Option(
        None, "--rationale", help="Optional natural-language justification."
    ),
    metadata: str | None = typer.Option(
        None, "--metadata", help="Optional JSON-encoded metadata dict."
    ),
    references: str | None = typer.Option(
        None,
        "--references",
        help=(
            "Comma-separated identifiers to whitelist inside the formula "
            "sandbox when --distribution carries an inline expression "
            "referencing module-scope constants (e.g. `--distribution "
            "'bayes.Binomial(n=TOTAL_COUNT, p=MENDELIAN_DOMINANT_PROBABILITY)' "
            "--references TOTAL_COUNT,MENDELIAN_DOMINANT_PROBABILITY`). "
            "Each name is also pushed into pre-write reference resolution "
            "so module-scope binding is verified. No effect when "
            "--distribution is a bare identifier."
        ),
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Run post-write `gaia build check` after a successful write (default on).",
    ),
    human: bool = typer.Option(
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt on pre-write warnings (human mode only)."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Author a ``bayes.model(hypothesis, observable=..., distribution=...)`` statement.

    Example:

    .. code-block:: bash

        gaia bayes model \
            --hypothesis mendelian_segregation_model \
            --observable f2_dominant_count \
            --distribution mendel_binomial \
            --background monohybrid_cross_setup,dominance_background \
            --rationale "Mendel predicts Binomial(N, 3/4) for F2 dominant counts." \
            --label mendel_count_model
    """
    del json_

    metadata_dict, metadata_error = parse_metadata(metadata)
    if metadata_error:
        emit_syntax_error("bayes.model", metadata_error, target=str(target), human=human)
        return

    # Axis 1 identifier-shape gates on --hypothesis / --observable.
    if not validate_identifier_flag(
        hypothesis, verb="bayes.model", flag="--hypothesis", target=str(target), human=human
    ):
        return
    if not validate_identifier_flag(
        observable, verb="bayes.model", flag="--observable", target=str(target), human=human
    ):
        return

    # Detect inline Distribution expression vs bare identifier.
    # Bare identifier → push into references for pre-write resolution.
    # Inline expression (anything with parentheses or attribute syntax) →
    # validate via the formula sandbox (which whitelists Distribution
    # factories imported from gaia.engine.lang) and skip the
    # reference-resolution path for the distribution itself.
    references_list, references_error = split_csv_idents(references)
    if references_error:
        emit_syntax_error(
            "bayes.model",
            f"--references rejected: {references_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return

    distribution_is_inline = not _BARE_IDENTIFIER_RE.match(distribution)
    if distribution_is_inline:
        try:
            validate_formula_expr(distribution, extra_names=frozenset(references_list))
        except FormulaSandboxError as exc:
            emit_syntax_error(
                "bayes.model",
                f"--distribution rejected by sandbox: {exc}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return
        # Semantic-type check on the inline shape:
        # ``ast.parse(mode="eval")`` and require Call / Attribute /
        # Name. A bare literal (``1`` / ``"foo"`` / ``[1, 2]``) fails
        # the engine at load time; reject it here at the flag boundary
        # with a precise error.
        import ast as _ast

        try:
            tree = _ast.parse(distribution, mode="eval")
        except SyntaxError as exc:
            emit_syntax_error(
                "bayes.model",
                f"--distribution is not a valid expression: {exc.msg}",
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return
        root = tree.body
        if not isinstance(root, (_ast.Call, _ast.Attribute, _ast.Name)):
            emit_syntax_error(
                "bayes.model",
                (
                    f"--distribution must be a Distribution factory call or "
                    f"reference (got {type(root).__name__}); literal values "
                    "are not Distributions"
                ),
                target=str(target),
                human=human,
                kind="prewrite.expr_unsafe",
            )
            return

    background_list, background_error = split_csv_idents(background)
    if background_error:
        emit_syntax_error(
            "bayes.model",
            f"--background rejected: {background_error}",
            target=str(target),
            human=human,
            kind="prewrite.expr_unsafe",
        )
        return
    generated_code = _render_model_statement(
        label=label,
        hypothesis=hypothesis,
        observable=observable,
        distribution=distribution,
        background=background_list,
        rationale=rationale,
        metadata=metadata_dict,
    )
    all_references = [hypothesis, observable, *background_list, *references_list]
    if not distribution_is_inline:
        all_references.insert(2, distribution)
    target_file = normalize_file_option(file)
    proposed_op = ProposedAuthorOp(
        verb="bayes.model",
        kind="reasoning",
        label=label,
        references=all_references,
        generated_code=generated_code,
        # ``bayes`` must be importable in the target file. The scaffold
        # template seeds ``from gaia.engine import bayes``; the
        # pre-write reference check accepts the dotted-call form because
        # ``bayes`` itself is the bound name in module scope.
        required_imports=("bayes",),
        target_file=target_file,
        sibling_imports=build_sibling_imports(all_references, target_file=target_file),
    )
    run_author_op(
        proposed_op,
        target=target,
        human=human,
        check=check,
        interactive=interactive,
    )


__all__ = ["model_command"]
