"""Scenario tests for Skillr — end-to-end user stories."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skillr.indexer import load_index, run_indexer
from skillr.intent import build_intent_prompt, parse_intent_response
from skillr.matcher import build_matcher_prompt, keyword_filter, parse_matcher_response
from skillr.models import IntentSpec, SkillMeta
from skillr.router import (
    assemble_command,
    format_match_results_for_display,
    index_stale_or_missing,
    parse_selection,
    select_skill_by_number,
)


class TestScenarioFullIndexBuild:
    """Scenario 1: Full index build from empty state."""

    def test_run_indexer_produces_valid_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker
    ):
        # Setup plugin data dir
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        # Create temp skills directory with 3 skills
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        for name, desc in [
            ("skill-one", "First skill"),
            ("skill-two", "Second skill"),
            ("skill-three", "Third skill"),
        ]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n",
                encoding="utf-8",
            )

        # Mock get_skills_dirs in the indexer module (where it is imported)
        mocker.patch("skillr.indexer.get_skills_dirs", return_value=[skills_dir])

        index_path, count = run_indexer()
        assert index_path.exists()
        assert count == 3

        # Load and verify
        loaded = load_index()
        assert loaded is not None
        assert len(loaded.skills) == 3
        names = {s.name for s in loaded.skills}
        assert "skill-one" in names
        assert "skill-two" in names
        assert "skill-three" in names


class TestScenarioIntentParsing:
    """Scenario 2: Intent parsing round-trip with mocked LLM."""

    def test_user_task_to_intent_spec(self):
        user_task = "I need to build a user authentication system with JWT tokens"

        # Build prompt
        prompt = build_intent_prompt(user_task)
        assert user_task in prompt

        # Simulate LLM returning structured JSON (as the main session LLM would)
        mock_llm_response = json.dumps(
            {
                "intent": "Build a JWT-based user authentication system",
                "constraints": ["must use JWT", "should support refresh tokens"],
                "keywords": ["auth", "jwt", "login", "user"],
            }
        )

        # Parse back to IntentSpec
        intent_spec = parse_intent_response(mock_llm_response, user_task)

        assert intent_spec is not None
        assert intent_spec.original_task == user_task
        assert "JWT" in intent_spec.intent
        assert len(intent_spec.keywords) >= 3


class TestScenarioSkillMatching:
    """Scenario 3: Skill matching round-trip with mocked LLM."""

    def test_keyword_filter_then_matcher_prompt_and_parse(self):
        # Available skills
        skills = [
            SkillMeta(
                name="auth-jwt",
                description="JWT-based authentication system",
                file_path=Path("/p1"),
            ),
            SkillMeta(
                name="api-rest", description="REST API builder with FastAPI", file_path=Path("/p2")
            ),
            SkillMeta(
                name="db-postgres",
                description="PostgreSQL database utilities",
                file_path=Path("/p3"),
            ),
            SkillMeta(
                name="frontend-react", description="React component library", file_path=Path("/p4")
            ),
        ]

        # User intent
        intent_spec = IntentSpec(
            original_task="build auth system",
            intent="Build a JWT authentication system",
            constraints=["JWT required"],
            keywords=["auth", "jwt", "login"],
        )

        # Pre-filter with keyword filter
        prefiltered = keyword_filter(skills, intent_spec.keywords)
        # Should match auth-jwt (auth, jwt in name/description)
        assert len(prefiltered) >= 1
        assert any(s.name == "auth-jwt" for s in prefiltered)

        # Build matcher prompt
        prompt = build_matcher_prompt(prefiltered, intent_spec)
        assert "Build a JWT authentication system" in prompt

        # Simulate LLM ranking response
        mock_llm_response = json.dumps(
            [
                {
                    "name": "auth-jwt",
                    "score": 0.95,
                    "match_reason": "Direct match for JWT auth requirement",
                },
                {
                    "name": "api-rest",
                    "score": 0.6,
                    "match_reason": "Could be used to expose auth endpoints",
                },
            ]
        )

        # Parse match results
        match_results = parse_matcher_response(mock_llm_response)
        assert match_results is not None
        assert len(match_results) == 2
        assert match_results[0].name == "auth-jwt"
        assert match_results[0].score > match_results[1].score


class TestScenarioSelectionAndCommand:
    """Scenario 4: User selects skills and gets executable commands."""

    def test_selection_parsing_and_command_assembly(self):
        # Match results from LLM
        match_results = parse_matcher_response(
            '[{"name": "auth-jwt", "score": 0.95, "match_reason": "Best match"}, {"name": "api-rest", "score": 0.7, "match_reason": "Also relevant"}]'
        )
        skills_map = {
            "auth-jwt": SkillMeta(name="auth-jwt", description="JWT auth", file_path=Path("/p1")),
            "api-rest": SkillMeta(name="api-rest", description="REST API", file_path=Path("/p2")),
        }

        # Format for display
        display = format_match_results_for_display(match_results, skills_map)
        assert "找到 2 个匹配的 Skills" in display

        # User selects "1" (first choice)
        selection = parse_selection("1")
        selected = select_skill_by_number(selection[0], match_results, skills_map)
        assert selected is not None

        # Assemble command
        command = assemble_command(selected, "build a login endpoint")
        assert command == "/auth-jwt build a login endpoint"

    def test_multi_selection(self):
        match_results = parse_matcher_response(
            '[{"name": "auth-jwt", "score": 0.95, "match_reason": "Best"}, {"name": "api-rest", "score": 0.7, "match_reason": "Also"}]'
        )
        skills_map = {
            "auth-jwt": SkillMeta(name="auth-jwt", description="JWT auth", file_path=Path("/p1")),
            "api-rest": SkillMeta(name="api-rest", description="REST API", file_path=Path("/p2")),
        }

        # User selects both: "1,2"
        indices = parse_selection("1,2")
        assert len(indices) == 2

        commands = []
        for idx in indices:
            skill = select_skill_by_number(idx, match_results, skills_map)
            if skill:
                commands.append(assemble_command(skill, "build auth API"))

        assert len(commands) == 2
        assert "/auth-jwt build auth API" in commands
        assert "/api-rest build auth API" in commands


class TestScenarioIndexStaleness:
    """Scenario 5: Index staleness detection."""

    def test_index_stale_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        # No index file exists
        result = index_stale_or_missing()
        assert result is True

    def test_index_not_stale_when_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        # Create index file
        index_dir = plugin_data / "index"
        index_dir.mkdir()
        index_path = index_dir / "skillr_index.json"
        index_data = {
            "version": "1.0.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "skills_dirs": [],
            "skills": [],
            "source_tracking": {},
            "retrieval_window": 50,
        }
        index_path.write_text(json.dumps(index_data), encoding="utf-8")

        result = index_stale_or_missing()
        assert result is False


class TestScenarioMalformedSkills:
    """Scenario 6: Handling malformed SKILL.md files gracefully."""

    def test_skips_invalid_skills(self, malformed_skills_dir: Path):
        from skillr.scanner import scan_skills_dir

        # Should not raise, should skip bad files
        result = scan_skills_dir(malformed_skills_dir)
        # No valid skills in malformed dir
        assert len(result) == 0
