"""Mendel strict-reproducibility equivalence assertion.

Re-runs the cli authoring sequence documented in
``examples/mendel-v0-5-gaia/CLI-AUTHORED.md`` against a fresh temp
directory and asserts content-equivalence between the cli-authored
mirror and the hand-authored ground truth at
``examples/mendel-v0-5-gaia/``.

Multi-level tolerance
---------------------

The mendel mirror exercises the cli's bayes / Variable / observation /
multi-file capability surface.

**Closed divergences (cli capability level)**:

* Variable-targeted ``observe(..., value=...)`` produces the
  ``metadata["observation"]`` payload consumed by Bayes compare lowering.
* Inline ``Binomial(name, n=..., p=...)`` accepted on
  ``bayes.model --distribution``. The cli mirror no longer pre-binds
  helper distribution literals.
* Default ``source_id='user_priors'`` omitted when caller doesn't pass
  ``--source-id``. The cli mirror's priors.py matches the hand-authored
  omit-when-default pattern.
* Bare-identifier ``--value`` resolves against module scope, so the cli
  mirror can pass through imported constants (the cli surface is in
  place; this test exercises the literal path because the mirror passes
  literals).

Per-axis tolerance map (see ``CLI-AUTHORED.md`` §Equivalence guarantees):

* ``user-authored-contents`` — BYTE_TEXT (claim/note prose is identical).
* ``strategy-count`` / ``operator-count`` / ``total-knowledge-count`` /
  ``knowledge-type-multiset`` / ``note-types-multiset`` — BYTE_TEXT
  (structural counts identical).
* ``bayes-model-count`` / ``register-prior-count`` — BYTE_TEXT (verb
  use is identical at the engine-call level).
* ``label-bag`` — CONTENT_SET (single-``--label`` discipline can affect
  source text, while the set of distinct IR labels should match).

The helper module ``tests/cli/_equivalence_levels.py`` underwrites
both this test and the galileo test.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
)
from tests.cli._equivalence_levels import (
    ToleranceLevel,
    compare_authored,
)

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_GROUND_TRUTH_PKG = Path(__file__).resolve().parents[3] / "examples" / "mendel-v0-5-gaia"


@pytest.fixture(autouse=True)
def _isolate_mendel_imports() -> Iterator[None]:
    """Reset ``sys.path`` and ``sys.modules`` for the ``mendel_v0_5`` name.

    Same isolation discipline as ``tests/cli/galileo_demo/test_equivalence.py``:
    the cli-authored mirror and the canonical hand-authored package
    both share import name ``mendel_v0_5``; the engine loader prepends
    each package's source root to ``sys.path``, and stale entries
    persist across tests. Snapshot + restore.
    """
    path_snapshot = list(sys.path)
    modules_snapshot = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name == "mendel_v0_5" or name.startswith("mendel_v0_5.")
    }
    try:
        yield
    finally:
        sys.path[:] = path_snapshot
        for name in list(sys.modules):
            if name == "mendel_v0_5" or name.startswith("mendel_v0_5."):
                sys.modules.pop(name, None)
        sys.modules.update(modules_snapshot)


# --------------------------------------------------------------------------- #
# Cli authoring sequence — mirrors CLI-AUTHORED.md step-by-step               #
# --------------------------------------------------------------------------- #


def _parse(output: str) -> dict[str, object]:
    """Parse the last JSON envelope line from cli stdout."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in cli stdout: {output!r}")


def _scaffold_mirror(tmp_path: Path) -> Path:
    """Run ``gaia pkg scaffold`` and return the cli-authored mendel package root."""
    target = tmp_path / "mendel-cli-mirror-gaia"
    # ``--import-name`` flag is not exposed; import_name is derived
    # from --name (``mendel-v0-5-gaia`` → ``mendel_v0_5``).
    result = runner.invoke(
        app,
        [
            "pkg",
            "scaffold",
            "--target",
            str(target),
            "--name",
            "mendel-v0-5-gaia",
            "--namespace",
            "example",
            "--no-check",
        ],
    )
    assert result.exit_code == 0, f"scaffold failed: {result.output}"
    env = _parse(result.output)
    assert env["status"] == "ok"
    # Wave 1 cleanup: scaffold no longer seeds a placeholder ``hypothesis``
    # claim, so there's nothing to strip.
    return target


