"""R3 tests for ``gaia author compose`` / ``gaia author composition``.

R3·❓D=A — file-based validate-and-register. The cli reads a Python file
containing exactly one ``@compose`` / ``@composition``-decorated
function, validates the shape, and inserts/updates an entry in the
target package's ``[[tool.gaia.compositions]]`` pyproject table.

These tests cover:

* happy path: one well-shaped function + valid pyproject → exit 0,
  pyproject gains the compositions entry.
* count = 0 → exit 2 with diagnostic.
* count >= 2 → exit 2 with diagnostic listing function names.
* decorator missing name= / version= kwargs → exit 2.
* wrong return annotation → exit 2.
* invalid target → exit 4 (system IO).
* idempotency: re-running for the same composition name updates in place.
* ``composition`` alias verb shares the same impl.
* ``--help`` epilog contains the example.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def _write_compose_file(path: Path, *, body: str) -> None:
    path.write_text(body, encoding="utf-8")


_VALID_PATTERN = """\
from gaia.engine.lang import compose, derive
from gaia.engine.lang.runtime.knowledge import Claim


@compose(name="my-pkg:my-pattern", version="1.0")
def my_pattern(input_claim: Claim) -> Claim:
    result = derive(input_claim, given=[input_claim], label="warranted")
    return result
"""

_ZERO_COMPOSE_FILE = """\
from gaia.engine.lang import claim


def regular_function() -> object:
    return claim("not a composition")
"""

_TWO_COMPOSE_FILE = """\
from gaia.engine.lang import compose
from gaia.engine.lang.runtime.knowledge import Claim


@compose(name="pkg:first", version="1.0")
def first(c: Claim) -> Claim:
    return c


@compose(name="pkg:second", version="1.0")
def second(c: Claim) -> Claim:
    return c
"""

_MISSING_KWARGS_FILE = """\
from gaia.engine.lang import compose
from gaia.engine.lang.runtime.knowledge import Claim


@compose()
def naked(c: Claim) -> Claim:
    return c
"""

_WRONG_RETURN_FILE = """\
from gaia.engine.lang import compose


@compose(name="pkg:wrong", version="1.0")
def wrong_return(c) -> int:
    return 42
"""

_NO_RETURN_ANNOTATION = """\
from gaia.engine.lang import compose


@compose(name="pkg:noann", version="1.0")
def no_ann(c):
    return c
"""

_COMPOSITION_ALIAS_FILE = """\
from gaia.engine.lang import composition
from gaia.engine.lang.runtime.knowledge import Claim


@composition(name="alias:pkg", version="2.0")
def aliased(c: Claim) -> Claim:
    return c
