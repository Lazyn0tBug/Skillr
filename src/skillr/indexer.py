"""Skill indexer — generates and persists the SkillrIndex JSON."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .config import ensure_plugin_data_dir, get_skills_dirs
from .models import SkillMeta, SkillrIndex, SourceTracking
from .scanner import (
    get_git_commit_hash,
    is_git_repo,
    scan_skills_dir,
)


def get_source_tracking_value(
    skills_dir: Path,
    file_mtimes: dict[str, str] | None = None,
) -> SourceTracking:
    """Return the tracking value for a skills_dir.

    Tier 1: git-aware (if directory is a git repo)
    Tier 2: per-file mtime (if not git)
    """
    if is_git_repo(skills_dir):
        commit_hash = get_git_commit_hash(skills_dir)
        if commit_hash:
            return SourceTracking(type="git", value=commit_hash, file_mtimes=file_mtimes)
    try:
        mtime = skills_dir.stat().st_mtime
        return SourceTracking(
            type="mtime",
            value=datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
            file_mtimes=file_mtimes,
        )
    except OSError:
        return SourceTracking(type="mtime", value="0", file_mtimes=file_mtimes)


def scan_all_skills_dirs() -> tuple[list[SkillMeta], dict[str, SourceTracking]]:
    """Scan all configured skills_dirs and return skills + source_tracking map.

    Returns:
        skills: flat list of all discovered SkillMeta
        source_tracking: dict[dir_path_str, SourceTracking]
    """
    skills_dirs = get_skills_dirs()
    all_skills: list[SkillMeta] = []
    source_tracking: dict[str, SourceTracking] = {}

    for skills_dir in skills_dirs:
        dir_skills, dir_file_mtimes = scan_skills_dir(skills_dir)
        all_skills.extend(dir_skills)
        source_tracking[str(skills_dir)] = get_source_tracking_value(skills_dir, dir_file_mtimes)

    return all_skills, source_tracking


def _skills_from_dir(skills_dir: Path, skills: list[SkillMeta]) -> list[SkillMeta]:
    """Return skills that belong to a specific skills_dir.

    A skill belongs to skills_dir if its SKILL.md file is directly under a
    subdirectory of skills_dir (i.e., skills_dir/skill_name/SKILL.md).
    """
    return [s for s in skills if s.file_path.parent.parent == skills_dir]


def build_incremental_index() -> SkillrIndex:
    """Build index, skipping dirs whose file_mtimes haven't changed since last build.

    If no previous index exists, performs a full scan.
    """
    prev_index = load_index()
    skills_dirs = get_skills_dirs()

    all_skills: list[SkillMeta] = []
    source_tracking: dict[str, SourceTracking] = {}

    for skills_dir in skills_dirs:
        dir_path_str = str(skills_dir)

        # Check if we can reuse the previous index's data for this dir
        if prev_index and dir_path_str in prev_index.source_tracking:
            prev_tracking = prev_index.source_tracking[dir_path_str]

            # Git-based: skip if commit hash unchanged
            if prev_tracking.type == "git":
                commit_hash = get_git_commit_hash(skills_dir)
                if commit_hash and commit_hash == prev_tracking.value:
                    # No changes — reuse previous data
                    source_tracking[dir_path_str] = prev_tracking
                    all_skills.extend(_skills_from_dir(skills_dir, prev_index.skills))
                    continue

            # Mtime-based: compare per-file mtimes
            if prev_tracking.type == "mtime":
                dir_skills, dir_file_mtimes = scan_skills_dir(skills_dir)

                # Check if all current file_mtimes match previous
                prev_mtimes = prev_tracking.file_mtimes or {}
                if dir_file_mtimes == prev_mtimes:
                    # No changes — reuse previous data
                    source_tracking[dir_path_str] = prev_tracking
                    all_skills.extend(_skills_from_dir(skills_dir, prev_index.skills))
                    continue

                # Changes detected — use fresh scan results
                all_skills.extend(dir_skills)
                source_tracking[dir_path_str] = get_source_tracking_value(
                    skills_dir, dir_file_mtimes
                )
        else:
            # No previous data for this dir — full scan
            dir_skills, dir_file_mtimes = scan_skills_dir(skills_dir)
            all_skills.extend(dir_skills)
            source_tracking[dir_path_str] = get_source_tracking_value(skills_dir, dir_file_mtimes)

    return SkillrIndex(
        version="1.0.0",
        generated_at=datetime.now(UTC).isoformat(),
        skills_dirs=[str(d) for d in skills_dirs],
        skills=all_skills,
        source_tracking=source_tracking,
        retrieval_window=50,
    )


def build_index() -> SkillrIndex:
    """Build a fresh SkillrIndex from all configured skills_dirs."""
    skills_dirs = [str(d) for d in get_skills_dirs()]
    skills, source_tracking = scan_all_skills_dirs()

    return SkillrIndex(
        version="1.0.0",
        generated_at=datetime.now(UTC).isoformat(),
        skills_dirs=skills_dirs,
        skills=skills,
        source_tracking=source_tracking,
        retrieval_window=50,
    )


def save_index(index: SkillrIndex) -> Path:
    """Save the SkillrIndex to ${CLAUDE_PLUGIN_DATA}/index/skillr_index.json."""
    plugin_data_dir = ensure_plugin_data_dir()
    index_dir = plugin_data_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    index_path = index_dir / "skillr_index.json"
    index_bytes = index.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
    index_path.write_bytes(index_bytes)

    return index_path


def load_index() -> SkillrIndex | None:
    """Load the existing SkillrIndex, or return None if not found."""
    plugin_data_dir = ensure_plugin_data_dir()
    index_path = plugin_data_dir / "index" / "skillr_index.json"

    if not index_path.exists():
        return None

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return SkillrIndex.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None


def run_indexer() -> tuple[Path, int]:
    """Run the full indexer: scan skills_dirs, save index, return (index_path, skill_count)."""
    index = build_index()
    index_path = save_index(index)
    return index_path, len(index.skills)
