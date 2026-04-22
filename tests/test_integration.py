"""Integration tests for Skillr — cross-module data flow."""

from __future__ import annotations

from pathlib import Path

from skillr.indexer import build_incremental_index, load_index, save_index, scan_all_skills_dirs
from skillr.intent import build_intent_prompt, parse_intent_response
from skillr.matcher import build_matcher_prompt, keyword_filter, parse_matcher_response
from skillr.models import IntentSpec, MatchResult, SkillMeta, SourceTracking
from skillr.router import (
    assemble_command,
    format_match_results_for_display,
    parse_selection,
    select_skill_by_number,
)


class TestScannerIndexerChain:
    """Test scanner -> indexer integration."""

    def test_scan_feeds_into_index(
        self, sample_skills_dir: Path, mocker, mock_plugin_data_dir: Path
    ):
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[sample_skills_dir])
        mocker.patch(
            "skillr.indexer.get_source_tracking_value",
            return_value=SourceTracking(type="mtime", value="0"),
        )

        skills, tracking = scan_all_skills_dirs()
        assert len(skills) == 3

        index = build_incremental_index()
        assert len(index.skills) == 3
        assert index.source_tracking[str(sample_skills_dir)].type == "mtime"


class TestConfigScannerIndexerPipeline:
    """Test full pipeline from config to saved index."""

    def test_full_pipeline(self, sample_skills_dir: Path, mocker, mock_plugin_data_dir: Path):
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[sample_skills_dir])
        mocker.patch(
            "skillr.indexer.get_source_tracking_value",
            return_value=SourceTracking(type="mtime", value="0"),
        )

        index = build_incremental_index()
        path = save_index(index)
        assert path.exists()

        # Load it back
        loaded = load_index()
        assert loaded is not None
        assert len(loaded.skills) == 3


class TestIntentMatcherChain:
    """Test intent -> matcher integration."""

    def test_parsed_intent_feeds_into_matcher_prompt(self):
        skills = [
            SkillMeta(name="api-skill", description="Build REST APIs", file_path=Path("/p")),
            SkillMeta(name="db-skill", description="Database utilities", file_path=Path("/p2")),
        ]
        intent = IntentSpec(
            original_task="I want to build an API",
            intent="Build a REST API",
            constraints=[],
            keywords=["api", "rest"],
        )
        prompt = build_matcher_prompt(skills, intent)
        assert "Build a REST API" in prompt
        assert "api" in prompt


class TestKeywordFilterThenMatcher:
    """Test keyword filter pre-filtering before LLM ranking."""

    def test_keyword_filter_reduces_candidates(self):
        skills = [
            SkillMeta(name="api-skill", description="Build REST APIs", file_path=Path("/p")),
            SkillMeta(name="db-skill", description="Database utilities", file_path=Path("/p2")),
            SkillMeta(name="auth-skill", description="Authentication", file_path=Path("/p3")),
        ]
        filtered = keyword_filter(skills, ["api", "rest"])
        assert len(filtered) == 1
        assert filtered[0].name == "api-skill"

    def test_empty_keyword_returns_all(self):
        skills = [
            SkillMeta(name="api-skill", description="Build REST APIs", file_path=Path("/p")),
            SkillMeta(name="db-skill", description="Database utilities", file_path=Path("/p2")),
        ]
        filtered = keyword_filter(skills, [])
        assert len(filtered) == 2


class TestRouterWorkflowIntegration:
    """Test router functions working together."""

    def test_selection_to_command_flow(self):
        results = [
            MatchResult(name="skill1", score=0.9, match_reason="Matches well"),
            MatchResult(name="skill2", score=0.7, match_reason="Also good"),
        ]
        skills_map = {
            "skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p1")),
            "skill2": SkillMeta(name="skill2", description="desc", file_path=Path("/p2")),
        }

        # Parse selection "1,2" -> [1, 2]
        indices = parse_selection("1,2")
        assert indices == [1, 2]

        # Select each
        selected = [select_skill_by_number(i, results, skills_map) for i in indices]
        assert len(selected) == 2
        assert selected[0].name == "skill1"
        assert selected[1].name == "skill2"

        # Assemble commands
        commands = [assemble_command(s, "refined intent") for s in selected]
        assert commands == ["/skill1 refined intent", "/skill2 refined intent"]

    def test_format_shows_all_matches(self):
        results = [
            MatchResult(name="skill1", score=0.9, match_reason="Best match"),
            MatchResult(name="skill2", score=0.8, match_reason="Second best"),
        ]
        skills_map = {
            "skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p1")),
            "skill2": SkillMeta(name="skill2", description="desc", file_path=Path("/p2")),
        }
        output = format_match_results_for_display(results, skills_map)
        assert "找到 2 个匹配的 Skills" in output
        assert "/skill1" in output
        assert "/skill2" in output
        assert "Best match" in output


class TestEndToEndIntentParsing:
    """Test intent parsing round-trip."""

    def test_build_prompt_then_parse_mock_response(self):
        prompt = build_intent_prompt("I want to build a REST API with authentication")
        assert "I want to build a REST API with authentication" in prompt

        # Simulate LLM response
        mock_response = '{"intent": "Build a REST API with auth", "constraints": ["python"], "keywords": ["api", "rest", "auth"]}'
        parsed = parse_intent_response(
            mock_response, "I want to build a REST API with authentication"
        )
        assert parsed is not None
        assert parsed.intent == "Build a REST API with auth"
        assert "python" in parsed.constraints
        assert "api" in parsed.keywords


class TestEndToEndMatcherParsing:
    """Test matcher response parsing round-trip."""

    def test_build_prompt_then_parse_mock_response(self):
        skills = [
            SkillMeta(name="api-skill", description="Build REST APIs", file_path=Path("/p1")),
            SkillMeta(name="db-skill", description="Database utilities", file_path=Path("/p2")),
        ]
        intent = IntentSpec(
            original_task="build API",
            intent="Build a REST API with auth",
            constraints=[],
            keywords=["api", "rest"],
        )
        prompt = build_matcher_prompt(skills, intent)
        assert "Build a REST API with auth" in prompt

        # Simulate LLM ranking response
        mock_response = (
            '[{"name": "api-skill", "score": 0.95, "match_reason": "Exact match for API building"}]'
        )
        parsed = parse_matcher_response(mock_response)
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0].name == "api-skill"
        assert parsed[0].score == 0.95
