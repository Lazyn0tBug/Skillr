"""Shared pytest fixtures for Skillr tests."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


# === Temp skills directory fixtures ===

@pytest.fixture
def temp_skills_dir(tmp_path: Path) -> Path:
    """A temporary empty skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    return skills_dir


@pytest.fixture
def sample_skills_dir(tmp_path: Path) -> Path:
    """A temporary skills directory with 3 sample skill subdirectories."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Skill 1: valid skill
    skill1 = skills_dir / "valid-skill"
    skill1.mkdir(parents=True)
    (skill1 / "SKILL.md").write_text(
        "---\nname: valid-skill\ndescription: A valid skill for testing\n---\n\n# Valid Skill\n",
        encoding="utf-8",
    )

    # Skill 2: another valid skill
    skill2 = skills_dir / "another-skill"
    skill2.mkdir(parents=True)
    (skill2 / "SKILL.md").write_text(
        "---\nname: another-skill\ndescription: Another skill for testing matching\n---\n\n# Another Skill\n",
        encoding="utf-8",
    )

    # Skill 3: third skill
    skill3 = skills_dir / "third-skill"
    skill3.mkdir(parents=True)
    (skill3 / "SKILL.md").write_text(
        "---\nname: third-skill\ndescription: Third skill for various tests\n---\n\n# Third Skill\n",
        encoding="utf-8",
    )

    return skills_dir


@pytest.fixture
def malformed_skills_dir(tmp_path: Path) -> Path:
    """A skills directory with various malformed SKILL.md files."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)

    # Missing frontmatter
    no_fm = skills_dir / "no-frontmatter"
    no_fm.mkdir(parents=True)
    (no_fm / "SKILL.md").write_text("# No Frontmatter\n", encoding="utf-8")

    # Missing name field
    no_name = skills_dir / "no-name"
    no_name.mkdir(parents=True)
    (no_name / "SKILL.md").write_text(
        "---\ndescription: Missing name field\n---\n\n# No Name\n",
        encoding="utf-8",
    )

    # Missing description field
    no_desc = skills_dir / "no-description"
    no_desc.mkdir(parents=True)
    (no_desc / "SKILL.md").write_text(
        "---\nname: no-description-skill\n---\n\n# No Description\n",
        encoding="utf-8",
    )

    # Invalid YAML
    bad_yaml = skills_dir / "bad-yaml"
    bad_yaml.mkdir(parents=True)
    (bad_yaml / "SKILL.md").write_text(
        "---\nname: bad-yaml\ndescription: Invalid\n  - this: is: not: valid yaml\n---\n\n# Bad YAML\n",
        encoding="utf-8",
    )

    return skills_dir


# === Mock config fixtures ===

@pytest.fixture
def mock_plugin_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set CLAUDE_PLUGIN_DATA to a temp directory and return its path."""
    plugin_data = tmp_path / "plugin_data"
    plugin_data.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))
    return plugin_data


@pytest.fixture
def mock_config_file(mock_plugin_data_dir: Path) -> Path:
    """Return path to a mock config.json inside the plugin data dir."""
    return mock_plugin_data_dir / "config.json"


@pytest.fixture
def empty_config(mock_config_file: Path) -> Path:
    """An empty config.json file (no skills_dirs)."""
    mock_config_file.write_text("{}", encoding="utf-8")
    return mock_config_file


@pytest.fixture
def valid_config(mock_config_file: Path, sample_skills_dir: Path) -> Path:
    """A config.json with valid skills_dirs pointing to sample_skills_dir."""
    config = {
        "skills_dirs": [
            {"path": str(sample_skills_dir), "type": "mtime"},
            str(sample_skills_dir),  # also test string form
        ]
    }
    mock_config_file.write_text(json.dumps(config), encoding="utf-8")
    return mock_config_file


# === Subprocess mock helpers ===

class MockSubprocessResult:
    """Build a mock subprocess.CompletedProcess result."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def mock_run_success(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Return a mock side_effect that returns success with given stdout."""

    def mock_run(*args, **kwargs):
        return MockSubprocessResult(returncode=returncode, stdout=stdout, stderr=stderr)

    return mock_run


def mock_run_failure(returncode: int = 1, stderr: str = ""):
    """Return a mock side_effect that returns failure."""

    def mock_run(*args, **kwargs):
        return MockSubprocessResult(returncode=returncode, stderr=stderr)

    return mock_run


def mock_run_not_found():
    """Return a mock side_effect that raises FileNotFoundError."""

    def mock_run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    return mock_run


def mock_run_timeout():
    """Return a mock side_effect that raises TimeoutExpired."""

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "", timeout=30)

    return mock_run