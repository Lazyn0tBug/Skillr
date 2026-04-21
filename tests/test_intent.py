"""Unit tests for Skillr intent module."""

from __future__ import annotations

from skillr.intent import build_intent_prompt, parse_intent_response


class TestBuildIntentPrompt:
    def test_contains_user_task(self):
        prompt = build_intent_prompt("I want to build a REST API")
        assert "I want to build a REST API" in prompt

    def test_requests_intent_constraints_keywords(self):
        prompt = build_intent_prompt("test task")
        assert "intent" in prompt
        assert "constraints" in prompt
        assert "keywords" in prompt


class TestParseIntentResponse:
    def test_valid_response(self):
        response = '{"intent": "Build a REST API", "constraints": ["python", "fast"], "keywords": ["api", "rest"]}'
        result = parse_intent_response(response, "original task")
        assert result is not None
        assert result.intent == "Build a REST API"
        assert result.constraints == ["python", "fast"]
        assert result.keywords == ["api", "rest"]
        assert result.original_task == "original task"

    def test_missing_intent_field(self):
        response = '{"constraints": [], "keywords": ["api"]}'
        result = parse_intent_response(response, "task")
        assert result is None

    def test_missing_keywords_field(self):
        response = '{"intent": "test"}'
        result = parse_intent_response(response, "task")
        assert result is None

    def test_non_list_constraints(self):
        # constraints is a string, not a list
        response = '{"intent": "test", "constraints": "无", "keywords": ["api"]}'
        result = parse_intent_response(response, "task")
        assert result is None

    def test_empty_constraints(self):
        response = '{"intent": "test", "constraints": [], "keywords": ["api"]}'
        result = parse_intent_response(response, "task")
        assert result is not None
        assert result.constraints == []

    def test_constraints_defaults_to_empty_list(self):
        response = '{"intent": "test", "keywords": ["api"]}'
        result = parse_intent_response(response, "task")
        assert result is not None
        assert result.constraints == []

    def test_no_json_found(self):
        result = parse_intent_response("Here is some text without JSON", "task")
        assert result is None

    def test_invalid_json(self):
        result = parse_intent_response("{not valid json", "task")
        assert result is None

    def test_non_greedy_regex_avoids_trailing_content(self):
        # JSON object followed by trailing text with a closing brace
        response = '{"intent": "test", "constraints": [], "keywords": ["api"]}  -- some explanation {extra}'
        result = parse_intent_response(response, "task")
        assert result is not None
        assert result.intent == "test"

    def test_nested_json_with_trailing_content(self):
        # Non-greedy should match first JSON block, not last closing brace
        response = '{"intent": "test", "constraints": [], "keywords": ["api"]} and more text {also: "valid"}'
        result = parse_intent_response(response, "task")
        # Should successfully parse the first JSON block
        assert result is not None
        assert result.intent == "test"

    def test_empty_response(self):
        result = parse_intent_response("", "task")
        assert result is None

    def test_whitespace_only_response(self):
        result = parse_intent_response("   \n  ", "task")
        assert result is None
