"""Configuration management for Skillr.

Reads skills_dirs from the plugin's userConfig, which Claude Code stores at:
  ${CLAUDE_PLUGIN_DATA}/config.json

The config file format:
  {
    "skills_dirs": [
      {"path": "~/.claude/skills", "type": "git"},
      {"/path/to/project-skills", "type": "mtime"}
    ]
  }

If the config file does not exist or skills_dirs is not set, returns defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _get_plugin_data_dir() -> Path:
    """Return the CLAUDE_PLUGIN_DATA directory path."""
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data)
    # Fallback for local development
    return Path.home() / ".claude" / "plugins" / "data" / "skillr"


def get_skills_dirs() -> list[Path]:
    """Return the configured skills_dirs as expanded Path objects.

    Reads from ${CLAUDE_PLUGIN_DATA}/config.json. If not configured,
    returns an empty list (caller should prompt user).
    """
    plugin_data_dir = _get_plugin_data_dir()
    config_file = plugin_data_dir / "config.json"

    if not config_file.exists():
        return []

    try:
        with open(config_file) as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    skills_dirs_raw = config.get("skills_dirs", [])
    if not isinstance(skills_dirs_raw, list):
        return []

    paths: list[Path] = []
    for entry in skills_dirs_raw:
        if isinstance(entry, str):
            path = Path(entry).expanduser().resolve()
        elif isinstance(entry, dict):
            path = Path(entry.get("path", "")).expanduser().resolve()
        else:
            continue
        if path.exists():
            paths.append(path)

    return paths


def ensure_plugin_data_dir() -> Path:
    """Ensure the plugin data directory exists."""
    plugin_data_dir = _get_plugin_data_dir()
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    return plugin_data_dir
