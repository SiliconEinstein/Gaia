"""Tests for the ``gaia skill`` CLI group (register / list).

Three layers:

* **Unit** — pure planners (``_plan_diff``, ``_is_owned_symlink``,
  ``_resolve_targets``) called directly with synthetic inputs.
* **Integration** — invoke ``gaia skill register`` / ``gaia skill list``
  via Typer's ``CliRunner`` against a ``tmp_path`` cwd. Assert the
  resulting filesystem state.
* **Cross-platform** — assert both verbs exit with code ``3`` when
  ``os.name == "nt"`` (Windows is unsupported in Phase 3).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.commands import skill as skill_module
from gaia.cli.commands.skill import (
    Plan,
    SkillEntry,
    _is_owned_symlink,
    _plan_diff,
    _resolve_targets,
)
from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _mk_entry(name: str, files: dict[str, bytes] | None = None) -> SkillEntry:
    """Build a synthetic ``SkillEntry`` with one ``SKILL.md`` by default."""
    if files is None:
        files = {"SKILL.md": f"# {name}\n".encode()}
    return SkillEntry(name=name, files=dict(files))


def _registry_root(cwd: Path) -> Path:
    return cwd / ".gaia-skills"


# --------------------------------------------------------------------------- #
# Unit — _plan_diff                                                           #
# --------------------------------------------------------------------------- #


class TestPlanDiff:
    """``_plan_diff`` is pure — exercise the four headline diff modes."""

    def test_all_new_when_installed_is_empty(self, tmp_path: Path) -> None:
        shipped = {
            "gaia-formalization": _mk_entry("gaia-formalization"),
            "gaia-review": _mk_entry("gaia-review"),
            "_shared": _mk_entry("_shared", {"bp-interpretation.md": b"shared\n"}),
        }
        plan = _plan_diff(
            shipped=shipped,
            installed={},
            cwd=tmp_path,
            active_surfaces=[],
            skipped_surfaces=[],
            registry_root=_registry_root(tmp_path),
        )
        # Every shipped entry (skills + _shared) is an ADD.
        assert sorted(plan.adds) == ["_shared", "gaia-formalization", "gaia-review"]
        assert plan.refreshes == []
        assert plan.stales == []
        assert plan.fresh_registry is True

    def test_all_stale_when_shipped_is_empty(self, tmp_path: Path) -> None:
        installed = {
            "gaia-old-one": _mk_entry("gaia-old-one"),
            "gaia-old-two": _mk_entry("gaia-old-two"),
        }
        plan = _plan_diff(
            shipped={},
            installed=installed,
            cwd=tmp_path,
            active_surfaces=[],
            skipped_surfaces=[],
            registry_root=_registry_root(tmp_path),
        )
        assert plan.adds == []
        assert plan.refreshes == []
        assert sorted(plan.stales) == ["gaia-old-one", "gaia-old-two"]

    def test_mixed_add_refresh_stale_and_ok(self, tmp_path: Path) -> None:
        shipped = {
            "gaia-formalization": _mk_entry("gaia-formalization", {"SKILL.md": b"# v2 content\n"}),
            "gaia-review": _mk_entry("gaia-review", {"SKILL.md": b"# review v1\n"}),
            "gaia-publish": _mk_entry("gaia-publish"),  # new — ADD
        }
        installed = {
            "gaia-formalization": _mk_entry(
                "gaia-formalization", {"SKILL.md": b"# v1 content\n"}
            ),  # DRIFTed → REFRESH
            "gaia-review": _mk_entry(
                "gaia-review", {"SKILL.md": b"# review v1\n"}
            ),  # byte-equal → OK (omitted)
            "gaia-old": _mk_entry("gaia-old"),  # gone from shipped → STALE
        }
        plan = _plan_diff(
            shipped=shipped,
            installed=installed,
            cwd=tmp_path,
            active_surfaces=[],
            skipped_surfaces=[],
            registry_root=_registry_root(tmp_path),
        )
        assert plan.adds == ["gaia-publish"]
        assert plan.refreshes == ["gaia-formalization"]
        assert plan.stales == ["gaia-old"]
        # Byte-equal entry must NOT appear in any of the action lists.
        assert "gaia-review" not in plan.adds
        assert "gaia-review" not in plan.refreshes
        assert "gaia-review" not in plan.stales

    def test_idempotent_steady_state(self, tmp_path: Path) -> None:
        shared_payload = {"bp-interpretation.md": b"shared body\n"}
        shipped = {
            "gaia-formalization": _mk_entry("gaia-formalization"),
            "_shared": _mk_entry("_shared", shared_payload),
        }
        installed = {
            "gaia-formalization": _mk_entry("gaia-formalization"),
            "_shared": _mk_entry("_shared", shared_payload),
        }
        registry_root = _registry_root(tmp_path)
        registry_root.mkdir()  # so fresh_registry is False
        plan = _plan_diff(
            shipped=shipped,
            installed=installed,
            cwd=tmp_path,
            active_surfaces=[],
            skipped_surfaces=[],
            registry_root=registry_root,
        )
        assert plan.adds == []
        assert plan.refreshes == []
        assert plan.stales == []
        assert plan.fresh_registry is False

    def test_symlink_plan_marks_collision_for_real_dir(self, tmp_path: Path) -> None:
        """A real directory at the consumer-surface entry path → COLLISION."""
        registry_root = _registry_root(tmp_path)
        registry_root.mkdir()
        (registry_root / "gaia-formalization").mkdir()
        # Pre-create a real directory where our symlink would otherwise live.
        claude_dir = tmp_path / ".claude" / "skills" / "gaia-formalization"
        claude_dir.mkdir(parents=True)
        shipped = {"gaia-formalization": _mk_entry("gaia-formalization")}
        plan = _plan_diff(
            shipped=shipped,
            installed=shipped,
            cwd=tmp_path,
            active_surfaces=["claude"],
            skipped_surfaces=[],
            registry_root=registry_root,
        )
        ops = [op for op in plan.symlink_ops if op.skill == "gaia-formalization"]
        assert len(ops) == 1
        assert ops[0].action == "COLLISION"
        assert "real directory" in ops[0].detail


# --------------------------------------------------------------------------- #
# Unit — _is_owned_symlink                                                    #
# --------------------------------------------------------------------------- #


class TestIsOwnedSymlink:
    """The ownership gate before any deletion of a consumer-surface entry."""

    def test_owned_symlink_returns_true(self, tmp_path: Path) -> None:
        registry_root = tmp_path / ".gaia-skills"
        registry_root.mkdir()
        (registry_root / "gaia-formalization").mkdir()
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        link = skills_dir / "gaia-formalization"
        os.symlink(Path("..") / ".." / ".gaia-skills" / "gaia-formalization", link)
        assert _is_owned_symlink(link, registry_root) is True

    def test_foreign_symlink_returns_false(self, tmp_path: Path) -> None:
        registry_root = tmp_path / ".gaia-skills"
        registry_root.mkdir()
        other = tmp_path / "elsewhere" / "gaia-formalization"
        other.mkdir(parents=True)
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        link = skills_dir / "gaia-formalization"
        os.symlink(other, link)
        assert _is_owned_symlink(link, registry_root) is False

    def test_real_file_returns_false(self, tmp_path: Path) -> None:
        registry_root = tmp_path / ".gaia-skills"
        registry_root.mkdir()
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        path = skills_dir / "gaia-formalization"
        path.write_text("not a link\n")
        assert _is_owned_symlink(path, registry_root) is False

    def test_real_directory_returns_false(self, tmp_path: Path) -> None:
        registry_root = tmp_path / ".gaia-skills"
        registry_root.mkdir()
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        path = skills_dir / "gaia-formalization"
        path.mkdir()
        assert _is_owned_symlink(path, registry_root) is False

    def test_missing_path_returns_false(self, tmp_path: Path) -> None:
        registry_root = tmp_path / ".gaia-skills"
        registry_root.mkdir()
        missing = tmp_path / ".claude" / "skills" / "gaia-formalization"
        assert _is_owned_symlink(missing, registry_root) is False


# --------------------------------------------------------------------------- #
# Unit — _resolve_targets                                                     #
# --------------------------------------------------------------------------- #


class TestResolveTargets:
    """Mapping ``--target`` × parent-dir presence to (active, skipped)."""

    def test_auto_with_only_claude_present(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        active, skipped = _resolve_targets("auto", tmp_path)
        assert active == ["claude"]
        assert [s for s, _ in skipped] == ["agent"]

    def test_auto_with_both_present(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".agent").mkdir()
        active, skipped = _resolve_targets("auto", tmp_path)
        assert active == ["claude", "agent"]
        assert skipped == []

    def test_auto_with_neither_present(self, tmp_path: Path) -> None:
        active, skipped = _resolve_targets("auto", tmp_path)
        assert active == []
        assert sorted(s for s, _ in skipped) == ["agent", "claude"]

    def test_target_claude_opts_in(self, tmp_path: Path) -> None:
        # Neither dir exists; explicit --target claude still opts in.
        active, skipped = _resolve_targets("claude", tmp_path)
        assert active == ["claude"]
        # The implementation does not populate skipped under explicit forms.
        assert skipped == []

    def test_target_agent_opts_in(self, tmp_path: Path) -> None:
        active, skipped = _resolve_targets("agent", tmp_path)
        assert active == ["agent"]
        assert skipped == []

    def test_target_both(self, tmp_path: Path) -> None:
        active, skipped = _resolve_targets("both", tmp_path)
        assert active == ["claude", "agent"]
        assert skipped == []


# --------------------------------------------------------------------------- #
# Integration — register / list against a tmp_path cwd                        #
# --------------------------------------------------------------------------- #


class TestRegisterIntegration:
    """End-to-end ``gaia skill register`` invocations via Typer's CliRunner."""

    def test_fresh_cwd_with_both_surfaces_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both ``.claude/`` and ``.agent/`` present → register links into both."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".agent").mkdir()

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 0, result.output

        registry = tmp_path / ".gaia-skills"
        assert registry.is_dir()
        # All shipped skills materialised, plus _shared. (The retired
        # `gaia-lkm-explorer` skill is now the `gaia-lkm-explore` orchestrator
        # client — CLIENT.md — so it is intentionally absent here.)
        for skill in (
            "gaia-formalize-fine",
            "gaia-formalize-coarse",
            "gaia-evidence-subgraph",
            "gaia-scholarly-synthesis",
            "gaia-obsidian-wiki",
            "gaia-publish",
            "gaia-review",
        ):
            assert (registry / skill / "SKILL.md").is_file(), skill
            for surface in (".claude", ".agent"):
                link = tmp_path / surface / "skills" / skill
                assert link.is_symlink(), f"{surface}/skills/{skill}"
                # The symlink resolves into the registry — i.e. we own it.
                assert _is_owned_symlink(link, registry)
        assert (registry / "_shared" / "bp-interpretation.md").is_file()
        # _shared must NOT be linked into the agent surfaces.
        assert not (tmp_path / ".claude" / "skills" / "_shared").exists()
        assert not (tmp_path / ".agent" / "skills" / "_shared").exists()

        # And `list` reports clean OK status.
        list_result = runner.invoke(app, ["skill", "list"])
        assert list_result.exit_code == 0, list_result.output
        # Every shipped skill row should carry an OK status.
        for skill in (
            "gaia-formalize-fine",
            "gaia-formalize-coarse",
            "gaia-evidence-subgraph",
            "gaia-scholarly-synthesis",
            "gaia-obsidian-wiki",
            "gaia-publish",
            "gaia-review",
        ):
            assert skill in list_result.output
        assert "COLLISION" not in list_result.output

    def test_fresh_cwd_only_claude_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``.claude/`` only → register links there but does NOT create ``.agent/``."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 0, result.output

        # Registry created; claude links present; .agent/ not created.
        assert (tmp_path / ".gaia-skills" / "gaia-formalize-fine").is_dir()
        assert (tmp_path / ".claude" / "skills" / "gaia-formalize-fine").is_symlink()
        assert not (tmp_path / ".agent").exists()

    def test_fresh_cwd_neither_surface_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Neither surface present → registry materialised, no symlinks created."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 0, result.output

        assert (tmp_path / ".gaia-skills" / "gaia-formalize-fine" / "SKILL.md").is_file()
        # No agent-surface dirs should have been created in auto mode.
        assert not (tmp_path / ".claude").exists()
        assert not (tmp_path / ".agent").exists()

    def test_target_claude_creates_surface_dir_when_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--target claude`` opts in to creating ``.claude/skills/``."""
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / ".claude").exists()

        result = runner.invoke(app, ["skill", "register", "--target", "claude"])
        assert result.exit_code == 0, result.output

        assert (tmp_path / ".gaia-skills" / "gaia-formalize-fine").is_dir()
        link = tmp_path / ".claude" / "skills" / "gaia-formalize-fine"
        assert link.is_symlink()
        # And .agent/ remains untouched.
        assert not (tmp_path / ".agent").exists()

    def test_dry_run_does_not_mutate_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--dry-run`` prints the plan but creates no ``.gaia-skills/``."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        result = runner.invoke(app, ["skill", "register", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Plan:" in result.output

        # No registry, no symlinks.
        assert not (tmp_path / ".gaia-skills").exists()
        assert not (tmp_path / ".claude" / "skills").exists()

    def test_idempotent_rerun_is_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two consecutive registers → second prints OK lines, no mutation."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        first = runner.invoke(app, ["skill", "register"])
        assert first.exit_code == 0, first.output

        registry = tmp_path / ".gaia-skills"
        link = tmp_path / ".claude" / "skills" / "gaia-formalize-fine"
        before_link_target = os.readlink(link)
        before_skill_mtime = (registry / "gaia-formalize-fine" / "SKILL.md").stat().st_mtime_ns

        second = runner.invoke(app, ["skill", "register"])
        assert second.exit_code == 0, second.output
        assert "OK" in second.output

        # Symlink unchanged, registry file unchanged.
        assert os.readlink(link) == before_link_target
        after_skill_mtime = (registry / "gaia-formalize-fine" / "SKILL.md").stat().st_mtime_ns
        assert after_skill_mtime == before_skill_mtime

    def test_stale_entry_removed_from_registry_and_surfaces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stale registry entries (not in shipped) → pruned from registry + owned links."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".agent").mkdir()

        # First register so the registry exists and links are owned.
        first = runner.invoke(app, ["skill", "register"])
        assert first.exit_code == 0, first.output

        # Plant a STALE registry entry and matching owned symlinks.
        stale_dir = tmp_path / ".gaia-skills" / "gaia-stale-skill"
        stale_dir.mkdir()
        (stale_dir / "SKILL.md").write_text("# stale\n")
        for surface in (".claude", ".agent"):
            link = tmp_path / surface / "skills" / "gaia-stale-skill"
            os.symlink(Path("..") / ".." / ".gaia-skills" / "gaia-stale-skill", link)

        # And an unrelated real file lying around at an unrelated path —
        # it must NOT be touched.
        bystander = tmp_path / "bystander.txt"
        bystander.write_text("untouched\n")

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 0, result.output

        # STALE entry pruned from registry AND both surfaces.
        assert not stale_dir.exists()
        assert not (tmp_path / ".claude" / "skills" / "gaia-stale-skill").exists()
        assert not (tmp_path / ".agent" / "skills" / "gaia-stale-skill").exists()
        # Bystander untouched.
        assert bystander.read_text() == "untouched\n"

    def test_collision_real_dir_blocks_one_skill_but_links_others(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real dir at our entry path → COLLISION, exit 1, dir preserved."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()
        colliding = tmp_path / ".claude" / "skills" / "gaia-formalize-fine"
        colliding.mkdir(parents=True)
        sentinel = colliding / "user-content.md"
        sentinel.write_text("user data\n")

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 1, result.output
        assert "COLLISION" in result.output
        assert "gaia-formalize-fine" in result.output

        # The colliding real dir + its contents are preserved.
        assert colliding.is_dir()
        assert not colliding.is_symlink()
        assert sentinel.read_text() == "user data\n"

        # Other skills DID get linked (rest of plan applied).
        other = tmp_path / ".claude" / "skills" / "gaia-review"
        assert other.is_symlink()

    def test_collision_real_file_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real file at our entry path → COLLISION, exit 1, file preserved."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        colliding = tmp_path / ".claude" / "skills" / "gaia-formalize-fine"
        colliding.write_text("user notes\n")

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 1, result.output
        assert "COLLISION" in result.output

        assert colliding.is_file()
        assert not colliding.is_symlink()
        assert colliding.read_text() == "user notes\n"

    def test_collision_foreign_symlink_preserved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Foreign-target symlink at our entry path → COLLISION, link preserved."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere" / "gaia-formalize-fine"
        elsewhere.mkdir(parents=True)
        (elsewhere / "marker.txt").write_text("foreign\n")
        colliding = tmp_path / ".claude" / "skills" / "gaia-formalize-fine"
        os.symlink(elsewhere, colliding)

        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 1, result.output
        assert "COLLISION" in result.output

        assert colliding.is_symlink()
        # Target unchanged.
        assert Path(os.readlink(colliding)) == elsewhere
        assert (colliding / "marker.txt").read_text() == "foreign\n"


class TestListIntegration:
    """``gaia skill list`` end-to-end."""

    def test_list_with_collision_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collision row in list → non-zero exit so CI can spot trouble."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        # Real dir collision at one of the shipped skill names.
        (tmp_path / ".claude" / "skills" / "gaia-formalize-fine").mkdir()

        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 1, result.output
        assert "COLLISION" in result.output
        # Other skills should still appear in the table.
        assert "gaia-review" in result.output


# --------------------------------------------------------------------------- #
# Cross-platform — Windows must raise typer.Exit(3)                           #
# --------------------------------------------------------------------------- #


class TestWindowsGate:
    """``register`` and ``list`` are POSIX-only — exit 3 on ``os.name == 'nt'``."""

    def test_register_exits_3_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(skill_module.os, "name", "nt")
        result = runner.invoke(app, ["skill", "register"])
        assert result.exit_code == 3, result.output
        # CliRunner merges stderr into output by default; the gate writes
        # to stderr with err=True. Either way, the wording must surface.
        combined = result.output + (result.stderr if hasattr(result, "stderr") else "")
        assert "POSIX-only" in combined or "Windows" in combined

    def test_list_exits_3_on_windows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(skill_module.os, "name", "nt")
        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 3, result.output
        combined = result.output + (result.stderr if hasattr(result, "stderr") else "")
        assert "POSIX-only" in combined or "Windows" in combined


# --------------------------------------------------------------------------- #
# Defensive sanity check on the Plan dataclass shape                          #
# --------------------------------------------------------------------------- #


def test_plan_dataclass_default_shape() -> None:
    """Sanity: an empty Plan has the expected empty defaults."""
    plan = Plan(shipped={}, installed={})
    assert plan.adds == []
    assert plan.refreshes == []
    assert plan.stales == []
    assert plan.symlink_ops == []
    assert plan.skipped_surfaces == []
    assert plan.fresh_registry is False
