---
title: "feat: Implement Skillr Skill Routing Framework"
type: feat
status: implemented
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-skilr-skill-routing-framework-requirements.md
---

# Skillr Skill Routing Framework

## Overview

Skillr 是一个 Claude Code Plugin，帮助用户在终端里找到最合适的 Skill 并组装可执行的命令建议。它不替用户工作，只做路由和提示词拼装。

实现分 4 个阶段：项目结构、扫描器、路由器、文档输出。

## Problem Frame

用户在不同终端工作时，常面对"我有一个任务，但不知道该用哪个 Skill/命令"的问题。Skillr 输入自然语言任务 → 找到最合适的 Skills → 输出可直接执行的命令建议。

## Requirements Trace

- R1. `/SkilrScan` — 扫描 Skills 目录，生成索引
- R2. `/Skilr <task>` — 意图分析 + 匹配 + 选择，输出候选命令
- R3. Skills 存储在用户配置目录（`~/.claude/skills` 等）
- R4. Skills 使用标准 `SKILL.md` 格式
- R5. 关键词 + LLM 意图分析
- R6. 懒重建索引（mtime 检查）
- R7. 索引格式 JSON（MVP）
- R8. 调用 Claude Code 内置 LLM（透传）
- R9. Top 3~5 候选 + 匹配理由
- R10. 用户 Markdown 编号选择
- R11. 输出纯命令字符串（可复制粘贴执行）
- R12. Skillr 不替代用户操作，不自己调用 Agent 工具
- R13. Python + uv + ty + ruff + pyproject.toml
- R14. Slash Command 注册

## Scope Boundaries

- Skillr 不执行 Skill 命令，只做路由
- Skillr 不管理 Skills 生命周期，只读元数据
- Skillr 不提供独立 LLM API Key

## Key Technical Decisions

- **LLM 调用方式**：Skillr 作为 Markdown Skill，SKILL.md 描述工作流，LLM 分析在主会话中完成（不派遣 sub-agent）；CE 的核心是 SKILL.md 作为技能入口，不是 sub-agent 嵌套
- **索引存储位置**：`${CLAUDE_PLUGIN_DATA}/index/` — plugin data 目录随插件安装存在，跨版本持久化
- **用户目录路径展开**：Python `pathlib.Path.expanduser()` 处理 `~`，通过 `userConfig.skills_dirs` 配置
- **Skill 扫描方式**：遍历配置的目录，读取每个子目录下的 `SKILL.md`，解析 YAML frontmatter 的 `name`、`description`
- **No independent triggers field**：不单独提取 triggers 字段，直接用 `description` 全文供 LLM 匹配（description 已包含触发条件语义）
- **JSON-only index**：R7 规定 JSON 格式；SKILR_INDEX.md（Markdown）不在 MVP 范围内，预留至向量数据库版本
- **mtime 追踪策略（Tiered）**：优先 git-aware（`git ls-files`），非 git 目录用 per-file mtime，文件不存在时降级到父目录 mtime
- **检索窗口**：索引不设数量限制；LLM 匹配时可设置 `retrieval_window` 窗口（Top K）避免 context overflow
- **命令输出（简化 MVP）**：所有 Skills 输出 `/<name> <intent>`，bifurcation 逻辑推迟至后续版本

## Open Questions

### Resolved During Planning

- **LLM 调用机制**：采用 CE 模式 — Markdown Skill 描述工作流，LLM 分析在主会话中完成。SDK 文档明确：sub-agent 不能嵌套（sub-agent 的 tools 中不能包含 Agent），因此不做 sub-agent 派遣
- **mtime 追踪策略**：git-aware > per-file mtime > per-dir mtime，分级降级。git-aware 用 `git ls-files` 检测变更，适合项目内 skills 目录；per-file 适合独立用户目录
- **索引存储位置**：使用 `${CLAUDE_PLUGIN_DATA}/index/`（plugin data 目录），避免污染用户工作目录
- **Python 项目结构**：`src/skilr/` 作为源码根目录，`pyproject.toml` 在插件根目录
- **userConfig.skills_dirs 类型**：应为对象 `{description: string, sensitive: boolean}`，不是 string array

### Deferred to Implementation

- **LLM prompt 细节**：意图分析的 prompt 模板、排序 prompt 模板，待实际使用中调优
- **向量数据库升级路径**：当前 MVP 用 JSON + 关键词匹配，预留但不实现
- **SKILR_INDEX.md**：R1 原本要求生成 Markdown 格式索引，MVP 仅生成 JSON，Markdown 版本在向量数据库升级时一并实现
- **命令 bifurcation**：slash command / 非 slash command 输出格式分化，在 MVP 后实现

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
用户调用 /Skilr <task>
    │
    ▼
