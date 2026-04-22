"""Skill matching — prompt templates and logic for filtering and ranking Skills.

The main session LLM uses these templates to rank Skills against the user's intent.
keyword_filter() is a local operation (no LLM).
"""

from __future__ import annotations

import json
import re

from .models import IntentSpec, MatchResult, SkillMeta

FILTER_AND_RANK_PROMPT_TEMPLATE = """
候选 Skills（JSON 数组）：
{skills_json}

{history_context}

用户意图：{intent}
约束条件：{constraints}
关键词：{keywords}

任务：
1. 过滤：排除明显不相关的 Skills（关键词完全不匹配）
2. 排序：对余下 Skills 按匹配度排序，输出 Top {top_k}
3. 对每个候选：给出 match_reason（1句话，说明为什么这个 Skill 适合用户的意图）

输出格式（JSON 数组，不要加 markdown 标记）：
[{{"name": "...", "score": 0.x, "match_reason": "..."}}]
"""


def build_matcher_prompt(
    skills: list[SkillMeta],
    intent: IntentSpec,
    top_k: int = 5,
    history_context: str = "",
) -> str:
    """Generate the filter + rank prompt for the main session LLM."""
    skills_json = json.dumps(
        [{"name": s.name, "description": s.description} for s in skills],
        ensure_ascii=False,
    )
    if history_context:
        history_context = f"\n{history_context}\n"
    return FILTER_AND_RANK_PROMPT_TEMPLATE.format(
        skills_json=skills_json,
        history_context=history_context,
        intent=intent.intent,
        constraints=", ".join(intent.constraints) if intent.constraints else "无",
        keywords=", ".join(intent.keywords),
        top_k=top_k,
    )


def keyword_filter(skills: list[SkillMeta], keywords: list[str]) -> list[SkillMeta]:
    """Filter skills by keyword presence in name or description (local, no LLM).

    Returns skills where at least one keyword appears in the name or description.
    Case-insensitive matching.
    """
    if not keywords:
        return skills

    lower_keywords = [k.lower() for k in keywords]
    matched: list[SkillMeta] = []

    for skill in skills:
        text = f"{skill.name} {skill.description}".lower()
        if any(kw in text for kw in lower_keywords):
            matched.append(skill)

    return matched


def parse_matcher_response(response_text: str) -> list[MatchResult] | None:
    """Parse the LLM's JSON response into a list of MatchResult.

    Returns None if parsing fails.
    """
    # Try to find JSON array in the response (non-greedy)
    json_match = re.search(r"\[[\s\S]*?\]", response_text)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list):
        return None

    results: list[MatchResult] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        score = item.get("score")
        reason = item.get("match_reason")

        if not name or not isinstance(score, (int, float)) or not reason:
            continue

        results.append(
            MatchResult(
                name=str(name),
                score=float(score),
                match_reason=str(reason),
            )
        )

    return results
