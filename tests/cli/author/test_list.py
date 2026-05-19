"""CLI E2E tests for ``gaia author list``.

Pure-AST verb that walks a Gaia package's source files and reports
every top-level author-verb statement. The tests cover all 19
recognised callable shapes, the two-statement ``claim`` + ``.label = ``
folding, reassignment shadow detection, ``__all__`` permutations,
syntax-error graceful failure, auxiliary-file skipping, ``--file``
scoping (including the auxiliary-file warning), ``--kind`` filtering,
``--unbound`` bare-call inclusion, the compositions section reader,
and the round-trip from ``gaia author claim`` → ``gaia author list``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _parse(output: str) -> dict[str, object]:
    """Pluck the JSON envelope (last brace-prefixed line) out of stdout."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def _write_init(pkg: FixturePackage, body: str) -> None:
    """Overwrite the package's ``__init__.py`` with ``body``."""
    pkg.source_init.write_text(body, encoding="utf-8")


def _invoke_list(pkg: FixturePackage, *extra: str) -> tuple[int, str]:
    """Run ``gaia author list --target <pkg.root>`` with extra args."""
    result = runner.invoke(
        app,
        ["author", "list", "--target", str(pkg.root), *extra],
    )
    return result.exit_code, result.output


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


def test_list_default_target_seeded_fixture(gaia_package: FixturePackage) -> None:
    """The freshly-scaffolded fixture has two seed claims; list returns both."""
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    envelope = _parse(output)
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    bindings = payload["bindings"]
    assert isinstance(bindings, list)
    names = sorted(b["name"] for b in bindings)
    assert names == ["hypothesis", "observation"]
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["by_kind"] == {"claim": 2}
    assert payload["summary"]["exported"] == 2


def test_list_human_renders_table(gaia_package: FixturePackage) -> None:
    """``--human`` produces a table with header + summary line."""
    code, output = _invoke_list(gaia_package, "--human")
    assert code == 0, output
    assert "Kind" in output and "Name" in output and "Exported" in output
    assert "hypothesis" in output and "observation" in output
    assert "2 bindings across 1 file" in output


# --------------------------------------------------------------------------- #
# 19 callable shapes — coverage                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "snippet,expected_kind",
    [
        ('x = claim("c")', "claim"),
        ('x = note("n")', "note"),
        ('x = question("q")', "question"),
        ("x = equal(a, b)", "equal"),
        ("x = contradict(a, b)", "contradict"),
        ("x = exclusive(a, b)", "exclusive"),
        ("x = decompose(whole=a, parts=[b, c])", "decompose"),
        ("x = derive(conclusion=a, given=[b])", "derive"),
        ('x = observe("o")', "observe"),
        ('x = compute("c", fn=lambda: 1)', "compute"),
        ("x = infer(a, given=[b])", "infer"),
        ("x = associate(a, b)", "associate"),
        ("x = parameter(v)", "parameter"),
        ("x = register_prior(c, value=0.5)", "register_prior"),
        ('x = Variable(symbol="s", domain=Nat)', "variable"),
        ("x = Constant(1, Nat)", "constant"),
        ("x = depends_on(a, given=[b])", "depends_on"),
        ("x = candidate_relation(a, b)", "candidate_relation"),
        ("x = materialize(a, b)", "materialize"),
    ],
)
def test_each_callable_shape_maps_to_kind(
    gaia_package: FixturePackage, snippet: str, expected_kind: str
) -> None:
    """Every recognised author callable maps to its expected ``kind``."""
    # Replace fixture body with a single recognisable statement. The
    # imports don't have to actually resolve — we're parsing AST only.
    body = (
        "from gaia.engine.lang import (\n"
        "    claim, note, question, equal, contradict, exclusive,\n"
        "    decompose, derive, observe, compute, infer, associate,\n"
        "    parameter, register_prior, Variable, Constant,\n"
        "    depends_on, candidate_relation, materialize,\n"
        "    Nat,\n"
        ")\n"
        f"a = claim('seed a')\n"
        f"b = claim('seed b')\n"
        f"c = claim('seed c')\n"
        f"v = Variable(symbol='v', domain=Nat)\n"
        f"{snippet}\n"
        "__all__ = ['a', 'b', 'c', 'v', 'x']\n"
    )
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    envelope = _parse(output)
    bindings = envelope["payload"]["bindings"]  # type: ignore[index]
    assert isinstance(bindings, list)
    # The expected binding is the one bound to ``x``.
    x_rows = [b for b in bindings if b["name"] == "x"]
    assert len(x_rows) == 1, bindings
    assert x_rows[0]["kind"] == expected_kind