def _run(*args: str) -> dict[str, object]:
    """Run a single cli invocation and assert success + ok-envelope."""
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, (
        f"cli {' '.join(args)} failed (exit {result.exit_code}): {result.output}"
    )
    env = _parse(result.output)
    assert env["status"] == "ok", f"non-ok envelope: {env}"
    return env


def _author(target: Path, verb: str, *args: str) -> dict[str, object]:
    """Run a single ``gaia author <verb>`` invocation."""
    return _run("author", verb, *args, "--target", str(target), "--no-check")


def _bayes(target: Path, verb: str, *args: str) -> dict[str, object]:
    """Run a single ``gaia bayes <verb>`` invocation."""
    return _run("bayes", verb, *args, "--target", str(target), "--no-check")


def _pkg(target: Path, verb: str, *args: str) -> dict[str, object]:
    """Run a single ``gaia pkg <verb>`` invocation."""
    return _run("pkg", verb, *args, "--target", str(target))


def _author_mendel(target: Path) -> None:
    """Author the full Mendel example via the cli surface.

    Mirrors ``examples/mendel-v0-5-gaia/CLI-AUTHORED.md`` step-by-step
    in 9 sections totalling ~35 cli invocations. The narrative ordering
    matches the doc so a diff against either side stays readable.
    """
    # ---- 2. Two Variables (typed terms) ------------------------------- #
    _author(
        target,
        "variable",
        "--dsl-binding-name",
        "f2_total_count",
        "--symbol",
        "n_f2",
        "--domain",
        "Nat",
        "--value",
        "395",
    )
    _author(
        target,
        "variable",
        "--dsl-binding-name",
        "f2_dominant_count",
        "--symbol",
        "k_dominant",
        "--domain",
        "Nat",
        "--value",
        "295",
    )

    # ---- 3. Three contextual notes ----------------------------------- #
    _author(
        target,
        "note",
        (
            "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，"
            "另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。"
        ),
        "--dsl-binding-name",
        "monohybrid_cross_setup",
    )
    _author(
        target,
        "note",
        "在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。",
        "--dsl-binding-name",
        "dominance_background",
    )
    _author(
        target,
        "note",
        (
            "F2 的显性/隐性计数是有限样本，因此用点似然（二项 PMF 在观测计数处的取值）"
            "衡量模型与数据的贴合度；对手理论取 p ~ Uniform[0,1] 的 diffuse 先验作为"
            "参考尺度，不引入任何具体的替代二项参数。"
        ),
        "--dsl-binding-name",
        "finite_sample_background",
    )

    # ---- 4. Two competing-model claims + the exclusive operator ------ #
    _author(
        target,
        "claim",
        (
            "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；"
            "形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。"
        ),
        "--dsl-binding-name",
        "mendelian_segregation_model",
    )
    _author(
        target,
        "claim",
        (
            "混合遗传模型：亲本性状在后代中连续平均；一旦平均，离散的显性/隐性类别"
            "就不应在 F2 中作为可计数的类型存在。"
        ),
        "--dsl-binding-name",
        "blending_inheritance_model",
    )
    _author(
        target,
        "exclusive",
        "--a",
        "mendelian_segregation_model",
        "--b",
        "blending_inheritance_model",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。",
        "--dsl-binding-name",
        "competing_models",
    )

    # ---- 5. Four qualitative observations ---------------------------- #
    _author(
        target,
        "observe",
        "--observation-prose",
        "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "这是单因子杂交实验中 F1 代的定性观察。",
        "--dsl-binding-name",
        "f1_uniform_dominant_observation",
    )
    _author(
        target,
        "observe",
        "--observation-prose",
        "F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "这是单因子杂交实验中 F2 代的定性观察：表型呈两类，不是连续分布。",
        "--dsl-binding-name",
        "f2_has_discrete_classes_observation",
    )
    _author(
        target,
        "observe",
        "--observation-prose",
        "F1 自交得到的 F2 后代中，原隐性表型作为离散类别重新出现。",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "这是单因子杂交实验中 F2 代的定性观察。",
        "--dsl-binding-name",
        "f2_recessive_reappears_observation",
    )

    # The quantitative F2 count is a Variable-targeted measurement.
    # This is the data shape consumed by bayes.compare lowering.
    _author(
        target,
        "observe",
        "--conclusion",
        "f2_dominant_count",
        "--value",
        "295",
        "--background",
        "monohybrid_cross_setup,f2_has_discrete_classes_observation",
        "--rationale",
        "这是用于贝叶斯点似然比较的 F2 显性/隐性计数数据。",
        "--dsl-binding-name",
        "f2_count_observation",
    )

    # ---- 6. Five Mendel derivations + three matches ------------------ #
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "如果孟德尔分离模型成立，纯种显性亲本与纯种隐性亲本杂交后，"
            "F1 后代都应携带一个显性因子和一个隐性因子，并表现显性表型。"
        ),
        "--given",
        "mendelian_segregation_model",
        "--background",
        "monohybrid_cross_setup,dominance_background",
        "--rationale",
        "显性因子在杂合 F1 个体中遮蔽隐性因子。",
        "--dsl-binding-name",
        "mendel_predicts_f1_dominance",
    )
    _author(
        target,
        "equal",
        "--a",
        "mendel_predicts_f1_dominance",
        "--b",
        "f1_uniform_dominant_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "孟德尔模型对 F1 统一显性的预测与观察相符。",
        "--dsl-binding-name",
        "f1_mendel_match",
    )
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "孟德尔分离模型下 F2 的基因型组合为 AA:Aa:aa = 1:2:1，"
            "显性因子遮蔽效应把这三个基因型映射到显性和隐性两个离散表型类别，"
            "因此 F2 应呈现清晰的两类离散表型而非连续谱。"
        ),
        "--given",
        "mendelian_segregation_model",
        "--background",
        "monohybrid_cross_setup,dominance_background",
        "--rationale",
        "离散因子 + 遮蔽 → 两个离散表型类别。",
        "--dsl-binding-name",
        "mendel_predicts_discrete_classes",
    )
    _author(
        target,
        "equal",
        "--a",
        "mendel_predicts_discrete_classes",
        "--b",
        "f2_has_discrete_classes_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。",
        "--dsl-binding-name",
        "f2_discrete_classes_mendel_match",
    )
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "如果 F1 个体仍携带被遮蔽的隐性因子，那么 F1 自交后，部分 F2 个体会继承"
            "两个隐性因子并重新表现隐性表型。"
        ),
        "--given",
        "mendelian_segregation_model",
        "--background",
        "monohybrid_cross_setup,dominance_background",
        "--rationale",
        "分离模型保留了隐性因子，并允许它在 F2 中重新组合为纯合隐性。",
        "--dsl-binding-name",
        "mendel_predicts_recessive_reappearance",
    )
    _author(
        target,
        "equal",
        "--a",
        "mendel_predicts_recessive_reappearance",
        "--b",
        "f2_recessive_reappears_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "孟德尔模型对 F2 隐性重现的预测与观察相符。",
        "--dsl-binding-name",
        "f2_reappearance_mendel_match",
    )
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "如果 F1 个体自交，成对因子分离会给出 AA:Aa:aa = 1:2:1 的基因型比例；"
            "由于 AA 和 Aa 都表现显性，F2 显性/隐性计数应服从 Binomial(N, 3/4)，"
            "期望表型比约为 3:1。"
        ),
        "--given",
        "mendelian_segregation_model",
        "--background",
        "monohybrid_cross_setup,dominance_background,finite_sample_background",
        "--rationale",
        "F1 配子等概率结合，给出 1:2:1 的基因型分布，即每个 F2 个体独立以概率 3/4 表现为显性。",
        "--dsl-binding-name",
        "mendel_predicts_three_to_one_ratio",
    )

    # ---- 7. Quantitative bayes comparison ---------------------------- #
    # Inline ``Binomial(...)`` / ``BetaBinomial(...)``
    # passed via ``--distribution``. No pre-binding step; matches the
    # hand-authored shape that inlines the Distribution literal inside
    # ``bayes.model(distribution=...)``.
    _bayes(
        target,
        "model",
        "--hypothesis",
        "mendelian_segregation_model",
        "--observable",
        "f2_dominant_count",
        "--distribution",
        "Binomial('F2 dominant count under Mendel 3:1', n=395, p=3/4)",
        "--background",
        "monohybrid_cross_setup,dominance_background,finite_sample_background",
        "--rationale",
        (
            "孟德尔分离模型给出 F2 每个个体以概率 3/4 表现显性的生成模型，"
            "因此显性计数服从 Binomial(N, 3/4)。"
        ),
        "--label",
        "mendel_count_model",
    )
    _bayes(
        target,
        "model",
        "--hypothesis",
        "blending_inheritance_model",
        "--observable",
        "f2_dominant_count",
        "--distribution",
        ("BetaBinomial('F2 dominant count under p ~ Uniform[0, 1]', n=395, alpha=1.0, beta=1.0)"),
        "--background",
        "monohybrid_cross_setup,finite_sample_background",
        "--rationale",
        (
            "把对照项写成 p ~ Uniform[0, 1] 下的 BetaBinomial(N, 1, 1) 预测分布；"
            "它给出任意具体计数的边际概率 1 / (N + 1)，不人为指定第二个二项参数。"
        ),
        "--label",
        "diffuse_count_model",
    )
    _bayes(
        target,
        "compare",
        "--data",
        "f2_count_observation",
        "--model",
        "mendel_count_model",
        "--against",
        "diffuse_count_model",
        "--background",
        "monohybrid_cross_setup,finite_sample_background",
        "--rationale",
        (
            "直接比较观测到的 F2 显性计数在 Mendel 点模型和 diffuse 参考模型下的"
            "log likelihood；观测可靠性仍留在 f2_count_observation 的 prior 中。"
        ),
        "--label",
        "mendel_count_likelihood",
    )

    # ---- 8. Three Blending derivations + three contradictions ------- #
    _author(
        target,
        "derive",
        "--conclusion-prose",
        ("如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。"),
        "--given",
        "blending_inheritance_model",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "连续平均模型把亲本性状视为在后代中均化。",
        "--dsl-binding-name",
        "blending_predicts_intermediate_f1",
    )
    _author(
        target,
        "contradict",
        "--a",
        "blending_predicts_intermediate_f1",
        "--b",
        "f1_uniform_dominant_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "F1 统一显性与混合模型的中间表型预测相冲突。",
        "--dsl-binding-name",
        "f1_blending_conflict",
    )
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "如果亲本性状在 F1 中连续平均，F2 应形成单峰连续分布，"
            "不能被划分为清晰的显性/隐性两个离散类别。"
        ),
        "--given",
        "blending_inheritance_model",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "连续平均不保留可重新组合的离散遗传单位，因此不给出离散的表型分类。",
        "--dsl-binding-name",
        "blending_predicts_f2_continuous",
    )
    _author(
        target,
        "contradict",
        "--a",
        "blending_predicts_f2_continuous",
        "--b",
        "f2_has_discrete_classes_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        (
            "F2 明确划分为两类离散表型，与混合模型的连续分布预测相冲突——"
            "这是 framework 级别的冲突：blending 否认的是 F2 可被分类这件事本身。"
        ),
        "--dsl-binding-name",
        "f2_discrete_classes_blending_conflict",
    )
    _author(
        target,
        "derive",
        "--conclusion-prose",
        (
            "连续平均的性状不保留可以重新组合的离散遗传单位，"
            "因此原隐性表型不应作为离散类别在 F2 中重新出现。"
        ),
        "--given",
        "blending_inheritance_model",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "混合模型没有保留可重新组合的离散隐性因子。",
        "--dsl-binding-name",
        "blending_predicts_no_recessive_reappearance",
    )
    _author(
        target,
        "contradict",
        "--a",
        "blending_predicts_no_recessive_reappearance",
        "--b",
        "f2_recessive_reappears_observation",
        "--background",
        "monohybrid_cross_setup",
        "--rationale",
        "F2 隐性表型作为离散类别重新出现，与混合模型的预测相冲突。",
        "--dsl-binding-name",
        "f2_reappearance_blending_conflict",
    )

    # ---- 9. Scaffold priors.py + register the 6 priors --------------- #
    _pkg(target, "add-module", "--name", "priors", "--imports", "register_prior")
    _author(
        target,
        "register-prior",
        "--claim",
        "mendelian_segregation_model",
        "--value",
        "0.5",
        "--justification",
        "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。",
        "--file",
        "priors.py",
    )
    _author(
        target,
        "register-prior",
        "--claim",
        "blending_inheritance_model",
        "--value",
        "0.5",
        "--justification",
        "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。",
        "--file",
        "priors.py",
    )
    _author(
        target,
        "register-prior",
        "--claim",
        "f1_uniform_dominant_observation",
        "--value",
        "0.95",
        "--justification",
        "把 F1 统一显性作为可靠的实验观察。",
        "--file",
        "priors.py",
    )
    _author(
        target,
        "register-prior",
        "--claim",
        "f2_has_discrete_classes_observation",
        "--value",
        "0.95",
        "--justification",
        "把 F2 呈两类离散表型作为可靠的实验观察。",
        "--file",
        "priors.py",
    )
    _author(
        target,
        "register-prior",
        "--claim",
        "f2_recessive_reappears_observation",
        "--value",
        "0.95",
        "--justification",
        "把 F2 隐性表型重新出现作为可靠的实验观察。",
        "--file",
        "priors.py",
    )
    _author(
        target,
        "register-prior",
        "--claim",
        "f2_count_observation",
        "--value",
        "0.95",
        "--justification",
        "把 F2 显性/隐性计数作为可靠的实验观察。",
        "--file",
        "priors.py",
    )


