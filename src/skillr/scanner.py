"""Skill scanner — discovers Skills by walking skills_dirs and parsing SKILL.md frontmatter."""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path

import yaml

from .models import SkillMeta


def is_git_repo(directory: Path) -> bool:
    """Return True if directory is a git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_git_tracked_files(directory: Path) -> set[str]:
    """Return set of git-tracked SKILL.md file paths (relative to directory)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--modified", "**/SKILL.md"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return set()
        files = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()


def get_git_commit_hash(directory: Path) -> str | None:
    """Return current git commit hash for directory, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def parse_skill_frontmatter(skill_md_path: Path) -> SkillMeta | None:
    """Parse SKILL.md and extract name + description from YAML frontmatter.

    Returns None if parsing fails or required fields are missing.
    Logs a warning for skipped files.
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError as e:
        warnings.warn(f"Cannot read {skill_md_path}: {e}")
        return None

    if not content.startswith("---"):
        warnings.warn(f"SKILL.md missing YAML frontmatter marker: {skill_md_path}")
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        warnings.warn(f"SKILL.md frontmatter parse error: {skill_md_path}")
        return None

    frontmatter_text = parts[1]
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        warnings.warn(f"YAML parse error in {skill_md_path}: {e}")
        return None

    if not isinstance(frontmatter, dict):
        warnings.warn(f"SKILL.md frontmatter is not a dict: {skill_md_path}")
        return None

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    has_slash_command = frontmatter.get("has_slash_command", True)

    if not name or not description:
        warnings.warn(f"SKILL.md missing 'name' or 'description': {skill_md_path}")
        return None

    return SkillMeta(
        name=str(name).strip(),
        description=str(description),
        file_path=skill_md_path,
        has_slash_command=bool(has_slash_command),
    )


def get_skill_file_mtime(skill_md_path: Path) -> str:
    """Return the mtime of a SKILL.md file as an ISO string."""
    try:
        mtime = skill_md_path.stat().st_mtime
        from datetime import UTC, datetime

        return datetime.fromtimestamp(mtime, tz=UTC).isoformat()
    except OSError:
        return ""


def scan_skills_dir(skills_dir: Path) -> tuple[list[SkillMeta], dict[str, str]]:
    """Scan a single skills_dir and return all discovered SkillMeta entries.

    Returns:
        skills: list of SkillMeta for discovered skills
        file_mtimes: dict of skill_name -> mtime ISO string (for incremental index)

    Walks immediate subdirectories looking for SKILL.md files.
    Skips subdirectories without SKILL.md.
    """
    skills: list[SkillMeta] = []
    file_mtimes: dict[str, str] = {}

    if not skills_dir.is_dir():
        warnings.warn(f"skills_dir is not a directory: {skills_dir}")
        return skills, file_mtimes

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        skill = parse_skill_frontmatter(skill_md)
        if skill is not None:
            skills.append(skill)
            file_mtimes[skill.name] = get_skill_file_mtime(skill_md)

    return skills, file_mtimes