# --------------------------------------------------------------------------- #
# claim + .label two-statement pair                                           #
# --------------------------------------------------------------------------- #


def test_claim_label_pair_is_folded(gaia_package: FixturePackage) -> None:
    """``foo = claim(...)`` + ``foo.label = "..."`` collapse into one row."""
    body = (
        "from gaia.engine.lang import claim\n"
        "hyp = claim('A real claim.')\n"
        "hyp.label = 'the real label'\n"
        "__all__ = ['hyp']\n"
    )
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    bindings = _parse(output)["payload"]["bindings"]  # type: ignore[index]
    assert isinstance(bindings, list)
    rows = [b for b in bindings if b["name"] == "hyp"]
    assert len(rows) == 1
    assert rows[0]["kind"] == "claim"
    assert rows[0]["label"] == "the real label"


# --------------------------------------------------------------------------- #
# Variable vs Constant split                                                  #
# --------------------------------------------------------------------------- #


def test_variable_and_constant_are_distinct_kinds(gaia_package: FixturePackage) -> None:
    """``Variable(...)`` and ``Constant(...)`` produce distinct ``kind`` values."""
    body = (
        "from gaia.engine.lang import Variable, Constant, Nat\n"
        "v = Variable(symbol='v', domain=Nat)\n"
        "c = Constant(42, Nat)\n"
        "__all__ = ['v', 'c']\n"
    )
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    by_name = {b["name"]: b["kind"] for b in _parse(output)["payload"]["bindings"]}  # type: ignore[index]
    assert by_name == {"v": "variable", "c": "constant"}


# --------------------------------------------------------------------------- #
# Reassignment / shadow detection                                             #
# --------------------------------------------------------------------------- #


def test_reassignment_marks_shadowed_by(gaia_package: FixturePackage) -> None:
    """Two writes to the same name → earlier carries ``shadowed_by``."""
    body = (
        "from gaia.engine.lang import claim, derive\n"
        "a = claim('seed')\n"
        "foo = claim('first def')\n"
        "foo = derive(conclusion=a, given=[a])\n"
        "__all__ = ['a', 'foo']\n"
    )
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    bindings = _parse(output)["payload"]["bindings"]  # type: ignore[index]
    foo_rows = [b for b in bindings if b["name"] == "foo"]
    assert len(foo_rows) == 2
    # The earlier (claim) carries shadowed_by, the later (derive) does not.
    earlier = next(b for b in foo_rows if b["kind"] == "claim")
    later = next(b for b in foo_rows if b["kind"] == "derive")
    assert earlier["shadowed_by"] == later["line"]
    assert later["shadowed_by"] is None


# --------------------------------------------------------------------------- #
# __all__ permutations                                                        #
# --------------------------------------------------------------------------- #


def test_dynamic_all_warns_and_marks_exported_null(gaia_package: FixturePackage) -> None:
    """``__all__ = sorted([...])`` (non-literal) → warning + ``exported = None``."""
    body = "from gaia.engine.lang import claim\na = claim('content')\n__all__ = sorted(['a'])\n"
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    envelope = _parse(output)
    assert any("dynamic" in w for w in envelope["warnings"])  # type: ignore[index]
    bindings = envelope["payload"]["bindings"]  # type: ignore[index]
    assert all(b["exported"] is None for b in bindings)


def test_missing_all_marks_exported_false(gaia_package: FixturePackage) -> None:
    """No ``__all__`` at top level → every binding is ``exported = False``."""
    body = "from gaia.engine.lang import claim\na = claim('content')\nb = claim('more')\n"
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    bindings = _parse(output)["payload"]["bindings"]  # type: ignore[index]
    assert all(b["exported"] is False for b in bindings)


# --------------------------------------------------------------------------- #
# Empty / syntax-error files                                                  #
# --------------------------------------------------------------------------- #


def test_empty_init_returns_zero_bindings(gaia_package: FixturePackage) -> None:
    """An empty ``__init__.py`` returns ``total = 0`` with exit 0."""
    _write_init(gaia_package, "")
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    envelope = _parse(output)
    assert envelope["payload"]["bindings"] == []  # type: ignore[index]
    assert envelope["payload"]["summary"]["total"] == 0  # type: ignore[index]


