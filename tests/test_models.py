"""Unit tests for Skillr data models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from skilr.models import (
    IntentSpec,
    MatchResult,
    SkillMeta,
    SkilrIndex,
    SourceTracking,
)


class TestSkillMeta:
    def test_valid_construction(self):
        skill = SkillMeta(
            name="test-skill",
            description="A test skill",
            file_path=Path("/path/to/SKILL.md"),
        )
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.file_path == Path("/path/to/SKILL.md")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            SkillMeta(description="desc", file_path=Path("/path"))
        assert "name" in str(exc_info.value)

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            SkillMeta(name="name", file_path=Path("/path"))
        assert "description" in str(exc_info.value)


class TestSourceTracking:
    def test_git_type(self):
        tracking = SourceTracking(type="git", value="abc123")
        assert tracking.type == "git"
        assert tracking.value == "abc123"

    def test_mtime_type(self):
        tracking = SourceTracking(type="mtime", value=datetime.now(timezone.utc).isoformat())
        assert tracking.type == "mtime"

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            SourceTracking(type="svn", value="abc123")  # type must be "git" or "mtime"


class TestSkilrIndex:
    def test_full_construction(self):
        skills = [
            SkillMeta(name="s1", description="d1", file_path=Path("/s1/SKILL.md")),
            SkillMeta(name="s2", description="d2", file_path=Path("/s2/SKILL.md")),
        ]
        tracking = {
            "/skills": SourceTracking(type="git", value="hash123"),
        }
        index = SkilrIndex(
            version="1.0.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            skills_dirs=["/skills"],
            skills=skills,
            source_tracking=tracking,
            retrieval_window=50,
        )
        assert index.version == "1.0.0"
        assert len(index.skills) == 2
        assert index.retrieval_window == 50

    def test_defaults(self):
        index = SkilrIndex(
            generated_at="2026-01-01T00:00:00Z",
            skills_dirs=[],
            skills=[],
            source_tracking={},
        )
        assert index.version == "1.0.0"
        assert index.retrieval_window == 50


class TestIntentSpec:
    def test_full_construction(self):
        spec = IntentSpec(
            original_task="I want to build a REST API",
            intent="Build a REST API with authentication",
            constraints=["must use Python", "must be fast"],
            keywords=["api", "rest", "python"],
        )
        assert spec.original_task == "I want to build a REST API"
        assert spec.intent == "Build a REST API with authentication"
        assert len(spec.constraints) == 2
        assert len(spec.keywords) == 3

    def test_defaults(self):
        spec = IntentSpec(
            original_task="test",
            intent="test intent",
            constraints=[],
            keywords=[],
        )
        assert spec.constraints == []
        assert spec.keywords == []


class TestMatchResult:
    def test_valid_score_bounds(self):
        result = MatchResult(name="skill", score=0.75, match_reason="Matches well")
        assert result.score == 0.75

    def test_score_zero(self):
        result = MatchResult(name="skill", score=0.0, match_reason="Barely matches")
        assert result.score == 0.0

    def test_score_one(self):
        result = MatchResult(name="skill", score=1.0, match_reason="Perfect match")
        assert result.score == 1.0

    def test_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            MatchResult(name="skill", score=-0.1, match_reason="Invalid")

    def test_score_above_one_raises(self):
        with pytest.raises(ValidationError):
            MatchResult(name="skill", score=1.5, match_reason="Invalid")