Skillr SKILL.md 描述工作流
    │  LLM 分析在主会话中完成（SKILL.md 驱动，不派遣 sub-agent）
    ▼
加载索引（skilr_index.json）
    │  检查 mtime（git-aware / per-file / per-dir 分级），必要时懒重建
    ▼
关键词过滤 + LLM 意图分析与排序
    │  → Top 3~5 候选 + 匹配理由
    ▼
Markdown 编号列表输出
    │  用户选择编号
    ▼
/<name> <intent>
    ▼
输出给用户
```

**SkillrScan 流程：**

```
用户调用 /SkilrScan
    │
    ▼
遍历 skills_dirs 配置的目录
    │
    ▼
读取每个子目录的 SKILL.md
    │  解析 YAML frontmatter
    ▼
生成索引文件
    │  skilr_index.json (机器可读)
    ▼
保存到 ${CLAUDE_PLUGIN_DATA}/index/
    │
    ▼
输出扫描结果摘要
```

## Implementation Units

- [x] **Unit 1: Project Foundation**

**Goal:** 建立 Skillr Plugin 的基础项目结构

**Requirements:** R14

**Dependencies:** None

**Files:**
- Create: `pyproject.toml` — uv + ty + ruff 配置
- Create: `src/skilr/__init__.py` — 包初始化
- Create: `src/skilr/py.typed` — PEP 561 类型标记
- Create: `.claude-plugin/plugin.json` — 插件清单，`userConfig.skills_dirs` 声明
- Create: `skills/skilrscan/SKILL.md` — /SkilrScan 入口（Markdown Skill）
- Create: `skills/skilr/SKILL.md` — /Skilr 入口（Markdown Skill）

**Approach:**
- Skillr 完全作为 Markdown Skill 实现，不自己调 LLM，通过 Task 工具派遣 sub-agent
- pyproject.toml 声明 uv 作为打包工具，ty 作为 CLI 构建入口，ruff 作为 lint/format
- plugin.json 的 `userConfig.skills_dirs` 声明为对象 `{description: string, sensitive: boolean}`，Claude Code 启用时提示用户配置
- SKILL.md 使用 YAML frontmatter（name、description），内容描述工作流

**Execution note:** 无特殊执行姿势

**Technical design:** N/A

**Patterns to follow:**
- 参考 compound-engineering 的 `skills/ce-brainstorm/SKILL.md` 格式（纯 Markdown Skill）
- Python 包结构参考标准 modern Python layout

**Test scenarios:**
- Happy path: Plugin 加载成功，skills/ 目录下的两个 Skill 被正确注册
- Edge case: skills_dirs 未配置时提示用户配置
- Error path: 插件加载失败时 Claude Code 报错

**Verification:**
- `claude --debug` 输出显示 "loading plugin skilr" 且两个 Skill 注册成功

---

- [x] **Unit 2: Skill Scanner**

**Goal:** 实现 /SkilrScan 的核心逻辑：遍历目录、读取 SKILL.md、生成索引

**Requirements:** R1, R3, R4, R6, R7

**Dependencies:** Unit 1

**Files:**
- Create: `src/skilr/scanner.py` — 目录扫描和 YAML 解析
- Create: `src/skilr/indexer.py` — 索引生成逻辑
- Create: `src/skilr/models.py` — Pydantic 数据模型（SkillMeta, SkilrIndex）
- Create: `src/skilr/config.py` — 配置读取，skills_dirs 从 userConfig 获取

**Approach:**
- scanner.py 用 pathlib 遍历配置的目录，对每个子目录检查 SKILL.md 是否存在
- SKILL.md 解析：读取文件内容，用 `---` 分隔 YAML frontmatter 和正文，frontmatter 解析出 name、description
- indexer.py 生成 `skilr_index.json`（JSON-only；不生成 SKILR_INDEX.md）
- mtime 懒重建：采用分级策略检测变更
  - **Tier 1 (git-aware)**：若 skills_dir 是 git 仓库，用 `git ls-files --others --modified` 与已存储的 commit hash 对比
  - **Tier 2 (per-file)**：非 git 目录，记录每个 SKILL.md 的 mtime，有文件 mtime 变化则重建
  - **Tier 3 (per-dir)**：文件不存在时，降级到父目录 mtime 作为兜底
- **注意**：不生成 SKILR_INDEX.md，R7 只要求 JSON 格式

**Execution note:** 无特殊执行姿势

**Technical design:**

```python
class SkillMeta(BaseModel):
    name: str           # from SKILL.md frontmatter name (slash command = /<name>)
    description: str    # from SKILL.md frontmatter description (全文用于 LLM 匹配)
    file_path: str      # absolute path to the SKILL.md
    # 不需要独立的 triggers 字段 — description 本身包含触发条件语义