def test_syntax_error_surfaces_diagnostic_and_nonzero_exit(gaia_package: FixturePackage) -> None:
    """A syntax-broken file → exit 2 (EXIT_INPUT_SYNTAX) with a ``prewrite.syntax`` diagnostic."""
    _write_init(gaia_package, "def foo(:\n    pass\n")
    code, output = _invoke_list(gaia_package)
    assert code == 2, output
    envelope = _parse(output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert any(d["kind"] == "prewrite.syntax" for d in diags)


# --------------------------------------------------------------------------- #
# Auxiliary skip + --file flag                                                #
# --------------------------------------------------------------------------- #


def test_priors_py_is_skipped(gaia_package: FixturePackage) -> None:
    """A ``priors.py`` sibling file is excluded from the default walk."""
    (gaia_package.source_init.parent / "priors.py").write_text(
        "from gaia.engine.lang import register_prior\nx = register_prior('aux', value=0.5)\n",
        encoding="utf-8",
    )
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    files = {b["file"] for b in _parse(output)["payload"]["bindings"]}  # type: ignore[index]
    assert "priors.py" not in files


def test_review_py_is_skipped(gaia_package: FixturePackage) -> None:
    """``review.py`` sibling is excluded just like ``priors.py``."""
    (gaia_package.source_init.parent / "review.py").write_text(
        "from gaia.engine.lang import note\nx = note('aux')\n",
        encoding="utf-8",
    )
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    files = {b["file"] for b in _parse(output)["payload"]["bindings"]}  # type: ignore[index]
    assert "review.py" not in files


def test_reviews_subdir_is_skipped(gaia_package: FixturePackage) -> None:
    """Any ``reviews/<sub>.py`` file is excluded from the walk."""
    reviews_dir = gaia_package.source_init.parent / "reviews"
    reviews_dir.mkdir()
    (reviews_dir / "__init__.py").write_text("")
    (reviews_dir / "panel.py").write_text(
        "from gaia.engine.lang import claim\nx = claim('rev')\n",
        encoding="utf-8",
    )
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    files = {b["file"] for b in _parse(output)["payload"]["bindings"]}  # type: ignore[index]
    assert not any("reviews" in f for f in files)


def test_file_flag_pointing_at_auxiliary_warns(gaia_package: FixturePackage) -> None:
    """``--file priors.py`` emits a warning but still scans the file."""
    (gaia_package.source_init.parent / "priors.py").write_text(
        "from gaia.engine.lang import register_prior\n",
        encoding="utf-8",
    )
    code, output = _invoke_list(gaia_package, "--file", "priors.py")
    assert code == 0, output
    envelope = _parse(output)
    assert any("auxiliary" in w for w in envelope["warnings"])  # type: ignore[index]


# --------------------------------------------------------------------------- #
# --kind filter                                                               #
# --------------------------------------------------------------------------- #


def test_kind_filter_restricts_output(gaia_package: FixturePackage) -> None:
    """``--kind claim`` returns only claim bindings."""
    body = (
        "from gaia.engine.lang import claim, observe, parameter, Variable, Nat\n"
        "v = Variable(symbol='v', domain=Nat)\n"
        "a = claim('hello')\n"
        "o = observe('seen')\n"
        "p = parameter(v)\n"
        "__all__ = ['a', 'o', 'p', 'v']\n"
    )
    _write_init(gaia_package, body)
    code, output = _invoke_list(gaia_package, "--kind", "claim")
    assert code == 0, output
    bindings = _parse(output)["payload"]["bindings"]  # type: ignore[index]
    assert {b["kind"] for b in bindings} == {"claim"}
    assert {b["name"] for b in bindings} == {"a"}


# --------------------------------------------------------------------------- #
# --unbound bare expressions                                                  #
# --------------------------------------------------------------------------- #


def test_unbound_flag_includes_bare_calls(gaia_package: FixturePackage) -> None:
    """Bare ``register_prior(...)`` calls only surface under ``--unbound``."""
    body = (
        "from gaia.engine.lang import claim, register_prior\n"
        "a = claim('seed')\n"
        "register_prior(a, value=0.5)\n"
        "__all__ = ['a']\n"
    )
    _write_init(gaia_package, body)

    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    bindings = _parse(output)["payload"]["bindings"]  # type: ignore[index]
    assert all(b["name"] is not None for b in bindings)  # bare call hidden

    code2, output2 = _invoke_list(gaia_package, "--unbound")
    assert code2 == 0, output2
    bindings2 = _parse(output2)["payload"]["bindings"]  # type: ignore[index]
    unbound_rows = [b for b in bindings2 if b["name"] is None]
    assert len(unbound_rows) == 1
    assert unbound_rows[0]["kind"] == "register_prior"


# --------------------------------------------------------------------------- #
# Compositions section                                                        #
# --------------------------------------------------------------------------- #


def test_compositions_section_appears_when_pyproject_has_entries(
    gaia_package: FixturePackage,
) -> None:
    """A ``[[tool.gaia.compositions]]`` entry shows up in payload + human output."""
    pyproject = gaia_package.root / "pyproject.toml"
    extra = (
        "\n[[tool.gaia.compositions]]\n"
        'name = "galileo_v05"\n'
        'version = "1.0"\n'
        'file = "/abs/path/to/pattern.py"\n'
        'function = "galileo_v05"\n'
        'registered_at = "2026-05-19T00:00:00+00:00"\n'
    )
    pyproject.write_text(pyproject.read_text() + extra)
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    compositions = _parse(output)["payload"]["compositions"]  # type: ignore[index]
    assert isinstance(compositions, list)
    assert len(compositions) == 1
    assert compositions[0]["name"] == "galileo_v05"
    assert compositions[0]["version"] == "1.0"

    code2, output2 = _invoke_list(gaia_package, "--human")
    assert code2 == 0, output2
    assert "Compositions registered" in output2
    assert "galileo_v05" in output2


def test_compositions_section_absent_when_pyproject_empty(
    gaia_package: FixturePackage,
) -> None:
    """No compositions entries → JSON array is empty, human section absent."""
    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    assert _parse(output)["payload"]["compositions"] == []  # type: ignore[index]
    code2, output2 = _invoke_list(gaia_package, "--human")
    assert code2 == 0, output2
    assert "Compositions registered" not in output2


# --------------------------------------------------------------------------- #
# Target validation                                                           #
# --------------------------------------------------------------------------- #


def test_missing_target_exits_4(tmp_path: Path) -> None:
    """Target pointing at a non-existent dir exits with EXIT_SYSTEM_IO=4."""
    result = runner.invoke(app, ["author", "list", "--target", str(tmp_path / "nope")])
    assert result.exit_code == 4, result.output


def test_target_not_gaia_package_exits_4(tmp_path: Path) -> None:
    """A non-Gaia pyproject path exits with EXIT_SYSTEM_IO=4."""
    root = tmp_path / "plain"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "plain"\nversion = "0.1.0"\n')
    result = runner.invoke(app, ["author", "list", "--target", str(root)])
    assert result.exit_code == 4, result.output


# --------------------------------------------------------------------------- #
# Help snapshot (smoke)                                                       #
# --------------------------------------------------------------------------- #


def test_help_output_includes_flags() -> None:
    """``gaia author list --help`` mentions every documented flag.

    Strips ANSI escape codes before asserting: under ``FORCE_COLOR=1`` (CI),
    Rich injects color codes between the two hyphens of each flag name,
    breaking the literal ``--flag`` substring in the raw output.
    """
    result = runner.invoke(app, ["author", "list", "--help"])
    assert result.exit_code == 0, result.output
    plain = _ANSI_RE.sub("", result.output)
    for flag in ("--target", "--file", "--kind", "--unbound", "--human", "--json"):
        assert flag in plain, f"missing {flag} in --help text"


def test_author_group_help_lists_list_verb() -> None:
    """``gaia author --help`` includes ``list`` in the verbs description."""
    result = runner.invoke(app, ["author", "--help"])
    assert result.exit_code == 0, result.output
    assert "list" in result.output


# --------------------------------------------------------------------------- #
# Round-trip: author claim → author list                                      #
# --------------------------------------------------------------------------- #


def test_round_trip_author_claim_then_list(gaia_package: FixturePackage) -> None:
    """Scaffold a claim via ``gaia author claim``, then verify ``list`` sees it."""
    add_result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Fresh round-trip claim.",
            "--dsl-binding-name",
            "round_trip",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert add_result.exit_code == 0, add_result.output

    code, output = _invoke_list(gaia_package)
    assert code == 0, output
    names = {b["name"] for b in _parse(output)["payload"]["bindings"]}  # type: ignore[index]
    assert "round_trip" in names