# --------------------------------------------------------------------------- #
# IR loaders + projections                                                    #
# --------------------------------------------------------------------------- #


def _compile_ir(pkg_root: Path) -> dict[str, object]:
    """Programmatic ``gaia build compile`` — returns the IR as a dict."""
    loaded = load_gaia_package(pkg_root)
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    return compiled.to_json()


def _user_authored_contents(ir: dict[str, object]) -> list[str]:
    """Project the IR down to user-authored content strings.

    Excludes auto-generated warrant claims (``derive warrants ...``,
    ``observe warrants ...``, ``implies(...)``, etc.) and operator-
    minted helper claims (``exactly one of ...``, ``... and ...``) so
    only the contents an author actually wrote remain. Inline-prose
    closure means both sides emit the same auto-warrant strings
    byte-for-byte, but excluding them keeps the assertion focused on
    user-authored data.
    """
    skip_prefixes = (
        "derive warrants ",
        "observe warrants ",
        "implies(",
        "exactly one of ",
    )
    contents: list[str] = []
    for k in ir["knowledges"]:  # type: ignore[index]
        content: str = k["content"]  # type: ignore[index]
        if any(content.startswith(p) for p in skip_prefixes):
            continue
        # The exclusive operator mints an XOR helper claim of shape
        # ``<a-content> and <b-content>``-ish; filter by detecting the
        # operator-helper marker (engine-internal; "and" appearing
        # mid-content is enough of a heuristic for this fixture).
        if " and " in content and not content.endswith("。"):
            continue
        contents.append(content)
    return sorted(contents)


