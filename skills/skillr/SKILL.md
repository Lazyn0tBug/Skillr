---
name: skillr
description: "Analyze a natural-language task, find the best-matching skills, and output an executable command suggestion. Use when you know what you want to do but are unsure which skill to use, or when you want a refined command suggestion."
argument-hint: "[your task or goal in natural language]"
---

# skillr — Route Tasks to the Right Skill

skillr helps you find the right skill and assemble executable command suggestions. It does **not** execute commands for you — it outputs a command string for you to copy and run.

## Usage

```
/skillr <your task in natural language>
```

Example:
```
/skillr 我想做一个用户认证系统
/skillr我想做一个fastapi项目
```

## Workflow

1. **Load Index** — skillr loads `skillr_index.json` from `${CLAUDE_PLUGIN_DATA}/index/`. If the index is stale (detected via tiered mtime), it prompts you to run `/skillscan` first.

2. **Intent Analysis** — Using the LLM (main session), skillr analyzes your task and extracts:
   - `intent`: refined intent description
   - `constraints`: any constraints you mentioned
   - `keywords`: 3-5 keywords for initial filtering

3. **Intent Routing** — Call `filter_by_intent_vector(intent.intent, skills, top_k=20)`:
   - **Default (`embedding_backend: "claude"`)**: returns all skills unchanged. The main session LLM handles semantic matching directly in step 4.
   - **`embedding_backend: "model"`**: returns top-20 vector-filtered candidates using fastembed ONNX embeddings. Falls back to all skills if vector store unavailable.

4. **LLM Ranking** — With the candidates from step 3, the LLM ranks them by relevance and returns the top 3-5 matches with match reasons.

5. **Selection** — skillr presents up to 4 matches per batch. Each batch ends with option `n` for pagination (or giving up on the last batch).

   **Batch 1:**
   ```
   找到 4 个匹配的 Skills：

   1. `/ce:plan` (已被选 8 次) — 理由: 专门用于规划实现方案
   2. `/fastapi-gen` (已被选 12 次) — 理由: 生成 FastAPI 项目结构
   3. `/auth-templates` (已被选 3 次) — 理由: 提供认证模板代码
   4. `/api-design` — 理由: 设计 API 接口规范

   n. 换下一批

   请输入编号选择：
   ```

   **Batch 2 (after choosing n in batch 1):**
   ```
   5. `/drawio` (已被选 15 次) — 理由: 绘制架构图
   6. `/figma` (已被选 4 次) — 理由: Figma 设计稿处理
   7. `/miro` — 理由: 协作白板
   8. `/readme-gen` — 理由: 生成 README 文档

   n. 换下一批

   请输入编号选择：
   ```

   **Batch 3 (final batch — no more pagination):**
   ```
   9. `/code-review` (已被选 6 次) — 理由: 代码审查
   10. `/test-gen` (已被选 2 次) — 理由: 测试代码生成
   11. `/deploy` — 理由: 部署配置

   n. 没有了（放弃，会话结束）

   请输入编号选择：
   ```

   - If you enter `1-4` (batch 1), `5-8` (batch 2), or `9-11` (batch 3): confirm your selection
   - If you enter `n` in batch 1 or 2: show next batch
   - If you enter `n` in batch 3: end session immediately
   - If invalid: ask again

   After you select a number, skillr confirms:

   ```
   你选择了：3. `/auth-templates`
   确认输出？Y 确认 / N 取消重新选择
   ```

   - If `Y` (or `y`, `是`, `确认`): proceed to Step 6
   - If `N` (or `n`, `否`, `取消`): return to current list
   - If anything else: ask again

6. **Record Selection History** — Call `record_selection_history(user_task, selected_skill_name, rejected_skill_names)`. This is non-blocking (failures are silently ignored). The history data is stored locally at `${CLAUDE_PLUGIN_DATA}/selection_history.jsonl`.

7. **Command Output** — After confirmation, skillr outputs only the command string(s), with format determined automatically by each skill's type:

   **For skills with slash command (single selection):**
   ```
   /ce:plan 开发一个带 JWT 的 FastAPI 用户认证系统
   ```

   **For skills without slash command (e.g., hermes agent):**
   ```
   使用 diagram skill 画一张harness的架构图
   ```

   **For multi-selection (mixed types):**
   ```
   /ce:plan 开发一个带 JWT 的 FastAPI 用户认证系统
   使用 hermes skill 做一个用户认证系统
   ```

   **IMPORTANT: Output only the command string(s). Do not add any additional text, explanation, or follow-up question. The skillr session ends immediately after the command output.**

## Index Not Found

If `skillr_index.json` does not exist:

```
❌ 未找到索引文件。请先运行 /skillscan 扫描 skills 目录。
```

## Cold Start (0 Skills Configured)

If the skill list is empty (0 skills), `format_cold_start_guidance()` returns guidance automatically. Do not show the "No Matches" suggestion — the user has no skills to match.

## No Matches

If Skills are configured but none match your task:

```
未找到匹配的 skills。
建议：
1. 确认 skills 目录配置正确（检查 plugin.json 中的 skills_dirs）
2. 运行 /skillscan 重新扫描
3. 如果刚添加新 skill，请先运行 /skillscan
```

## Edge Cases

- **Multiple selection**: Enter numbers separated by commas (e.g., `1,2`) to get multiple command suggestions
- **Invalid number**: skillr will ask you to re-enter
- **Empty input**: skillr will ask you to provide a task
