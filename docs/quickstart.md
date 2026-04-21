# Skillr Quickstart

Skillr 是一个 Claude Code Plugin，帮助你在终端里找到最合适的 Skill 并组装可执行的命令建议。

**特点：** 输入自然语言任务 → 意图分析 → 匹配排序 → 输出可直接复制的命令

---

## 前置要求

- Claude Code 已安装
- Python 3.11+

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/Lazyn0tBug/Skillr.git
cd Skillr

# 安装依赖
uv sync
```

### 注册为 Claude Code Plugin

将插件目录链接到 Claude Code 的插件目录：

```bash
ln -s /path/to/Skillr ~/.claude/plugins/skillr
```

或在 Claude Code 中启用本地插件（取决于你的 Claude Code 版本配置）。

---

## 配置

Skillr 需要知道去哪里扫描 Skills。当插件首次加载时，Claude Code 会根据 `plugin.json` 中的 `userConfig` 声明提示你配置 `skills_dirs`。

配置存储在 `${CLAUDE_PLUGIN_DATA}/config.json`（由 Claude Code 自动管理）。

### 本地开发配置

如果想在本地开发时使用，可以手动创建配置文件：

```bash
mkdir -p ~/.claude/plugins/data/skillr
```

在 `~/.claude/plugins/data/skillr/config.json` 中创建：

```json
{
  "skills_dirs": [
    "~/.claude/skills",
    "~/my-custom-skills"
  ]
}
```

`skills_dirs` 可以是：
- 字符串路径（支持 `~` 展开）
- 对象形式：`{"path": "~/skills", "type": "mtime"}`

### 创建示例 Skill

在配置的目录下创建 Skill 子目录，每个 Skill 需要一个 `SKILL.md`：

```bash
mkdir -p ~/.claude/skills/my-api-skill
```

```markdown
# ~/.claude/skills/my-api-skill/SKILL.md
---
name: my-api-skill
description: "Generate a REST API with FastAPI, including JWT authentication and PostgreSQL integration."
---

# My API Skill

This skill generates a production-ready FastAPI project with:
- JWT authentication
- PostgreSQL database
- CRUD endpoints
- OpenAPI docs
```

---

## 使用

### 1. 扫描 Skills

首次使用或添加新 Skill 后，先运行扫描：

```
/SkillrScan
```

输出示例：
```
✅ 扫描完成，共发现 5 个 Skills
  - ~/.claude/skills: 5 个 Skills
索引已保存至: ${CLAUDE_PLUGIN_DATA}/index/skillr_index.json
```

### 2. 查找并使用 Skill

```
/Skillr 我想做一个用户认证系统
```

Skillr 会：
1. 加载索引
2. 分析你的任务（意图、关键词）
3. 关键词预过滤 + LLM 排序
4. 展示匹配结果：

```
找到 3 个匹配的 Skills：

1. `/auth-jwt` — 理由: JWT 认证系统，直接匹配"用户认证"需求
2. `/fastapi-gen` — 理由: FastAPI 项目生成，可用于快速初始化
3. `/db-postgres` — 理由: PostgreSQL 集成，认证系统通常需要数据库

请输入编号选择（支持多选，用逗号分隔，如 1,2）：
```

### 3. 获取命令

输入编号后，Skillr 输出可执行的命令：

```
/auth-jwt 开发一个带 JWT 的用户认证系统
```

直接复制运行即可。

---

## 工作原理

```
你: /Skillr 我想做一个 API
  │
  ▼
Skillr SKILL.md 描述工作流
  │
  ▼
┌─────────────────────────────────────┐
│ 主会话 LLM（不派遣 sub-agent）      │
│  1. 意图分析 → IntentSpec          │
│  2. 关键词过滤 → 候选集             │
│  3. LLM 排序 → Top 3-5 + 理由       │
└─────────────────────────────────────┘
  │
  ▼
你选择编号 → 组装命令字符串 → 输出
```

---

## 数据流

| 阶段 | 操作 | 说明 |
|------|------|------|
| `/SkillrScan` | 扫描 → 生成索引 | 遍历 skills_dirs，解析 SKILL.md，保存 JSON |
| `/Skillr` | 加载索引 → 意图分析 → 匹配排序 → 输出命令 | 全程在主会话完成 |

---

## SKILL.md 格式

```markdown
---
name: skill-name           # Slash 命令名：/skill-name
description: "描述技能用途，用于 LLM 匹配"
---

# 可选的正文内容（当前版本不读取）
```

**注意：** 不需要单独的 `triggers` 字段——`description` 本身已包含触发条件语义。

---

## 性能

- **索引扫描**：~10k Skills 约 3-5 秒
- **意图分析 + 匹配**：< 100ms（不含 LLM 调用延迟）
- **retrieval_window**：默认 Top 50，避免 LLM context overflow

---

## 常见问题

**Q: `/Skillr` 提示"未找到索引文件"**
A: 先运行 `/SkillrScan` 生成索引。如果配置了多个 skills_dirs，确保 config.json 路径正确。

**Q: 添加了新 Skill 但搜不到**
A: 运行 `/SkillrScan` 重新扫描。

**Q: 如何指定多个 skills_dirs？**
A: 在 `${CLAUDE_PLUGIN_DATA}/config.json` 的 `skills_dirs` 中添加多个路径。

---

## 下一步

- 查看 [TODO.md](../TODO.md) 了解未来规划
- 查看 [docs/plans/](plans/) 了解技术设计细节
- 查看 [tests/](tests/) 了解测试覆盖情况