def _knowledge_type_multiset(ir: dict[str, object]) -> list[str]:
    """Multiset of knowledge ``type`` fields, as a sorted list."""
    return sorted(k.get("type", "<unknown>") for k in ir["knowledges"])  # type: ignore[union-attr]


def _strategy_count(ir: dict[str, object]) -> list[int]:
    """Single-element list with the strategy count (so BYTE_TEXT axis fits)."""
    return [len(ir["strategies"])]  # type: ignore[arg-type]


def _operator_count(ir: dict[str, object]) -> list[int]:
    """Single-element list with the operator count."""
    return [len(ir["operators"])]  # type: ignore[arg-type]


def _knowledge_count(ir: dict[str, object]) -> list[int]:
    """Single-element list with the total knowledge count."""
    return [len(ir["knowledges"])]  # type: ignore[arg-type]


def _label_bag(ir: dict[str, object]) -> list[str]:
    """The set of labels visible on knowledge nodes / strategies / operators.

    Used at CONTENT_SET tolerance — the single-``--label`` discipline +
    pre-bound distribution bindings cause multiset differences between
    cli-authored and hand-authored shapes, but the set of distinct
    labels referenced anywhere is invariant.
    """
    labels: set[str] = set()
    for k in ir["knowledges"]:  # type: ignore[index]
        label = k.get("label")  # type: ignore[union-attr]
        if isinstance(label, str) and label:
            labels.add(label)
    for s in ir["strategies"]:  # type: ignore[index]
        label = s.get("label")  # type: ignore[union-attr]
        if isinstance(label, str) and label:
            labels.add(label)
    for op in ir["operators"]:  # type: ignore[index]
        label = op.get("label")  # type: ignore[union-attr]
        if isinstance(label, str) and label:
            labels.add(label)
    return sorted(labels)


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_mendel_cli_authoring_compiles(tmp_path: Path) -> None:
    """The cli authoring sequence produces a package that compiles cleanly.

    Smoke test — equivalence assertions below all require a clean
    compile, so this surfaces compilation failure as a discrete error
    rather than a confusing equivalence mismatch.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)
    ir = _compile_ir(mirror)
    assert ir["knowledges"], "cli-authored mendel package compiled to zero knowledges"
    assert ir["package_name"]


def test_mendel_user_authored_contents_byte_text(tmp_path: Path) -> None:
    """User-authored content strings match BYTE_TEXT (inline-prose closure).

    The primary strict-reproducibility invariant: every Claim or note
    content string the author wrote in the hand-authored file appears
    byte-identical in the cli-authored compiled IR. Auto-warrant
    claims are filtered (handled in galileo's test too; same shape).
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    hand_ir = _compile_ir(_GROUND_TRUTH_PKG)
    cli_ir = _compile_ir(mirror)

    hand_contents = _user_authored_contents(hand_ir)
    cli_contents = _user_authored_contents(cli_ir)

    report = compare_authored(
        axis_tolerance_map={"user-authored-contents": ToleranceLevel.BYTE_TEXT},
        axis_projection={
            "user-authored-contents": (hand_contents, cli_contents),
        },
    )
    assert report.passed, report.format()


def test_mendel_structural_counts_byte_text(tmp_path: Path) -> None:
    """Strategy / operator / total-knowledge / type-multiset counts match BYTE_TEXT.

    All structural counts and the knowledge-type multiset must match
    byte-for-byte: the cli-authored mirror compiles to the same
    44 / 9 / 7 shape as the hand-authored package.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    hand_ir = _compile_ir(_GROUND_TRUTH_PKG)
    cli_ir = _compile_ir(mirror)

    report = compare_authored(
        axis_tolerance_map={
            "strategy-count": ToleranceLevel.BYTE_TEXT,
            "operator-count": ToleranceLevel.BYTE_TEXT,
            "total-knowledge-count": ToleranceLevel.BYTE_TEXT,
            "knowledge-type-multiset": ToleranceLevel.BYTE_TEXT,
        },
        axis_projection={
            "strategy-count": (_strategy_count(hand_ir), _strategy_count(cli_ir)),
            "operator-count": (_operator_count(hand_ir), _operator_count(cli_ir)),
            "total-knowledge-count": (_knowledge_count(hand_ir), _knowledge_count(cli_ir)),
            "knowledge-type-multiset": (
                _knowledge_type_multiset(hand_ir),
                _knowledge_type_multiset(cli_ir),
            ),
        },
    )
    assert report.passed, report.format()

    # Defensive lower bounds — Mendel v0.5 ships these counts.
    assert _strategy_count(hand_ir) == [9]
    assert _operator_count(hand_ir) == [7]
    assert _knowledge_count(hand_ir) == [44]


def test_mendel_label_bag_content_set(tmp_path: Path) -> None:
    """Label-bag axis matches at CONTENT_SET (intrinsic single-``--label`` axis).

    The single-``--label`` discipline forces every cli statement to
    render ``label=``; some hand-authored statements omit the kwarg
    when the binding name happens to equal the label. The set of distinct
    labels is the stable IR-level comparison axis.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    hand_ir = _compile_ir(_GROUND_TRUTH_PKG)
    cli_ir = _compile_ir(mirror)

    hand_labels = set(_label_bag(hand_ir))
    cli_labels = set(_label_bag(cli_ir))

    # The cli inlines ``Binomial(...)`` /
    # ``BetaBinomial(...)`` directly in --distribution, matching
    # the hand-authored shape; no extra Distribution-binding labels
    # (``mendel_count_distribution`` / ``diffuse_count_distribution``)
    # are minted.
    missing = hand_labels - cli_labels
    assert not missing, f"hand-authored labels missing from cli mirror: {sorted(missing)}"


def test_mendel_bayes_engine_invocation_round_trip(tmp_path: Path) -> None:
    """The cli-authored bayes statements load + compile through the engine.

    A targeted sanity check that the cli's bayes.model / bayes.compare
    rendering survives the engine round trip — the hand-authored test
    side will have already exercised this on the canonical package; the
    cli mirror just needs to produce a clean IR.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)
    cli_ir = _compile_ir(mirror)
    # Filter knowledges that carry a bayes-derived label or come from
    # bayes.model / bayes.compare helper claims (they show up as
    # claim knowledges in the IR with their helper label).
    bayes_labels = {"mendel_count_model", "diffuse_count_model", "mendel_count_likelihood"}
    cli_labels = {
        k.get("label")  # type: ignore[union-attr]
        for k in cli_ir["knowledges"]  # type: ignore[index]
        if isinstance(k.get("label"), str)  # type: ignore[union-attr]
    }
    missing = bayes_labels - cli_labels
    assert not missing, f"bayes helper labels missing from cli mirror IR: {missing}"


def test_mendel_register_prior_in_sibling_module(tmp_path: Path) -> None:
    """All 6 ``register_prior`` calls landed in ``priors.py``, not ``__init__.py``.

    The multi-file plumbing is what makes mendel's hand-authored layout
    (``priors.py`` sibling module) reproducible via cli. This test
    verifies the cli sequence routed the prior records to the sibling
    module rather than the main authoring file.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    # CLI-authored statements + priors land in the composed authored/
    # submodule (canon), not the package-root __init__.py.
    init_path = mirror / "src" / "mendel_v0_5" / "authored" / "__init__.py"
    priors_path = mirror / "src" / "mendel_v0_5" / "authored" / "priors.py"

    assert priors_path.exists(), "authored/priors.py must be scaffolded via pkg add-module"
    init_text = init_path.read_text()
    priors_text = priors_path.read_text()

    # priors.py must hold all 6 register_prior calls; __init__.py must
    # hold zero.
    assert priors_text.count("register_prior(") == 6, (
        f"expected 6 register_prior calls in priors.py, got {priors_text.count('register_prior(')}"
    )
    assert "register_prior(" not in init_text, (
        "register_prior calls leaked into __init__.py instead of priors.py"
    )


# --------------------------------------------------------------------------- #
# Source-shape closure — BYTE_TEXT axes                                       #
# --------------------------------------------------------------------------- #


def test_mendel_register_prior_omits_default_source_id(tmp_path: Path) -> None:
    """Cli mirror's priors.py omits default source_id.

    Hand-authored priors.py never renders ``source_id=`` because it
    relies on the engine default. The cli mirror does the same when
    ``--source-id`` is not passed. This axis asserts BYTE_TEXT closure:
    zero ``source_id=`` mentions in either side's priors.py.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    cli_priors = (mirror / "src" / "mendel_v0_5" / "authored" / "priors.py").read_text()
    hand_priors = (_GROUND_TRUTH_PKG / "src" / "mendel_v0_5" / "priors.py").read_text()

    report = compare_authored(
        axis_tolerance_map={"source-id-count": ToleranceLevel.BYTE_TEXT},
        axis_projection={
            "source-id-count": (
                [hand_priors.count("source_id=")],
                [cli_priors.count("source_id=")],
            ),
        },
    )
    assert report.passed, report.format()
    # Defensive lower bound — hand-authored mendel never writes source_id=.
    assert hand_priors.count("source_id=") == 0


def test_mendel_count_observation_uses_variable_value(tmp_path: Path) -> None:
    """Cli mirror records the F2 count as observe(Variable, value=...)."""
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    cli_init = (mirror / "src" / "mendel_v0_5" / "authored" / "__init__.py").read_text()
    observation_lines = [
        line for line in cli_init.splitlines() if line.startswith("f2_count_observation = observe(")
    ]
    assert observation_lines, "cli mirror missing f2_count_observation"
    observation_line = observation_lines[0]
    assert "observe(f2_dominant_count" in observation_line
    assert "value=295" in observation_line


def test_mendel_bayes_model_inline_distribution(tmp_path: Path) -> None:
    """bayes.model emits inline bare Distribution factories in source.

    Hand-authored: ``bayes.model(..., distribution=Binomial("name", n=..., p=...))``.
    The cli matches that shape by emitting the inline Distribution
    expression directly via ``--distribution 'Binomial(...)'``; no
    separate pre-binding ``mendel_count_distribution = Binomial(...)``
    line is minted.
    """
    mirror = _scaffold_mirror(tmp_path)
    _author_mendel(mirror)

    cli_init = (mirror / "src" / "mendel_v0_5" / "authored" / "__init__.py").read_text()
    # The mendel_count_model line should embed the inline Distribution
    # expression directly.
    assert (
        "distribution=Binomial('F2 dominant count under Mendel 3:1', n=395, p=3/4)" in cli_init
    ), "bayes.model did not inline Binomial(...)"
    assert (
        "distribution=BetaBinomial('F2 dominant count under p ~ Uniform[0, 1]', "
        "n=395, alpha=1.0, beta=1.0)" in cli_init
    ), "bayes.model did not inline BetaBinomial(...)"
    # The cli mirror does not emit standalone pre-binding lines.
    assert "mendel_count_distribution =" not in cli_init, (
        "unexpected pre-bound distribution emitted"
    )
    assert "diffuse_count_distribution =" not in cli_init, (
        "unexpected pre-bound distribution emitted"
    )
