"""File-based ID generator. Phase 1: single-process safe via asyncio lock."""

import asyncio
import json
from pathlib import Path


class IDGenerator:
    def __init__(self, storage_path: str):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._counters: dict[str, int] = self._load()

    def _state_file(self) -> Path:
        return self._path / "counters.json"

    def _load(self) -> dict[str, int]:
        f = self._state_file()
        if f.exists():
            return json.loads(f.read_text())
        return {"node": 0, "hyperedge": 0}

    def _save(self) -> None:
        self._state_file().write_text(json.dumps(self._counters))

    async def _alloc(self, kind: str, count: int) -> list[int]:
        async with self._lock:
            start = self._counters[kind] + 1
            self._counters[kind] = start + count - 1
            self._save()
            return list(range(start, start + count))

    async def alloc_node_id(self) -> int:
        return (await self._alloc("node", 1))[0]

    async def alloc_hyperedge_id(self) -> int:
        return (await self._alloc("hyperedge", 1))[0]

    async def alloc_node_ids_bulk(self, count: int) -> list[int]:
        return await self._alloc("node", count)

    async def alloc_hyperedge_ids_bulk(self, count: int) -> list[int]:
        return await self._alloc("hyperedge", count)
