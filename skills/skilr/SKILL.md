---
name: Skilr
description: "Analyze a natural-language task, find the best-matching Skills, and output an executable command suggestion. Use when you know what you want to do but are unsure which Skill to use, or when you want a refined command suggestion."
argument-hint: "[your task or goal in natural language]"
---

# Skilr — Route Tasks to the Right Skill

Skillr helps you find the right Skill and assemble executable command suggestions. It does **not** execute commands for you — it outputs a command string for you to copy and run.

## Usage

```
/Skilr <your task in natural language>
```

Example:
```
/Skilr 我想做一个用户认证系统
/Skilr我想做一个fastapi项目
```

## Workflow

1. **Load Index** — Skillr loads `skilr_index.json` from `${CLAUDE_PLUGIN_DATA}/index/`. If the index is stale (detected via tiered mtime), it prompts you to run `/SkilrScan` first.

2. **Intent Analysis** — Using the LLM (main session), Skillr analyzes your task and extracts:
   - `intent`: refined intent description
   - `constraints`: any constraints you mentioned
   - `keywords`: 3-5 keywords for initial filtering

3. **Keyword Filter** — Skillr filters the Skill list to candidates matching your keywords (local operation, no LLM).

4. **LLM Ranking** — With the filtered candidates, the LLM ranks them by relevance and returns the top 3-5 matches with match reasons.

5. **Selection** — Skillr presents results as a numbered Markdown list:

   ```
   找到 3 个匹配的 Skills：

   1. `/ce:plan` — 理由: 专门用于规划实现方案，适合"做一个认证系统"这种需要设计的任务
   2. `/fastapi-gen` — 理由: 生成 FastAPI 项目结构，可用于快速初始化
   3. `/auth-templates` — 理由: 提供认证相关的模板代码

   请输入编号选择（支持多选，用逗号分隔，如 1,2）：
   ```

6. **Command Output** — After you select, Skillr outputs:

   ```
   /ce:plan 开发一个带 JWT 的 FastAPI 用户认证系统
   ```

   You can copy and run this command directly.

## Output Format (MVP)

All Skills output as `/<name> <intent>` in MVP. Future versions will support:
- `/<name> refine(<intent>)` for skills with subcommand support
- `我想用 <skill_name> skill <intent>` for skills without slash commands

## Index Not Found

If `skilr_index.json` does not exist:

```
❌ 未找到索引文件。请先运行 /SkilrScan 扫描 Skills 目录。
```

## No Matches

If no Skills match your task:

```
未找到匹配的 Skills。
建议：
1. 确认 Skills 目录配置正确（检查 plugin.json 中的 skills_dirs）
2. 运行 /SkilrScan 重新扫描
3. 如果刚添加新 Skill，请先运行 /SkilrScan
```

## Edge Cases

- **Multiple selection**: Enter numbers separated by commas (e.g., `1,2`) to get multiple command suggestions
- **Invalid number**: Skillr will ask you to re-enter
- **Empty input**: Skillr will ask you to provide a task
