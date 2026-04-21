"""Unit tests for Skillr scanner module."""

from __future__ import annotations

from pathlib import Path

from skillr.scanner import (
    get_git_commit_hash,
    get_git_tracked_files,
    is_git_repo,
    parse_skill_frontmatter,
    scan_skills_dir,
)
from tests.conftest import (
    mock_run_failure,
    mock_run_not_found,
    mock_run_success,
    mock_run_timeout,
)


class TestIsGitRepo:
    def test_is_git_repo_success(self, mocker):
        mocker.patch("subprocess.run", mock_run_success())
        result = is_git_repo(Path("/some/path"))
        assert result is True

    def test_is_git_repo_failure(self, mocker):
        mocker.patch("subprocess.run", mock_run_failure())
        result = is_git_repo(Path("/some/path"))
        assert result is False

    def test_is_git_repo_not_found(self, mocker):
        mocker.patch("subprocess.run", mock_run_not_found())
        result = is_git_repo(Path("/some/path"))
        assert result is False

    def test_is_git_repo_timeout(self, mocker):
        mocker.patch("subprocess.run", mock_run_timeout())
        result = is_git_repo(Path("/some/path"))
        assert result is False


class TestGetGitCommitHash:
    def test_returns_hash(self, mocker):
        mocker.patch("subprocess.run", mock_run_success(stdout="abc123def456\n"))
        result = get_git_commit_hash(Path("/some/path"))
        assert result == "abc123def456"

    def test_returns_none_on_failure(self, mocker):
        mocker.patch("subprocess.run", mock_run_failure())
        result = get_git_commit_hash(Path("/some/path"))
        assert result is None

    def test_returns_none_on_not_found(self, mocker):
        mocker.patch("subprocess.run", mock_run_not_found())
        result = get_git_commit_hash(Path("/some/path"))
        assert result is None

    def test_returns_none_on_timeout(self, mocker):
        mocker.patch("subprocess.run", mock_run_timeout())
        result = get_git_commit_hash(Path("/some/path"))
        assert result is None


class TestGetGitTrackedFiles:
    def test_returns_set_of_files(self, mocker):
        mocker.patch(
            "subprocess.run",
            mock_run_success(stdout="skills/skill1/SKILL.md\nskills/skill2/SKILL.md\n"),
        )
        result = get_git_tracked_files(Path("/some/path"))
        assert result == {"skills/skill1/SKILL.md", "skills/skill2/SKILL.md"}

    def test_returns_empty_set_on_failure(self, mocker):
        mocker.patch("subprocess.run", mock_run_failure())
        result = get_git_tracked_files(Path("/some/path"))
        assert result == set()

    def test_returns_empty_set_on_not_found(self, mocker):
        mocker.patch("subprocess.run", mock_run_not_found())
        result = get_git_tracked_files(Path("/some/path"))
        assert result == set()

    def test_returns_empty_set_on_timeout(self, mocker):
        mocker.patch("subprocess.run", mock_run_timeout())
        result = get_git_tracked_files(Path("/some/path"))
        assert result == set()


class TestParseSkillFrontmatter:
    def test_valid_frontmatter(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test\n", encoding="utf-8"
        )
        result = parse_skill_frontmatter(skill_md)
        assert result is not None
        assert result.name == "test-skill"
        assert result.description == "A test skill"
        assert result.file_path == skill_md

    def test_missing_frontmatter_marker(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# No Frontmatter\n", encoding="utf-8")
        result = parse_skill_frontmatter(skill_md)
        assert result is None

    def test_missing_name(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\ndescription: No name here\n---\n\n# Test\n", encoding="utf-8")
        result = parse_skill_frontmatter(skill_md)
        assert result is None

    def test_missing_description(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: no-description\n---\n\n# Test\n", encoding="utf-8")
        result = parse_skill_frontmatter(skill_md)
        assert result is None

    def test_invalid_yaml(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: bad\ndescription: [invalid yaml\n---\n\n# Test\n", encoding="utf-8"
        )
        result = parse_skill_frontmatter(skill_md)
        assert result is None

    def test_file_not_found(self, tmp_path: Path):
        result = parse_skill_frontmatter(tmp_path / "nonexistent.md")
        assert result is None

    def test_trims_whitespace(self, tmp_path: Path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname:  whitespace-skill  \ndescription:  desc  \n---\n\n# Test\n",
            encoding="utf-8",
        )
        result = parse_skill_frontmatter(skill_md)
        assert result is not None
        assert result.name == "whitespace-skill"


class TestScanSkillsDir:
    def test_empty_directory(self, tmp_path: Path):
        result = scan_skills_dir(tmp_path)
        assert result == []

    def test_no_skills_md(self, tmp_path: Path):
        (tmp_path / "some-file.txt").write_text("content", encoding="utf-8")
        result = scan_skills_dir(tmp_path)
        assert result == []

    def test_scans_subdirectories(self, sample_skills_dir: Path):
        result = scan_skills_dir(sample_skills_dir)
        assert len(result) == 3
        names = {s.name for s in result}
        assert "valid-skill" in names
        assert "another-skill" in names
        assert "third-skill" in names

    def test_skips_non_directory_entries(self, tmp_path: Path):
        # File directly in skills_dir (not a subdirectory)
        (tmp_path / "file.txt").write_text("not a dir", encoding="utf-8")
        # Valid skill subdirectory
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: real-skill\ndescription: real\n---\n\n# Real\n", encoding="utf-8"
        )
        result = scan_skills_dir(tmp_path)
        assert len(result) == 1
        assert result[0].name == "real-skill"

    def test_non_existent_directory(self, tmp_path: Path):
        result = scan_skills_dir(tmp_path / "does-not-exist")
        assert result == []