class SkilrIndex(BaseModel):
    version: str
    generated_at: str
    skills_dirs: list[str]
    skills: list[SkillMeta]
    # mtime 追踪：dict[file_path, {git_hash}] 或 dict[file_path, {mtime}]
    # git-aware 目录存 git commit hash，非 git 目录存 mtime
    source_tracking: dict[str, dict]  # dir_path -> {"type": "git"|"mtime", "value": str|float}
    retrieval_window: int = 50        # LLM 匹配窗口大小，避免 context overflow
```

**Patterns to follow:**
- YAML frontmatter 解析参考 PyYAML 的 safe_load
- Pydantic v2 for 数据验证

**Test scenarios:**
- Happy path: skills_dir 下有 3 个 Skill 子目录，扫描生成完整索引
- Edge case: 子目录下没有 SKILL.md（跳过）
- Edge case: SKILL.md 的 YAML frontmatter 格式错误（记录警告，跳过该 Skill）
- Edge case: skills_dir 配置的目录不存在（提示警告，跳过）
- Error path: 目录无读取权限

**Verification:**
- /SkilrScan 输出 "✅ 扫描完成，共发现 N 个 Skills"
- `skilr_index.json` 可被 JSON 解析且字段完整

---

- [x] **Unit 3: Skill Router**

**Goal:** 实现 /Skilr 的核心逻辑：加载索引、意图分析、匹配排序、用户选择、输出命令

**Requirements:** R2, R5, R8, R9, R10, R11, R12

**Dependencies:** Unit 2

**Files:**
- Create: `src/skilr/router.py` — 主流程：加载索引、调用 intent/matcher 组件
- Create: `src/skilr/intent.py` — 意图提取 prompt 模板（SKILL.md 主会话驱动 LLM 时使用）
- Create: `src/skilr/matcher.py` — 关键词过滤 + 排序 prompt 模板（SKILL.md 主会话驱动 LLM 时使用）

**Approach:**
- Skillr SKILL.md 描述工作流，主会话（SKILL.md 驱动）执行 LLM 分析，不派遣 sub-agent
- SKILL.md 中引用 intent.py 的 prompt 模板，主会话 LLM 根据模板生成 IntentSpec
- SKILL.md 中引用 matcher.py 的过滤/排序逻辑，主会话 LLM 完成匹配排序
- 用户选择：Markdown 编号列表，用户输入编号后组装输出

**命令组装（简化 MVP）：**

```
MVP:       /<name> <intent>
bifurcation 逻辑推迟至后续版本
```

**Technical design:**

```python
# === intent.py — 主会话 LLM 调用 ===

class IntentSpec(BaseModel):
    """用户任务经过 LLM 分析后的结构化意图"""
    original_task: str     # 用户原始输入
    intent: str             # 精化后的意图描述
    constraints: list[str] # 约束条件
    keywords: list[str]    # 提取的关键词（用于过滤）

INTENT_PROMPT_TEMPLATE: str = """
用户任务：{user_task}

分析用户任务，提取：
1. intent：精化后的意图描述（1-2句话）
2. constraints：约束条件列表（如有）
3. keywords：关键词列表（3-5个，用于初步过滤）

输出格式（JSON）：
{{"intent": "...", "constraints": [...], "keywords": [...]}}
"""

def build_intent_prompt(user_task: str) -> str:
    """生成意图提取 prompt，供主会话 LLM 使用"""
    return INTENT_PROMPT_TEMPLATE.format(user_task=user_task)


# === matcher.py — 主会话 LLM 调用 ===

class MatchResult(BaseModel):
    skill: SkillMeta
    score: float       # 0.0–1.0
    match_reason: str   # 为什么这个 skill 匹配

FILTER_AND_RANK_PROMPT_TEMPLATE: str = """
候选 Skills（JSON）：
{skills_json}

用户意图：{intent}
关键词：{keywords}

任务：
1. 过滤：排除明显不相关的 Skills（关键词完全不匹配）
2. 排序：对余下 Skills 按匹配度排序，输出 Top {top_k}
3. 对每个候选：给出 match_reason（1句话）

输出格式（JSON数组）：
[{{"name": "...", "score": 0.x, "match_reason": "..."}}]
"""

