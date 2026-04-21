"""Unit tests for Skillr indexer module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skillr.indexer import (
    build_index,
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
        result = get_source_tracking_value(Path("/git/repo"))
        assert result.type == "git"
        assert result.value == "abc123"

    def test_returns_mtime_tracking(self, mocker, tmp_path: Path):
        mocker.patch("skillr.indexer.is_git_repo", return_value=False)
        # Create actual directory so stat() works
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        result = get_source_tracking_value(skills_dir)
        assert result.type == "mtime"
        # Should be a valid ISO string
        datetime.fromisoformat(result.value)

    def test_fallback_on_os_error(self, mocker):
        mocker.patch("skillr.indexer.is_git_repo", return_value=False)
        mocker.patch("pathlib.Path.stat", side_effect=OSError())
        result = get_source_tracking_value(Path("/nonexistent"))
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


class TestBuildIndex:
    def test_creates_index_with_version(self, mocker):
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[])
        index = build_index()
        assert index.version == "1.0.0"
        assert index.retrieval_window == 50

    def test_sets_generated_at(self, mocker):
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[])
        index = build_index()
        # Should be a valid ISO timestamp
        datetime.fromisoformat(index.generated_at)


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
