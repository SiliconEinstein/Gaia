"""File-based JSON store for Commit objects.

Each commit is persisted as ``{storage_path}/{commit_id}.json``.
"""

from __future__ import annotations

from pathlib import Path

from libs.models import Commit


class CommitStore:
    """Simple file/JSON-based persistence for :class:`Commit` objects."""

    def __init__(self, storage_path: str) -> None:
        self._root = Path(storage_path)
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _path_for(self, commit_id: str) -> Path:
        return self._root / f"{commit_id}.json"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def save(self, commit: Commit) -> str:
        """Persist *commit* to disk and return its ``commit_id``."""
        path = self._path_for(commit.commit_id)
        path.write_text(commit.model_dump_json(indent=2), encoding="utf-8")
        return commit.commit_id

    async def get(self, commit_id: str) -> Commit | None:
        """Load a commit by *commit_id*, or return ``None`` if not found."""
        path = self._path_for(commit_id)
        if not path.exists():
            return None
        data = path.read_text(encoding="utf-8")
        return Commit.model_validate_json(data)

    async def list_commits(self) -> list[Commit]:
        """List all commits, sorted by created_at descending."""
        commits = []
        for path in self._root.glob("*.json"):
            data = path.read_text(encoding="utf-8")
            commits.append(Commit.model_validate_json(data))
        commits.sort(key=lambda c: c.created_at or "", reverse=True)
        return commits

    async def update(self, commit_id: str, **fields) -> None:
        """Update specific fields of an existing commit.

        Raises :class:`FileNotFoundError` if *commit_id* does not exist.
        """
        commit = await self.get(commit_id)
        if commit is None:
            raise FileNotFoundError(f"Commit {commit_id!r} not found")

        # Apply each supplied field to the model
        for key, value in fields.items():
            if not hasattr(commit, key):
                raise ValueError(f"Commit has no field {key!r}")
            setattr(commit, key, value)

        await self.save(commit)