"""


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


def test_compose_happy_path_registers_in_pyproject(
    gaia_package: FixturePackage, tmp_path: Path
) -> None:
    pattern = tmp_path / "pattern.py"
    _write_compose_file(pattern, body=_VALID_PATTERN)

    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["status"] == "ok"
    assert envelope["verb"] == "compose"
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    assert payload["composition_name"] == "my-pkg:my-pattern"
    assert payload["composition_version"] == "1.0"
    assert payload["function"] == "my_pattern"

    # Confirm the pyproject table was updated.
    pp = (gaia_package.root / "pyproject.toml").read_text()
    cfg = tomllib.loads(pp)
    comps = cfg["tool"]["gaia"]["compositions"]
    assert isinstance(comps, list)
    assert len(comps) == 1
    entry = comps[0]
    assert entry["name"] == "my-pkg:my-pattern"
    assert entry["version"] == "1.0"
    assert entry["function"] == "my_pattern"
    assert entry["registered_at"]


def test_compose_idempotent_overwrite(gaia_package: FixturePackage, tmp_path: Path) -> None:
    """Re-running compose with the same name updates the entry in place."""
    pattern = tmp_path / "pattern.py"
    _write_compose_file(pattern, body=_VALID_PATTERN)

    runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )

    # Second run with the same content.
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    cfg = tomllib.loads((gaia_package.root / "pyproject.toml").read_text())
    comps = cfg["tool"]["gaia"]["compositions"]
    assert len(comps) == 1, comps


def test_compose_second_distinct_name_appends_entry(
    gaia_package: FixturePackage, tmp_path: Path
) -> None:
    """A distinct composition name is added without disturbing existing ones."""
    pattern_a = tmp_path / "a.py"
    _write_compose_file(pattern_a, body=_VALID_PATTERN)
    runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern_a),
            "--target",
            str(gaia_package.root),
        ],
    )

    pattern_b = tmp_path / "b.py"
    _write_compose_file(pattern_b, body=_COMPOSITION_ALIAS_FILE)
    result = runner.invoke(
        app,
        [
            "author",
            "composition",
            "--from-file",
            str(pattern_b),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output

    cfg = tomllib.loads((gaia_package.root / "pyproject.toml").read_text())
    comps = cfg["tool"]["gaia"]["compositions"]
    names = {c["name"] for c in comps}
    assert names == {"my-pkg:my-pattern", "alias:pkg"}


# --------------------------------------------------------------------------- #
# Count != 1 rejection                                                        #
# --------------------------------------------------------------------------- #


def test_compose_zero_functions_exits_2(gaia_package: FixturePackage, tmp_path: Path) -> None:
    pattern = tmp_path / "empty.py"
    _write_compose_file(pattern, body=_ZERO_COMPOSE_FILE)

    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "no @compose" in diags[0]["message"]


def test_compose_two_functions_exits_2(gaia_package: FixturePackage, tmp_path: Path) -> None:
    pattern = tmp_path / "two.py"
    _write_compose_file(pattern, body=_TWO_COMPOSE_FILE)

    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    message = diags[0]["message"]
    assert "multiple" in message
    assert "first" in message
    assert "second" in message


# --------------------------------------------------------------------------- #
# Shape validation                                                            #
# --------------------------------------------------------------------------- #


def test_compose_missing_kwargs_exits_2(gaia_package: FixturePackage, tmp_path: Path) -> None:
    pattern = tmp_path / "missing.py"
    _write_compose_file(pattern, body=_MISSING_KWARGS_FILE)

    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    msg = diags[0]["message"]
    assert "name=" in msg
    assert "version=" in msg


def test_compose_wrong_return_annotation_exits_2(
    gaia_package: FixturePackage, tmp_path: Path
) -> None:
    pattern = tmp_path / "wrong.py"
    _write_compose_file(pattern, body=_WRONG_RETURN_FILE)

    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    msg = diags[0]["message"]
    assert "Claim" in msg
    assert "annotation" in msg.lower() or "return" in msg.lower()


def test_compose_missing_return_annotation_exits_2(
    gaia_package: FixturePackage, tmp_path: Path
) -> None:
    pattern = tmp_path / "noann.py"
    _write_compose_file(pattern, body=_NO_RETURN_ANNOTATION)
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# Target validation                                                           #
# --------------------------------------------------------------------------- #


def test_compose_missing_target_exits_4(tmp_path: Path) -> None:
    """Non-existent --target path is a system IO failure (exit 4)."""
    pattern = tmp_path / "pattern.py"
    _write_compose_file(pattern, body=_VALID_PATTERN)
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(tmp_path / "missing"),
        ],
    )
    assert result.exit_code == 4


def test_compose_target_not_gaia_package_exits_4(tmp_path: Path) -> None:
    """A pyproject without [tool.gaia].type = knowledge-package is rejected."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "pyproject.toml").write_text('[project]\nname = "plain"\nversion = "0.1.0"\n')

    pattern = tmp_path / "pattern.py"
    _write_compose_file(pattern, body=_VALID_PATTERN)
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(plain),
        ],
    )
    assert result.exit_code == 4


def test_compose_from_file_missing_exits_4(gaia_package: FixturePackage, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(tmp_path / "no_such.py"),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 4


def test_compose_from_file_invalid_syntax_exits_2(
    gaia_package: FixturePackage, tmp_path: Path
) -> None:
    pattern = tmp_path / "broken.py"
    pattern.write_text("def broken( -> Claim:\n    return", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "author",
            "compose",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# Alias                                                                       #
# --------------------------------------------------------------------------- #


def test_composition_alias_verb_round_trips(gaia_package: FixturePackage, tmp_path: Path) -> None:
    """The composition verb reuses the compose impl + writes verb=composition."""
    pattern = tmp_path / "alias.py"
    _write_compose_file(pattern, body=_COMPOSITION_ALIAS_FILE)
    result = runner.invoke(
        app,
        [
            "author",
            "composition",
            "--from-file",
            str(pattern),
            "--target",
            str(gaia_package.root),
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["verb"] == "composition"


# --------------------------------------------------------------------------- #
# Help text                                                                   #
# --------------------------------------------------------------------------- #


def test_compose_help_contains_example() -> None:
    """``compose --help`` shows the canonical pattern example."""
    result = runner.invoke(app, ["author", "compose", "--help"])
    assert result.exit_code == 0
    assert "@compose" in result.output
    assert "pattern.py" in result.output or "Example" in result.output
