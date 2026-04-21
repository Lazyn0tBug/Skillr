"""Data models for Skillr."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    """Metadata for a single Skill, parsed from SKILL.md frontmatter."""

    name: str = Field(description="Skill name from SKILL.md frontmatter 'name' field (slash command = /<name>)")
    description: str = Field(description="Skill description from SKILL.md frontmatter (used for LLM matching)")
    file_path: Path = Field(description="Absolute path to the SKILL.md file")


class SourceTracking(BaseModel):
    """Tracking info for a single skills_dir (git-aware or mtime-based)."""

    type: Literal["git", "mtime"] = Field(description="Tracking strategy for this directory")
    value: str = Field(description="For 'git': commit hash. For 'mtime': mtime as ISO string")


class SkilrIndex(BaseModel):
    """The complete Skillr index stored as JSON."""

    version: str = Field(default="1.0.0", description="Index schema version")
    generated_at: str = Field(description="ISO timestamp when index was generated")
    skills_dirs: list[str] = Field(description="List of scanned skills_dir paths")
    skills: list[SkillMeta] = Field(default_factory=list, description="All discovered Skills")
    # dir_path -> {"type": "git"|"mtime", "value": str}
    source_tracking: dict[str, dict] = Field(
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
