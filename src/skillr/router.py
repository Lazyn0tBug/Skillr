"""Skill router — main workflow: load index, filter, rank, assemble command."""

from __future__ import annotations

from .cache import IntentCacheStore
from .indexer import load_index
from .intent import build_intent_prompt
from .matcher import build_matcher_prompt
from .models import IntentSpec, MatchResult, SkillMeta


def assemble_command(skill: SkillMeta, intent: str) -> str:
    """Assemble the executable command for a matched skill.

    Format depends on whether the skill has a registered slash command:
    - With slash command: /<name> <intent>
    - Without slash command: 使用 <name> skill <intent>
    """
    name = skill.name.strip()
    intent_text = intent.strip()
    if skill.has_slash_command:
        return f"/{name} {intent_text}"
    else:
        return f"使用 {name} skill {intent_text}"


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
    batch_num: int = 1,
    batch_size: int = 4,
) -> str:
    """Format match results as a Markdown numbered list for user selection with pagination.

    Args:
        match_results: All matched results from LLM ranking
        skills_map: Map of skill name to SkillMeta for looking up skill details
        batch_num: Current batch number (1, 2, or 3), affects numbering and pagination prompt
        batch_size: Number of results per batch (default 4)
    """
    if not match_results:
        if not skills_map:
            return format_cold_start_guidance()
        return "未找到匹配的 Skills。"

    total = len(match_results)
    total_batches = min(3, (total + batch_size - 1) // batch_size)

    # Calculate which slice of results to show for this batch
    start_idx = (batch_num - 1) * batch_size
    end_idx = min(start_idx + batch_size, total)
    batch_results = match_results[start_idx:end_idx]

    if batch_num == 1:
        lines = [f"找到 {min(batch_size, total)} 个匹配的 Skills：", ""]
    else:
        remaining = total - start_idx
        lines = [f"还有 {remaining} 个匹配的 Skills：", ""]

    # Number consecutively across all batches
    for i, result in enumerate(batch_results, start=start_idx + 1):
        skill = skills_map.get(result.name)
        skill_name = skill.name if skill else result.name
        lines.append(f"{i}. `/{skill_name}` — 理由: {result.match_reason}")

    lines.append("")

    # Pagination prompt based on batch
    if batch_num < total_batches:
        lines.append("n. 换下一批")
    else:
        lines.append("n. 没有了（放弃，会话结束）")

    lines.append("")
    lines.append("请输入编号选择：")

    return "\n".join(lines)


def format_cold_start_guidance() -> str:
    """Return guidance for users who have no skills configured."""
    return """未找到匹配的 Skills。

看起来你还没有配置任何 Skills。要开始使用 Skillr：

1. 在 ~/.claude/skills/ 目录下创建你的第一个 Skill
2. 每个 Skill 需要一个 SKILL.md 文件（包含 name 和 description）
3. 运行 /skillscan 扫描后重新使用 /skillr

查看文档：https://docs.claude.com/skills"""


def index_stale_or_missing() -> bool:
    """Return True if the index is missing or should be considered stale."""
    return load_index() is None


# === Cache-aware routing (E1) ===

_cache_store: IntentCacheStore | None = None


def _get_cache_store() -> IntentCacheStore:
    """Lazily initialize the cache store."""
    global _cache_store
    if _cache_store is None:
        _cache_store = IntentCacheStore()
    return _cache_store


def route_intent_cached(
    user_task: str,
    skills: list[SkillMeta],
) -> list[MatchResult] | None:
    """Route intent with caching: check cache first, fall back to LLM ranking.

    Returns:
        list[MatchResult]: cached match results on cache hit
        None: on cache miss (caller should invoke LLM ranking)

    The caller can distinguish three cases:
        - []             → LLM ran but found no matches
        - None          → cache miss, LLM not yet called
        - [MatchResult]  → cache hit
    """
    if not skills:
        return []

    # Step 1: Compute intent hash
    # NOTE: In SKILL.md, the main session LLM generates intent_prompt response.
    # parse_intent_response is called by SKILL.md after receiving the LLM response.
    # For caching, we compute intent_hash from user_task directly (not from parsed intent
    # since the LLM call happens externally in SKILL.md).
    intent_hash = IntentCacheStore.hash_intent(user_task)
    skill_ids = [s.name for s in skills]
    skill_ids_hash = IntentCacheStore.hash_skill_ids(skill_ids)

    # Step 2: Check cache
    store = _get_cache_store()
    cached = store.get(intent_hash, skill_ids_hash)
    if cached is not None:
        return cached

    # Cache miss — return None to signal caller should invoke LLM ranking.
    return None


def cache_match_results(
    user_task: str,
    skills: list[SkillMeta],
    match_results: list[MatchResult],
) -> None:
    """Store match results in the intent cache.

    Called from SKILL.md after a successful LLM ranking.
    """
    if not skills or not match_results:
        return

    intent_hash = IntentCacheStore.hash_intent(user_task)
    skill_ids = [s.name for s in skills]
    skill_ids_hash = IntentCacheStore.hash_skill_ids(skill_ids)

    store = _get_cache_store()
    store.set(intent_hash, skill_ids_hash, match_results)
