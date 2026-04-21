"""Data models for Skillr."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    """Metadata for a single Skill, parsed from SKILL.md frontmatter."""

    name: str = Field(
        description="Skill name from SKILL.md frontmatter 'name' field (slash command = /<name>)"
    )
    description: str = Field(
        description="Skill description from SKILL.md frontmatter (used for LLM matching)"
    )
    file_path: Path = Field(description="Absolute path to the SKILL.md file")
    has_slash_command: bool = Field(
        default=True,
        description="Whether this skill has a registered slash command. False for agent-like skills (e.g., hermes) that require '使用 <name> skill' format",
    )


class SourceTracking(BaseModel):
    """Tracking info for a single skills_dir (git-aware or mtime-based)."""

    type: Literal["git", "mtime"] = Field(description="Tracking strategy for this directory")
    value: str = Field(description="For 'git': commit hash. For 'mtime': mtime as ISO string")
    # Per-skill-file mtime tracking: skill_name -> mtime as ISO string
    # Used for incremental index updates (detect which files changed)
    file_mtimes: dict[str, str] = Field(
        default_factory=dict,
        description="Per-skill file mtimes: skill name -> mtime ISO string",
    )


class SkillrIndex(BaseModel):
    """The complete Skillr index stored as JSON."""

    version: str = Field(default="1.0.0", description="Index schema version")
    generated_at: str = Field(description="ISO timestamp when index was generated")
    skills_dirs: list[str] = Field(description="List of scanned skills_dir paths")
    skills: list[SkillMeta] = Field(default_factory=list, description="All discovered Skills")
    # dir_path -> SourceTracking instance (deserialized from {"type": ..., "value": ...})
    source_tracking: dict[str, SourceTracking] = Field(
        default_factory=dict,
        description="Per-directory tracking info: type and value (git hash or mtime ISO string)",
    )
    retrieval_window: int = Field(
        default=50,
        description="Number of top skills to pass to LLM for ranking (avoids context overflow)",
    )


class IntentSpec(BaseModel):
    """Structured intent extracted from user task via LLM."""

    original_task: str = Field(description="The user's original natural-language input")
    intent: str = Field(description="Refined intent description (1-2 sentences)")
    constraints: list[str] = Field(default_factory=list, description="Any constraints mentioned")
    keywords: list[str] = Field(default_factory=list, description="3-5 keywords for filtering")


class MatchResult(BaseModel):
    """A matched Skill with relevance score and explanation."""

    name: str = Field(description="Skill name")
    score: float = Field(ge=0.0, le=1.0, description="Relevance score 0.0-1.0")
    match_reason: str = Field(description="Why this skill matches the user's intent (1 sentence)")


class IntentCacheEntry(BaseModel):
    """A cached intent matching result entry."""

    intent_hash: str = Field(description="SHA256 hash of the intent text")
    skill_ids_hash: str = Field(
        description="SHA256 hash of sorted skill IDs (changes when skills change)"
    )
    match_results: list[MatchResult] = Field(
        default_factory=list, description="Cached match results"
    )
    created_at: str = Field(description="ISO timestamp when entry was created")
    ttl_seconds: int = Field(default=3600, description="Time-to-live in seconds")


class IntentCache(BaseModel):
    """Disk-persistent cache of intent matching results."""

    version: str = Field(default="1.0.0", description="Cache schema version")
    entries: dict[str, IntentCacheEntry] = Field(
        default_factory=dict,
        description="Cache entries keyed by intent_hash",
    )