def build_matcher_prompt(
    skills: list[SkillMeta],
    intent: str,
    keywords: list[str],
    top_k: int = 5
) -> str:
    """生成过滤排序 prompt，供主会话 LLM 使用"""
    skills_json = json.dumps([s.model_dump() for s in skills], ensure_ascii=False)
    return FILTER_AND_RANK_PROMPT_TEMPLATE.format(
        skills_json=skills_json,
        intent=intent,
        keywords=", ".join(keywords),
        top_k=top_k
    )

def keyword_filter(skills: list[SkillMeta], keywords: list[str]) -> list[SkillMeta]:
    """基于关键词的初步过滤（主会话本地执行，不需要 LLM）"""
    ...

# === router.py — 主流程 ===

def assemble_command(skill: SkillMeta, intent: str) -> str:
    """MVP: 所有 Skills 输出 /<name> <intent>"""
    return f"/{skill.name} {intent}"
```

**Patterns to follow:**
- CE 的 Markdown Skill 驱动主会话 LLM（SKILL.md 作为工作流描述，不派遣 sub-agent）
- prompt 模板由 intent.py / matcher.py 提供，主会话 LLM 按模板生成结构化输出
- SDK 文档明确 sub-agent 不能嵌套，不做 sub-agent 派遣

**Test scenarios:**
- Happy path: 用户输入 "我想做一个用户认证系统"，返回匹配的 skill 列表
- Edge case: 没有任何 skill 匹配（输出 "未找到匹配的 Skills，建议先运行 /SkilrScan"）
- Edge case: 用户输入 "1,2" 多选（正常处理）
- Edge case: 用户输入非法编号（提示重新输入）
- Error path: 索引文件不存在（提示先运行 /SkilrScan）

**Verification:**
- /Skilr 返回的 Markdown 列表格式正确
- 输出的命令字符串可被用户直接复制粘贴执行

---

- [x] **Unit 4: Output Artifacts**

**Goal:** 生成 CHANGELOG.md、TODO.md、Session.md 三个文档

**Requirements:** N/A（项目管理和进度追踪）

**Dependencies:** None（跨项目独立）

**Files:**
- Create: `CHANGELOG.md` — 变更日志
- Create: `TODO.md` — 未来工作目标
- Create: `Session.md` — 工作明细和实施状态

**Approach:**
- CHANGELOG.md：按时间倒序记录每次重要变更（版本号、日期、变更内容）
- TODO.md：记录已知问题、待优化项、未来功能
- Session.md：记录本次会话的所有工作内容、决策点、实施状态

**Test scenarios:**
- Test expectation: none — 纯文档生成

**Verification:**
- 三个文档存在且格式正确
- Session.md 包含本次规划的所有关键决策

---

## System-Wide Impact

- **Interaction graph:** Skillr 作为 Markdown Skill 运行，SKILL.md 描述工作流，主会话 LLM 完成意图分析和排序（不做 sub-agent 派遣）
- **Error propagation:** 文件读取错误、YAML 解析错误、LLM 输出解析错误均输出友好提示，不崩溃
- **State lifecycle risks:** 索引文件可能与实际 Skills 目录不同步（通过 git-aware / per-file mtime 检测）
- **Integration coverage:** 跨 Claude Code 会话不保持状态，每次需要重新加载索引

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| YAML frontmatter 解析错误 | 跳过该 Skill，记录警告，不中断扫描 |
| skills_dirs 配置无效 | 检测目录存在性，不存在时提示用户 |
| LLM 输出解析失败 | 降级为纯关键词匹配，保证基本可用 |
| 索引过期 | mtime 分级懒重建机制，每次路由前检查 |
| 用户 Skills 分散在不同目录 | userConfig 支持多目录配置 |
| git-aware 在非 git 目录失效 | 降级到 per-file mtime，per-file 失效再降级到 per-dir |

## Documentation / Operational Notes

- 插件根目录的 `docs/` 存放规划文档，`CHANGELOG.md`、`TODO.md`、`Session.md` 在插件根目录
- `docs/plans/` 存放实现计划
- `docs/brainstorms/` 存放需求文档

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-skilr-skill-routing-framework-requirements.md](../brainstorms/2026-04-21-skilr-skill-routing-framework-requirements.md)
- **Agent SDK Docs:** `docs/references/agentsdk_overview.md`, `agentsdk_subagent.md`, `agentsdk_skill.md`, `agentsdk_plugin.md`, `agentsdk_slash_command.md`
- **CE Pattern Reference:** compound-engineering plugin 的 skills/ 结构（Markdown Skill 驱动主会话 LLM）
- **SDK 文档关键约束**：sub-agent 的 tools 数组中不能包含 Agent（即 sub-agent 不能嵌套派遣）
