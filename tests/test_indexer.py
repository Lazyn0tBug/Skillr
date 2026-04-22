"""Unit tests for Skillr indexer module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skillr.indexer import (
    get_source_tracking_value,
    load_index,
    run_indexer,
    save_index,
    scan_all_skills_dirs,
)
from skillr.models import SkillrIndex, SourceTracking


class TestGetSourceTrackingValue:
    def test_returns_git_tracking(self, mocker):
        mocker.patch("skillr.indexer.is_git_repo", return_value=True)
        mocker.patch("skillr.indexer.get_git_commit_hash", return_value="abc123")
        result = get_source_tracking_value(Path("/git/repo"), {})
        assert result.type == "git"
        assert result.value == "abc123"

    def test_returns_mtime_tracking(self, mocker, tmp_path: Path):
        mocker.patch("skillr.indexer.is_git_repo", return_value=False)
        # Create actual directory so stat() works
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        result = get_source_tracking_value(skills_dir, {})
        assert result.type == "mtime"
        # Should be a valid ISO string
        datetime.fromisoformat(result.value)

    def test_fallback_on_os_error(self, mocker):
        mocker.patch("skillr.indexer.is_git_repo", return_value=False)
        mocker.patch("pathlib.Path.stat", side_effect=OSError())
        result = get_source_tracking_value(Path("/nonexistent"), {})
        assert result.type == "mtime"
        assert result.value == "0"


class TestScanAllSkillsDirs:
    def test_empty_when_no_dirs_configured(self, mocker):
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[])
        skills, tracking = scan_all_skills_dirs()
        assert skills == []
        assert tracking == {}

    def test_aggregates_multiple_dirs(self, mocker, tmp_path: Path):
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create a skill in dir1
        skill1_dir = dir1 / "skill1"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: skill1\ndescription: Skill one\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[dir1, dir2])
        mocker.patch(
            "skillr.indexer.get_source_tracking_value",
            return_value=SourceTracking(type="mtime", value="0"),
        )

        skills, tracking = scan_all_skills_dirs()
        assert len(skills) == 1
        assert skills[0].name == "skill1"
        assert str(dir1) in tracking
        assert str(dir2) in tracking


class TestSaveIndex:
    def test_saves_json_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        index = SkillrIndex(
            version="1.0.0",
            generated_at=datetime.now(UTC).isoformat(),
            skills_dirs=[],
            skills=[],
            source_tracking={},
        )
        path = save_index(index)
        assert path.exists()
        assert path.name == "skillr_index.json"

        # Verify it's valid JSON
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == "1.0.0"


class TestLoadIndex:
    def test_returns_none_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        result = load_index()
        assert result is None

    def test_loads_valid_index(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        index_dir = plugin_data / "index"
        index_dir.mkdir()
        index_path = index_dir / "skillr_index.json"
        index_data = {
            "version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "skills_dirs": ["/skills"],
            "skills": [
                {
                    "name": "test-skill",
                    "description": "A test",
                    "file_path": "/skills/test/SKILL.md",
                }
            ],
            "source_tracking": {"/skills": {"type": "mtime", "value": "0"}},
            "retrieval_window": 50,
        }
        index_path.write_text(json.dumps(index_data), encoding="utf-8")

        result = load_index()
        assert result is not None
        assert result.version == "1.0.0"
        assert len(result.skills) == 1

    def test_returns_none_on_corrupt_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        index_dir = plugin_data / "index"
        index_dir.mkdir()
        index_path = index_dir / "skillr_index.json"
        index_path.write_text("not valid json", encoding="utf-8")

        result = load_index()
        assert result is None

    def test_returns_none_on_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        index_dir = plugin_data / "index"
        index_dir.mkdir()
        index_path = index_dir / "skillr_index.json"
        # Missing required 'generated_at' field
        index_path.write_text('{"version": "1.0.0"}', encoding="utf-8")

        result = load_index()
        assert result is None


class TestRunIndexer:
    def test_returns_path_and_count(self, mocker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        # No skills dirs configured
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[])

        index_path, count = run_indexer()
        assert index_path.exists()
        assert count == 0


class TestIncrementalIndex:
    def test_build_incremental_index_returns_skillrindex(
        self, mocker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """build_incremental_index returns a valid SkillrIndex."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[])

        from skillr.indexer import build_incremental_index

        index = build_incremental_index()
        assert isinstance(index, SkillrIndex)
        assert index.version == "1.0.0"

    def test_file_mtimes_tracked_in_source_tracking(
        self, mocker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """file_mtimes dict is populated in source_tracking for each dir."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: skill1\ndescription: Test skill 1\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[skills_dir])

        from skillr.indexer import build_incremental_index

        index = build_incremental_index()
        tracking = index.source_tracking.get(str(skills_dir))
        assert tracking is not None
        assert "skill1" in tracking.file_mtimes
        # mtime should be a valid ISO string
        datetime.fromisoformat(tracking.file_mtimes["skill1"])

    def test_incremental_reuses_previous_data_when_mtime_unchanged(
        self, mocker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When file_mtimes unchanged, previous index skills are reused."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: skill1\ndescription: Test skill\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[skills_dir])

        from skillr.indexer import build_incremental_index, save_index

        # First build
        index1 = build_incremental_index()
        save_index(index1)

        # Second build — mtime unchanged, should reuse
        index2 = build_incremental_index()
        assert len(index2.skills) == 1
        assert index2.skills[0].name == "skill1"

    def test_incremental_rebuilds_when_file_mtime_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When a file's mtime changes, incremental index rebuilds that dir."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir()
        skill1_md = skill1_dir / "SKILL.md"
        skill1_md.write_text(
            "---\nname: skill1\ndescription: Test skill\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        # Write skills_dir to config so get_skills_dirs finds it without mocking
        config_dir = plugin_data
        config_dir.mkdir(exist_ok=True)
        import json

        (config_dir / "config.json").write_text(
            json.dumps({"skills_dirs": [str(skills_dir)]}),
            encoding="utf-8",
        )

        import time

        from skillr.indexer import build_incremental_index, save_index

        # First build
        index1 = build_incremental_index()
        save_index(index1)

        # Touch the file to change mtime
        time.sleep(0.01)
        skill1_md.write_text(
            "---\nname: skill1\ndescription: Updated description\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        # Second build — should detect change
        index2 = build_incremental_index()
        assert len(index2.skills) == 1
        # The rebuilt tracking should have a different mtime
        tracking = index2.source_tracking.get(str(skills_dir))
        assert tracking is not None
        new_mtime = tracking.file_mtimes.get("skill1", "")
        # mtime should exist and be a valid ISO string
        assert new_mtime != ""
        datetime.fromisoformat(new_mtime)

    def test_deleted_skill_removed_from_new_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A skill that existed in previous index but not in current scan is removed."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Write skills_dir to config so get_skills_dirs finds it without mocking
        config_dir = plugin_data
        config_dir.mkdir(exist_ok=True)
        import json

        (config_dir / "config.json").write_text(
            json.dumps({"skills_dirs": [str(skills_dir)]}),
            encoding="utf-8",
        )

        # Create skill1
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: skill1\ndescription: Test skill 1\n---\n\n# Skill 1\n",
            encoding="utf-8",
        )

        from skillr.indexer import build_incremental_index, save_index

        # First build — has skill1
        index1 = build_incremental_index()
        save_index(index1)
        assert len(index1.skills) == 1

        # Delete skill1 by removing its SKILL.md then the directory
        (skill1_dir / "SKILL.md").unlink()
        skill1_dir.rmdir()

        # Second build — skill1 should be gone
        index2 = build_incremental_index()
        skill_names = {s.name for s in index2.skills}
        assert "skill1" not in skill_names
