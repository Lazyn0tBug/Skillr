"""Intent extraction — prompt templates for LLM-driven intent analysis.

The main session LLM uses these templates to produce an IntentSpec from the user's task.
These are NOT sub-agent dispatch functions — they generate prompt strings.
"""

from __future__ import annotations

from .models import IntentSpec


INTENT_PROMPT_TEMPLATE = """
用户任务：{user_task}

分析用户任务，提取：
1. intent：精化后的意图描述（1-2句话）
2. constraints：约束条件列表（如有；没有则返回空列表）
3. keywords：关键词列表（3-5个，用于初步过滤候选 Skills）

输出格式（JSON，不要加 markdown 标记）：
{{"intent": "...", "constraints": [...], "keywords": [...]}}
"""


def build_intent_prompt(user_task: str) -> str:
    """Generate the intent extraction prompt for the main session LLM."""
    return INTENT_PROMPT_TEMPLATE.format(user_task=user_task)


def parse_intent_response(response_text: str) -> IntentSpec | None:
    """Parse the LLM's JSON response into an IntentSpec.

    Attempts to extract JSON from the response text.
    Returns None if parsing fails.
    """
    import json
    import re

    # Try to find JSON block in the response
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None

    # Validate required fields
    if not isinstance(data.get("intent"), str):
        return None
    if not isinstance(data.get("keywords"), list):
        return None

    return IntentSpec(
        original_task=user_task,
        intent=data["intent"],
        constraints=data.get("constraints", []),
        keywords=data.get("keywords", []),
    )
