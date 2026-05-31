"""Compose — action-level composition DAG records."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Compose(BaseModel):
    """A named DAG of action targets with one public conclusion Claim."""

    model_config = ConfigDict(extra="forbid")

    compose_id: str
    name: str
    version: str
    inputs: list[str] = []
    background: list[str] = []
    actions: list[str] = []
    warrants: list[str] = []
    conclusion: str
    metadata: dict[str, Any] | None = None
