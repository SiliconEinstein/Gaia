"""R4 tests for the engine-DSL deprecation AST scanner.

R4·❓C=A — replace the R3 hand-curated ``_DEPRECATED_DSL_NAMES`` constant
with a live AST scan of ``gaia.engine.lang.dsl.**.py``. Two engine
shapes are recognised:

1. **Direct** — ``warnings.warn(<msg>, DeprecationWarning, ...)`` inside
   the function body. The deprecated name is the function name; the
   replacement hint is parsed out of the message string.
2. **Indirect** — ``_warn_deprecated_*(<name>, <replacement>)`` call
   referencing a private helper. Args carry both name and replacement.

These tests cover:

* Coverage of R3's hand-curated set: every name the R3 constant carried
  is still surfaced post-scan.
* Replacement-hint extraction for each shape (direct + indirect).
* Caching: repeated calls return the same dict identity.
* Fallback merge for names the scanner would miss.
"""

from __future__ import annotations

import pytest

from gaia.cli.commands.author import _deprecation_scan
from gaia.cli.commands.author._deprecation_scan import (
    _extract_replacement_hint,
    _R3_FALLBACK_NAMES,
    get_deprecated_names,
)

pytestmark = pytest.mark.pr_gate


# --------------------------------------------------------------------------- #
# Coverage                                                                    #
# --------------------------------------------------------------------------- #


def test_get_deprecated_names_covers_r3_hand_curated_set() -> None:
    """All 10 names R3 hand-curated remain present after R4's AST scan."""
    discovered = get_deprecated_names()
    for name in _R3_FALLBACK_NAMES:
        assert name in discovered, f"R3 name {name!r} missing from AST scan"


def test_get_deprecated_names_includes_known_engine_deprecations() -> None:
    """Direct + indirect deprecations from v0.5 engine source surface."""
    discovered = get_deprecated_names()
    # Indirect-helper shape from operators.py.
    assert "contradiction" in discovered
    assert "equivalence" in discovered
    # Indirect-helper shape from knowledge.py (fixed-replacement helper).
    assert "context" in discovered
    assert "setting" in discovered
    # Direct shape from strategies.py.
    assert "noisy_and" in discovered


def test_get_deprecated_names_picks_up_support_beyond_r3_set() -> None:
    """The AST scanner finds ``support`` (a direct-shape deprecation R3 missed).

    Validates that the scan is genuinely picking up engine source — not
    just regurgitating the R3 fallback — by spotting at least one
    deprecation outside the curated set. ``support`` lives next to
    ``noisy_and`` in strategies.py with the same direct-call pattern.
    """
    discovered = get_deprecated_names()
    assert "support" in discovered
    assert "support" not in _R3_FALLBACK_NAMES


def test_replacement_hint_present_for_known_indirect_helpers() -> None:
    """Indirect-helper deprecations carry the engine's replacement string."""
    discovered = get_deprecated_names()
    repl, since = discovered["contradiction"]
    # Helper call is _warn_deprecated_operator("contradiction", "<replacement>")
    assert "contradict" in repl
    assert since == "0.5"

    repl_eq, _ = discovered["equivalence"]
    assert "equal" in repl_eq


def test_replacement_hint_present_for_direct_deprecations() -> None:
    """Direct-shape deprecations parse the replacement out of the message."""
    discovered = get_deprecated_names()
    repl, _ = discovered["noisy_and"]
    # The "use derive()" mention in the engine message should land here.
    assert "derive" in repl.lower()


# --------------------------------------------------------------------------- #
# Caching                                                                     #
# --------------------------------------------------------------------------- #


def test_get_deprecated_names_returns_cached_dict_on_repeat() -> None:
    """Subsequent calls return the same dict instance (cheap repeated use)."""
    first = get_deprecated_names()
    second = get_deprecated_names()
    assert first is second


def test_get_deprecated_names_includes_fallback_only_when_unseen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name in the R3 fallback but not in the scan still surfaces."""
    monkeypatch.setattr(_deprecation_scan, "_CACHED", None)
    monkeypatch.setattr(
        _deprecation_scan,
        "_R3_FALLBACK_NAMES",
        {"_test_only_fallback_name": ("test-replacement", "0.5")},
    )
    discovered = get_deprecated_names()
    # The fake fallback name should land via the merge step.
    assert "_test_only_fallback_name" in discovered
    assert discovered["_test_only_fallback_name"] == ("test-replacement", "0.5")
    # Clean up cache between tests so the production fixture re-loads.
    monkeypatch.setattr(_deprecation_scan, "_CACHED", None)


# --------------------------------------------------------------------------- #
# Replacement-hint extraction                                                 #
# --------------------------------------------------------------------------- #


def test_extract_replacement_hint_use_phrase() -> None:
    """Simple ``use <X>`` produces ``<X>`` (possibly with trailing context).

    Engine messages typically include trailing words like ``instead`` or
    ``for backwards compat``; the regex stops at the next sentence
    boundary, not at every connective, so a ``"use note() instead."``
    cleanly yields ``"note() instead"`` (replacement remains a useful
    hint).
    """
    hint = _extract_replacement_hint("foo() is deprecated; use note() instead.")
    assert hint is not None
    assert "note()" in hint


def test_extract_replacement_hint_with_for_phrase() -> None:
    """Hint truncates at ``for`` boundary."""
    msg = "foo() is deprecated; use derive() for deterministic reasoning."
    assert _extract_replacement_hint(msg) == "derive()"


def test_extract_replacement_hint_returns_none_when_no_match() -> None:
    """A message without ``use <X>`` returns None."""
    assert _extract_replacement_hint("deprecated since 0.5") is None
