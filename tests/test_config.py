"""Unit tests for Skillr config module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillr.config import _get_plugin_data_dir, ensure_plugin_data_dir, get_skills_dirs


class TestGetPluginDataDir:
    def test_returns_env_var_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "/custom/path")
        assert _get_plugin_data_dir() == Path("/custom/path")

    def test_fallback_when_no_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        result = _get_plugin_data_dir()
        assert "skillr" in str(result)


class TestGetSkillsDirs:
    def test_missing_config_file(self, mock_plugin_data_dir: str):
        # No config.json exists at all
        result = get_skills_dirs()
        assert result == []

    def test_empty_config_object(self, mock_config_file: str):
        mock_config_file.write_text("{}", encoding="utf-8")
        result = get_skills_dirs()
        assert result == []

    def test_invalid_json(self, mock_config_file: str):
        mock_config_file.write_text("not valid json", encoding="utf-8")
        result = get_skills_dirs()
        assert result == []

    def test_skills_dirs_not_a_list(self, mock_config_file: str):
        mock_config_file.write_text('{"skills_dirs": "not-a-list"}', encoding="utf-8")
        result = get_skills_dirs()
        assert result == []

    def test_string_path_entry_valid(self, tmp_path: Path, mock_config_file: str):
        skills_dir = tmp_path / "my-skills"
        skills_dir.mkdir()
        mock_config_file.write_text(
            json.dumps({"skills_dirs": [str(skills_dir)]}),
            encoding="utf-8",
        )
        result = get_skills_dirs()
        assert len(result) == 1
        assert result[0] == skills_dir

    def test_dict_path_entry_valid(self, tmp_path: Path, mock_config_file: str):
        skills_dir = tmp_path / "my-skills"
        skills_dir.mkdir()
        mock_config_file.write_text(
            json.dumps({"skills_dirs": [{"path": str(skills_dir), "type": "git"}]}),
            encoding="utf-8",
        )
        result = get_skills_dirs()
        assert len(result) == 1
        assert result[0] == skills_dir

    def test_non_existent_path_filtered_out(self, tmp_path: Path, mock_config_file: str):
        real_dir = tmp_path / "real-skills"
        real_dir.mkdir()
        mock_config_file.write_text(
            json.dumps({"skills_dirs": [str(real_dir), "/does/not/exist"]}),
            encoding="utf-8",
        )
        result = get_skills_dirs()
        assert len(result) == 1
        assert result[0] == real_dir

    def test_mixed_valid_and_invalid(self, tmp_path: Path, mock_config_file: str):
        valid1 = tmp_path / "dir1"
        valid2 = tmp_path / "dir2"
        valid1.mkdir()
        valid2.mkdir()
        mock_config_file.write_text(
            json.dumps({"skills_dirs": [str(valid1), "/invalid", {"path": str(valid2)}]}),
            encoding="utf-8",
        )
        result = get_skills_dirs()
        assert len(result) == 2


class TestEnsurePluginDataDir:
    def test_creates_directory(self, mock_plugin_data_dir: Path):
        # Should not raise
        result = ensure_plugin_data_dir()
        assert result.exists()
        assert result == mock_plugin_data_dir

    def test_idempotent(self, mock_plugin_data_dir: Path):
        # Calling twice should not raise
        r1 = ensure_plugin_data_dir()
        r2 = ensure_plugin_data_dir()
        assert r1 == r2