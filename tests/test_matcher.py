"""Unit tests for Skillr matcher module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillr.matcher import build_matcher_prompt, keyword_filter, parse_matcher_response
from skillr.models import IntentSpec, SkillMeta


class TestKeywordFilter:
    def test_matches_one_keyword(self):
        skills = [
            SkillMeta(name="api-skill", description="Build REST APIs", file_path=Path("/p")),
        ]
        result = keyword_filter(skills, ["api"])
        assert len(result) == 1

    def test_matches_in_description(self):
        skills = [
            SkillMeta(name="skill1", description="Database migration tool", file_path=Path("/p")),
        ]
        result = keyword_filter(skills, ["database"])
        assert len(result) == 1

    def test_matches_case_insensitive(self):
        skills = [
            SkillMeta(name="api-skill", description="REST API Builder", file_path=Path("/p")),
        ]
        result = keyword_filter(skills, ["REST"])
        assert len(result) == 1

    def test_no_matches(self):
        skills = [
            SkillMeta(name="skill1", description="Description", file_path=Path("/p")),
        ]
        result = keyword_filter(skills, ["nonexistent"])
        assert len(result) == 0

    def test_empty_keywords_returns_all(self):
        skills = [
            SkillMeta(name="skill1", description="Description", file_path=Path("/p")),
            SkillMeta(name="skill2", description="Description 2", file_path=Path("/p2")),
        ]
        result = keyword_filter(skills, [])
        assert len(result) == 2

    def test_multiple_keywords_any_match(self):
        skills = [
            SkillMeta(name="skill1", description="Python web API", file_path=Path("/p")),
        ]
        # "python" matches but "java" doesn't - one match is enough
        result = keyword_filter(skills, ["python", "java"])
        assert len(result) == 1

    def test_searches_combined_name_description(self):
        skills = [
            SkillMeta(name="api-builder", description="Build things", file_path=Path("/p")),
        ]
        # "builder" is in name, "things" is in description
        result = keyword_filter(skills, ["builder", "things"])
        assert len(result) == 1


class TestBuildMatcherPrompt:
    def test_contains_intent(self):
        skills = []
        intent = IntentSpec(original_task="test", intent="Build REST API", constraints=[], keywords=["api"])
        prompt = build_matcher_prompt(skills, intent)
        assert "Build REST API" in prompt

    def test_serializes_skills_as_json(self):
        skills = [
            SkillMeta(name="skill1", description="Description 1", file_path=Path("/p1")),
            SkillMeta(name="skill2", description="Description 2", file_path=Path("/p2")),
        ]
        intent = IntentSpec(original_task="test", intent="test", constraints=[], keywords=[])
        prompt = build_matcher_prompt(skills, intent)
        assert "skill1" in prompt
        assert "Description 1" in prompt

    def test_top_k_parameter(self):
        skills = []
        intent = IntentSpec(original_task="test", intent="test", constraints=[], keywords=[])
        prompt = build_matcher_prompt(skills, intent, top_k=3)
        assert "Top 3" in prompt or "top_k" in prompt or "3" in prompt


class TestParseMatcherResponse:
    def test_valid_response(self):
        response = '[{"name": "skill1", "score": 0.9, "match_reason": "Matches well"}]'
        result = parse_matcher_response(response)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "skill1"
        assert result[0].score == 0.9
        assert result[0].match_reason == "Matches well"

    def test_multiple_results(self):
        response = '[{"name": "s1", "score": 0.9, "match_reason": "Good"}, {"name": "s2", "score": 0.7, "match_reason": "OK"}]'
        result = parse_matcher_response(response)
        assert result is not None
        assert len(result) == 2

    def test_invalid_item_missing_name(self):
        response = '[{"score": 0.9, "match_reason": "No name"}]'
        result = parse_matcher_response(response)
        # Should skip invalid item, return empty or partial
        # The function skips items that don't have name
        assert result is not None
        assert len(result) == 0

    def test_invalid_item_missing_score(self):
        response = '[{"name": "skill1", "match_reason": "No score"}]'
        result = parse_matcher_response(response)
        assert result is not None
        assert len(result) == 0

    def test_invalid_item_missing_reason(self):
        response = '[{"name": "skill1", "score": 0.9}]'
        result = parse_matcher_response(response)
        assert result is not None
        assert len(result) == 0

    def test_non_list_response(self):
        result = parse_matcher_response('{"name": "skill1"}')
        assert result is None

    def test_no_json_array_found(self):
        result = parse_matcher_response("No JSON array here")
        assert result is None

    def test_invalid_json(self):
        result = parse_matcher_response("[not valid json")
        assert result is None

    def test_non_greedy_avoids_trailing_content(self):
        response = '[{"name": "s1", "score": 0.9, "match_reason": "Good"}] and more text [also: "array"]'
        result = parse_matcher_response(response)
        # Should match first array, not second
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "s1"

    def test_score_is_float(self):
        response = '[{"name": "skill1", "score": 1, "match_reason": "Int score"}]'
        result = parse_matcher_response(response)
        assert result is not None
        assert result[0].score == 1.0

    def test_empty_response(self):
        result = parse_matcher_response("")
        assert result is None

    def test_whitespace_only_response(self):
        result = parse_matcher_response("   \n  ")
        assert result is None