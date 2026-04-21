"""Unit tests for Skillr router module."""

from __future__ import annotations

from pathlib import Path

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

    def test_non_slash_command_format(self):
        """Skills without slash command use '使用 <name> skill' format."""
        skill = SkillMeta(
            name="hermes",
            description="Hermes agent",
            file_path=Path("/p"),
            has_slash_command=False,
        )
        result = assemble_command(skill, "画一张架构图")
        assert result == "使用 hermes skill 画一张架构图"

    def test_name_whitespace_stripped(self):
        skill = SkillMeta(name=" skill ", description="desc", file_path=Path("/p"))
        result = assemble_command(skill, "some task")
        assert result == "/skill some task"


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
        assert "Matches well" in output
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


class TestFormatMatchResultsPagination:
    """Test batch pagination in format_match_results_for_display."""

    def _make_results(self, count: int) -> list[MatchResult]:
        return [
            MatchResult(name=f"skill{i}", score=0.9, match_reason=f"Reason {i}")
            for i in range(1, count + 1)
        ]

    def _make_map(self, count: int) -> dict[str, SkillMeta]:
        return {
            f"skill{i}": SkillMeta(name=f"skill{i}", description="desc", file_path=Path(f"/p{i}"))
            for i in range(1, count + 1)
        }

    def test_batch1_shows_pagination_next(self):
        """Batch 1 with more results shows '换下一批'."""
        results = self._make_results(6)
        skills_map = self._make_map(6)
        output = format_match_results_for_display(results, skills_map, batch_num=1)
        assert "找到 4 个匹配的 Skills" in output
        assert "n. 换下一批" in output
        assert "1." in output
        assert "4." in output
        assert "5." not in output

    def test_batch2_shows_pagination_next(self):
        """Batch 2 with more results shows '换下一批'."""
        results = self._make_results(9)  # 9 items = 3 batches (4, 4, 1)
        skills_map = self._make_map(9)
        output = format_match_results_for_display(results, skills_map, batch_num=2)
        assert "还有 5 个匹配的 Skills" in output  # 9 - 4 = 5 remaining
        assert "n. 换下一批" in output
        assert "5." in output
        assert "8." in output

    def test_batch3_final_shows_no_more(self):
        """Batch 3 (final) shows '没有了' instead of pagination."""
        results = self._make_results(11)
        skills_map = self._make_map(11)
        output = format_match_results_for_display(results, skills_map, batch_num=3)
        assert "n. 没有了" in output
        assert "没有了（放弃，会话结束）" in output

    def test_single_batch_allows_selection(self):
        """With only 3 results and batch_size=4, single batch shows no pagination."""
        results = self._make_results(3)
        skills_map = self._make_map(3)
        output = format_match_results_for_display(results, skills_map, batch_num=1)
        assert "找到 3 个匹配的 Skills" in output
        assert "n. 没有了" in output

    def test_batch_size_respected(self):
        """Each batch shows at most batch_size results."""
        results = self._make_results(12)
        skills_map = self._make_map(12)
        # Batch 1
        output1 = format_match_results_for_display(results, skills_map, batch_num=1)
        assert "/skill1" in output1
        assert "/skill4" in output1
        assert "/skill5" not in output1
        # Batch 2
        output2 = format_match_results_for_display(results, skills_map, batch_num=2)
        assert "/skill5" in output2
        assert "/skill8" in output2
        assert "/skill9" not in output2
        # Batch 3
        output3 = format_match_results_for_display(results, skills_map, batch_num=3)
        assert "/skill9" in output3
        assert "/skill12" in output3


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

    def test_returns_empty_list_when_index_empty(self, mocker):
        """Index exists but has 0 skills → empty list (not None)."""
        mock_index = mocker.MagicMock()
        mock_index.skills = []
        mocker.patch("skillr.router.load_index", return_value=mock_index)
        result = load_skills_or_none()
        assert result == []


class TestColdStartGuidance:
    def test_cold_start_guidance_contains_skill_instructions(self):
        """Cold start guidance shows skill setup instructions."""
        from skillr.router import format_cold_start_guidance

        result = format_cold_start_guidance()
        assert "未找到匹配的 Skills" in result
        assert "~/.claude/skills/" in result
        assert "/skillscan" in result

    def test_empty_skills_shows_cold_start_guidance(self):
        """Empty skills_map with empty results shows cold start, not generic no-match."""
        from skillr.router import format_match_results_for_display

        result = format_match_results_for_display([], {})
        assert "未找到匹配的 Skills" in result
        assert "还没有配置任何 Skills" in result
        assert "SKILL.md" in result
