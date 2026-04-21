"""Skill router — main workflow: load index, filter, rank, assemble command."""

from __future__ import annotations

from .indexer import load_index
from .intent import build_intent_prompt, parse_intent_response
from .matcher import build_matcher_prompt, keyword_filter, parse_matcher_response
from .models import IntentSpec, MatchResult, SkillMeta


def assemble_command(skill: SkillMeta, intent: str) -> str:
    """Assemble the executable command for a matched skill (MVP: all /<name> <intent>)."""
    return f"/{skill.name} {intent}"


def select_skill_by_number(
    selected_number: int,
    match_results: list[MatchResult],
    skills_map: dict[str, SkillMeta],
) -> SkillMeta | None:
    """Return the SkillMeta for a given 1-based selection number."""
    if selected_number < 1 or selected_number > len(match_results):
        return None
    match = match_results[selected_number - 1]
    return skills_map.get(match.name)


def parse_selection(selection: str) -> list[int]:
    """Parse a user selection string like '1' or '1,2' into a list of 1-based indices."""
    parts = selection.replace(",", " ").split()
    indices = []
    for p in parts:
        p = p.strip()
        if p.isdigit():
            indices.append(int(p))
    return indices


# === Exposed workflow functions (called from SKILL.md workflow) ===

def build_intent_prompt_for_task(user_task: str) -> str:
    """Build the LLM prompt for extracting intent from a user task."""
    return build_intent_prompt(user_task)


def build_matcher_prompt_for_intent(
    skills: list[SkillMeta],
    intent: IntentSpec,
    top_k: int = 5,
) -> str:
    """Build the LLM prompt for filtering and ranking skills against an intent."""
    return build_matcher_prompt(skills, intent, top_k)


def load_skills_or_none() -> list[SkillMeta] | None:
    """Load all skills from the index, or None if no index exists."""
    index = load_index()
    if index is None:
        return None
    return index.skills


def format_match_results_for_display(
    match_results: list[MatchResult],
    skills_map: dict[str, SkillMeta],
) -> str:
    """Format match results as a Markdown numbered list for user selection."""
    if not match_results:
        return "未找到匹配的 Skills。"

    n = len(match_results)
    lines = [f"找到 {n} 个匹配的 Skills：", ""]
    for i, result in enumerate(match_results, 1):
        skill = skills_map.get(result.name)
        skill_name = skill.name if skill else result.name
        lines.append(f"{i}. `/{skill_name}` — 理由: {result.match_reason}")

    lines.append("")
    lines.append("请输入编号选择（支持多选，用逗号分隔，如 1,2）：")

    return "\n".join(lines)


def index_stale_or_missing() -> bool:
    """Return True if the index is missing or should be considered stale."""
    return load_index() is None
