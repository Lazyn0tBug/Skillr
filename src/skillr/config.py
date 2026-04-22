"""Configuration management for Skillr.

Reads skills_dirs from the plugin's userConfig, which Claude Code stores at:
  ${CLAUDE_PLUGIN_DATA}/config.json

The config file format:
  {
    "skills_dirs": [
      {"path": "~/.claude/skills", "type": "git"},
      {"/path/to/project-skills", "type": "mtime"}
    ],
    "embedding_backend": "claude",
    "cache_secret": "<hex-encoded HMAC key for cache integrity>"
  }

If the config file does not exist or skills_dirs is not set, returns defaults.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path


def _get_plugin_data_dir() -> Path:
    """Return the CLAUDE_PLUGIN_DATA directory path."""
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data)
    # Fallback for local development
    return Path.home() / ".claude" / "plugins" / "data" / "skillr"


def get_embedding_backend() -> str:
    """Return the configured embedding backend: 'claude' (default) or 'model'.

    'claude': main session LLM does direct semantic matching (no vector preprocessing)
    'model': fastembed ONNX does vector pre-filtering before LLM ranking
    """
    plugin_data_dir = _get_plugin_data_dir()
    config_file = plugin_data_dir / "config.json"

    if not config_file.exists():
        return "claude"

    try:
        with open(config_file) as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "claude"

    return config.get("embedding_backend", "claude")


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


def get_cache_secret() -> str:
    """Return the machine-specific cache HMAC secret, generating once if needed.

    The secret is stored in ${CLAUDE_PLUGIN_DATA}/config.json and is unique per
    machine/install. It is used to sign intent cache entries so that tampering
    (ADV-007) can be detected.
    """
    plugin_data_dir = _get_plugin_data_dir()
    config_file = plugin_data_dir / "config.json"

    # Load existing config
    config: dict = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    # Return existing secret if already generated
    if config.get("cache_secret"):
        return config["cache_secret"]

    # Generate new 256-bit secret
    secret = secrets.token_hex(32)
    config["cache_secret"] = secret

    # Persist to config.json atomically (same pattern as cache.py)
    tmp_path = config_file.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp_path.rename(config_file)

    return secret
