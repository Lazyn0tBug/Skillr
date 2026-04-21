---
date: 2026-04-21
topic: skillr-skill-routing-framework
---

# Skillr: Skill Routing Framework

## Problem Frame

用户在不同终端（Claude Code 等）工作时，常常面对"我有一个任务，但不知道该用哪个 Skill/命令"的问题。用户需要一种方式：输入自然语言任务 → 找到最合适的 Skills → 获得可直接执行的命令建议。

Skillr 是一个**用户终端侧的 Skills 装配层**，帮助用户在他们的终端里找到并组装正确的下一跳命令。它不替用户工作，只把正确的提示词和命令拼好交给用户。

## Requirements

**Core Commands**
- R1. `/SkillrScan` — 扫描用户配置的 Skills 目录，生成 `skillr_index.json`（机器可读）和 `SKILR_INDEX.md`（人类可读）
- R2. `/Skillr <用户任务>` — 分析用户意图，匹配可用 Skills，返回候选命令列表

**Skills Discovery**
- R3. Skills 存储在用户配置的目录（如 `~/.claude/skills` 或项目内 `skills/`），独立于 Skillr Plugin 本身
- R4. 被扫描的 Skills 每个自带 `SKILL.md`（Claude Code 标准格式），Skillr 读取其 YAML frontmatter 的 `name`、`description`、`triggers` 字段
- R5. Skillr 通过解析 `triggers` 字段做关键词匹配，通过 LLM 做意图分析和排序

**Index Management**
- R6. 安装后执行首次扫描，之后每次 `/Skillr` 调用时检查 Skills 目录 mtime，懒重建 stale 索引
- R7. 索引格式为 JSON（MVP），预留向量数据库升级路径

**Matching & Selection**
- R8. 意图分析：调用 Claude Code 内置 LLM，从用户任务中提取 `intent`、`constraints`、`keywords`
- R9. 匹配排序：关键词穷举 + LLM 排序，输出 Top 3~5 候选 Skills 与匹配理由
- R10. 用户交互：Markdown 编号列表，支持单选/多选（逗号分隔编号）

**Output**
- R11. 输出格式为纯命令字符串（如 `/ce:plan 开发一个带 JWT 的 FastAPI`），用户自行复制粘贴或回车执行
- R12. Skillr 不替代用户操作，不自己调用 Agent 工具

**Configuration**
- R13. Skills 扫描目录通过 `plugin.json` 的 `userConfig.skills_dirs` 字段声明，Claude Code 在启用插件时提示用户配置

**Technical Stack**
- R14. 实现语言：Python（MVP），使用 `uv` 管理依赖，`ty` 构建 CLI 入口，`ruff` 做 lint/format，`pyproject.toml` 管理项目配置
- R15. 宿主接口：Slash Command，作为 Claude Code Plugin 注册
- R16. LLM 调用：使用 Claude Code 内置 LLM，不引入额外 API Key 消耗

## Success Criteria

- SC1. 用户在 Claude Code 中调用 `/SkillrScan` 能成功扫描配置的 Skills 目录并生成索引
- SC2. 用户调用 `/Skillr 我想做一个用户认证系统` 能返回匹配的命令建议列表
- SC3. 用户选择编号后，Skillr 输出完整的命令字符串，用户可直接执行
- SC4. Skillr 作为 Claude Code Plugin 注册，目录结构符合 `plugin.json` + `skills/<name>/SKILL.md` 规范

## Scope Boundaries

- Skillr 本身不执行任何 Skill 命令，只做路由和建议
- Skillr 不管理 Skills 的生命周期（安装、卸载、版本更新），只读取元数据
- Skillr 不提供自己的 LLM API Key，依赖 Claude Code 内置 LLM
- Skillr Plugin 只管理自己的 Skill（`/SkillrScan`、`/Skillr`），无法直接扫描 Plugin 外部目录，但通过 `userConfig` 配置后拥有扫描权限

## Key Decisions

- **两个独立 Skill**：`/SkillrScan` 和 `/Skillr` 分别注册为独立 Skill（各自 `skills/skillrscan/SKILL.md` 和 `skills/skillr/SKILL.md`）。职责分离清晰，用户可以单独刷新索引而不触发路由。
- **用户配置扫描目录**：通过 `plugin.json` 的 `userConfig.skills_dirs` 字段声明，用户在启用插件时配置。避免硬编码路径。
- **Skill 入口文件为 SKILL.md**：被扫描的用户 Skills 使用 Claude Code 标准格式 `SKILL.md`，Skillr 读取其 YAML frontmatter 的 `name`、`description`、`triggers`。
- **输出纯命令字符串而非结构化数据**：用户习惯在终端看到完整的可执行命令，复制粘贴即用。零摩擦。
- **懒重建索引**：每次 `/Skillr` 调用时检查 mtime，必要时才重建。避免维护守护进程或依赖外部调度。
- **透传 Claude Code 内置 LLM**：Skillr 运行在 Claude Code 上下文中，直接调用宿主内置 LLM，不消耗额外 token。

## Outstanding Questions

### Deferred to Planning

- [Technical] **Python 项目结构与包管理**：确定目录布局、`pyproject.toml` 依赖声明、`uv` 工作流
- [Technical] **LLM prompt 设计**：意图分析的 prompt 模板，`triggers` 匹配 + LLM 排序的 prompt 设计
- [Technical] **Skillr Plugin 与用户 Skills 的文件路径解析**：用户目录（`~/.claude/skills`）路径展开与权限处理
- [Technical] **索引存储位置**：`skillr_index.json` 和 `SKILR_INDEX.md` 存放在 plugin data 目录（`${CLAUDE_PLUGIN_DATA}`）还是用户工作目录

## Next Steps

-> `/ce:plan` for structured implementation planning
