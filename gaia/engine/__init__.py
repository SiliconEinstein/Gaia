"""Gaia engine — public sub-facades under `gaia.engine.*`.

Alpha 0 architectural split: engine code is the stable contract surface,
distinct from `gaia.cli`. Each sub-package owns its own `__all__`; this
namespace package intentionally does not flat-re-export the 244 public
symbols — callers import from the relevant sub-facade.
"""
