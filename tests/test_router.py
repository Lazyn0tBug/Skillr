"""Unit tests for Skillr router module."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillr.matcher import MatchResult
from skillr.models import SkillMeta
from skillr.router import (
    assemble_command,
    format_match_results_for_display,
    index_stale_or_missing,
    load_skills_or_none,
    parse_selection,
    select_skill_by_number,
)


class TestAssembleCommand:
    def test_correct_format(self):
        skill = SkillMeta(name="skill-name", description="desc", file_path=Path("/p"))
        result = assemble_command(skill, "build a REST API")
        assert result == "/skill-name build a REST API"

    def test_skill_with_hyphen(self):
        skill = SkillMeta(name="skill-scan", description="desc", file_path=Path("/p"))
        result = assemble_command(skill, "some task")
        assert result == "/skill-scan some task"


class TestParseSelection:
    def test_single_number(self):
        result = parse_selection("1")
        assert result == [1]

    def test_comma_separated(self):
        result = parse_selection("1,2,3")
        assert result == [1, 2, 3]

    def test_space_separated(self):
        result = parse_selection("1 2 3")
        assert result == [1, 2, 3]

    def test_mixed_separators(self):
        result = parse_selection("1,2 3")
        assert result == [1, 2, 3]

    def test_non_digit_filtered(self):
        result = parse_selection("1 abc 2")
        assert result == [1, 2]

    def test_empty_string(self):
        result = parse_selection("")
        assert result == []

    def test_whitespace_only(self):
        result = parse_selection("   ")
        assert result == []


class TestSelectSkillByNumber:
    def test_valid_selection(self):
        results = [
            MatchResult(name="skill1", score=0.9, match_reason="good"),
            MatchResult(name="skill2", score=0.7, match_reason="ok"),
        ]
        skills_map = {
            "skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p1")),
            "skill2": SkillMeta(name="skill2", description="desc", file_path=Path("/p2")),
        }
        result = select_skill_by_number(1, results, skills_map)
        assert result is not None
        assert result.name == "skill1"

    def test_out_of_range_low(self):
        results = [MatchResult(name="skill1", score=0.9, match_reason="good")]
        skills_map = {"skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p"))}
        result = select_skill_by_number(0, results, skills_map)
        assert result is None

    def test_out_of_range_high(self):
        results = [MatchResult(name="skill1", score=0.9, match_reason="good")]
        skills_map = {"skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p"))}
        result = select_skill_by_number(2, results, skills_map)
        assert result is None

    def test_skill_not_in_map(self):
        results = [MatchResult(name="unknown", score=0.9, match_reason="good")]
        skills_map = {"skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p"))}
        result = select_skill_by_number(1, results, skills_map)
        assert result is None


class TestFormatMatchResultsForDisplay:
    def test_empty_results(self):
        result = format_match_results_for_display([], {})
        assert "未找到匹配的 Skills" in result

    def test_non_empty_results(self):
        results = [
            MatchResult(name="skill1", score=0.9, match_reason="Matches well"),
            MatchResult(name="skill2", score=0.7, match_reason="Also good"),
        ]
        skills_map = {
            "skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p1")),
            "skill2": SkillMeta(name="skill2", description="desc", file_path=Path("/p2")),
        }
        output = format_match_results_for_display(results, skills_map)
        assert "找到 2 个匹配的 Skills" in output
        assert "/skill1" in output
        assert "/skill2" in output
        assert " Matches well" in output
        assert "Also good" in output

    def test_shows_reason(self):
        results = [MatchResult(name="skill1", score=0.9, match_reason="Exact match")]
        skills_map = {"skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p"))}
        output = format_match_results_for_display(results, skills_map)
        assert "Exact match" in output

    def test_prompt_for_selection(self):
        results = [MatchResult(name="skill1", score=0.9, match_reason="Good")]
        skills_map = {"skill1": SkillMeta(name="skill1", description="desc", file_path=Path("/p"))}
        output = format_match_results_for_display(results, skills_map)
        assert "请输入编号选择" in output


class TestIndexStaleOrMissing:
    def test_delegates_to_load_index(self, mocker):
        mocker.patch("skillr.router.load_index", return_value=None)
        result = index_stale_or_missing()
        assert result is True

    def test_returns_false_when_index_exists(self, mocker):
        mocker.patch("skillr.router.load_index", return_value="something")
        result = index_stale_or_missing()
        assert result is False


class TestLoadSkillsOrNone:
    def test_returns_none_when_no_index(self, mocker):
        mocker.patch("skillr.router.load_index", return_value=None)
        result = load_skills_or_none()
        assert result is None

    def test_returns_skills_list(self, mocker):
        mock_index = mocker.MagicMock()
        mock_index.skills = ["skill1", "skill2"]
        mocker.patch("skillr.router.load_index", return_value=mock_index)
        result = load_skills_or_none()
        assert result == ["skill1", "skill2"]