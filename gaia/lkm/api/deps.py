"""Dependency injection for LKM API."""

from __future__ import annotations

from fastapi import Request

from gaia.lkm.storage import StorageManager


def get_storage(request: Request) -> StorageManager:
    return request.app.state.storage
