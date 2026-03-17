"""Curation service — global graph maintenance and cleanup."""

from .scheduler import run_curation

__all__ = ["run_curation"]
