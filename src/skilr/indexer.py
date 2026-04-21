"""Skill indexer — generates and persists the SkilrIndex JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .config import ensure_plugin_data_dir, get_skills_dirs
from .models import SkillMeta, SkilrIndex, SourceTracking
from .scanner import (
    get_git_commit_hash,
    get_git_tracked_files,
    is_git_repo,
    scan_skills_dir,
)


def get_source_tracking_value(skills_dir: Path) -> dict[str, str]:
    """Return the tracking dict for a skills_dir.

    Tier 1: git-aware (if directory is a git repo)
    Tier 2: per-file mtime (if not git)
    """
    if is_git_repo(skills_dir):
        commit_hash = get_git_commit_hash(skills_dir)
        if commit_hash:
            return {"type": "git", "value": commit_hash}
    try:
        mtime = skills_dir.stat().st_mtime
        from datetime import datetime, timezone
        return {"type": "mtime", "value": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()}
    except OSError:
        return {"type": "mtime", "value": "0"}


def scan_all_skills_dirs() -> tuple[list[SkillMeta], dict[str, dict]]:
    """Scan all configured skills_dirs and return skills + source_tracking map.

    Returns:
        skills: flat list of all discovered SkillMeta
        source_tracking: dict[dir_path_str, tracking_dict]
    """
    skills_dirs = get_skills_dirs()
    all_skills: list[SkillMeta] = []
    source_tracking: dict[str, dict] = {}

    for skills_dir in skills_dirs:
        dir_skills = scan_skills_dir(skills_dir)
        all_skills.extend(dir_skills)
        source_tracking[str(skills_dir)] = get_source_tracking_value(skills_dir)

    return all_skills, source_tracking


def build_index() -> SkilrIndex:
    """Build a fresh SkilrIndex from all configured skills_dirs."""
    skills_dirs = [str(d) for d in get_skills_dirs()]
    skills, source_tracking = scan_all_skills_dirs()

    return SkilrIndex(
        version="1.0.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        skills_dirs=skills_dirs,
        skills=skills,
        source_tracking=source_tracking,
        retrieval_window=50,
    )


def save_index(index: SkilrIndex) -> Path:
    """Save the SkilrIndex to ${CLAUDE_PLUGIN_DATA}/index/skilr_index.json."""
    plugin_data_dir = ensure_plugin_data_dir()
    index_dir = plugin_data_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    index_path = index_dir / "skilr_index.json"
    index_bytes = index.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
    index_path.write_bytes(index_bytes)

    return index_path


def load_index() -> SkilrIndex | None:
    """Load the existing SkilrIndex, or return None if not found."""
    plugin_data_dir = ensure_plugin_data_dir()
    index_path = plugin_data_dir / "index" / "skilr_index.json"

    if not index_path.exists():
        return None

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return SkilrIndex.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None


def run_indexer() -> tuple[Path, int]:
    """Run the full indexer: scan skills_dirs, save index, return (index_path, skill_count)."""
    index = build_index()
    index_path = save_index(index)
    return index_path, len(index.skills)
