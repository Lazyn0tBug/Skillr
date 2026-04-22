---
date: 2026-04-21
topic: skillr-enhancements
---

# Skillr Enhancements Requirements

## Context

Skillr v0.1.2 已发布，实现了基础的 `/skillr` 路由和 `/skillscan` 扫描功能。

现有流程：
```
用户输入 → 关键词过滤 → LLM Ranking → 用户选择 → 输出命令
```

## 问题发现

当前实现没有解决以下场景：
- 重复查询每次都重新调用 LLM（延迟 + 费用）
- `/skillscan` 每次全量扫描大量文件
- 关键词匹配无法捕获语义相似性
- 用户选择历史没有用于优化匹配
- 新用户冷启动（0 skills）没有任何引导

## Enhancement Roadmap

按优先级排列：

### E0: 冷启动引导 (Cold Start)

**目标：** 新用户（0 skills）有清晰的引导，不再困惑

**行为描述：**
- 检测到 skills 列表为空时，显示引导信息
- 提供 SKILL.md 模板或链接到 Claude Code skills 文档

**边界：**
- 不做远程 skill 发现或自动安装

**成功标准：**
- 0 skill 用户运行 `/skillr` 时，看到引导信息而非空白或错误

---

### E1: 结果缓存 (Result Cache)

**目标：** 相同/相似查询直接返回缓存结果，避免重复 LLM 调用

**行为描述：**
- 缓存 backend：**磁盘持久化**（`${CLAUDE_PLUGIN_DATA}/cache/intent_cache.json`）
- 缓存 key：`sha256(intent + sorted(skill_ids_hash))` — 使用 skill ID 列表的 hash 而非 count，避免 count 不变但内容变化时返回脏数据
- 缓存 value：`MatchResult[]` 列表（JSON 序列化）
- TTL：可配置，默认 1 小时
- 命中条件：intent hash 匹配且 skill 列表内容未变（通过 skill_ids_hash 检测）

**用户场景：**
- 用户重复查询 "我想做用户认证" → 直接返回缓存结果，不调用 LLM
- skills 内容变化（新增/删除/修改 skill）→ 自动失效

**边界：**
- 只缓存 LLM Ranking 结果（keyword filter 和 index 加载不缓存）
- 进程重启后从磁盘恢复缓存
- 缓存损坏或解析失败 → 降级为正常 LLM 调用，不阻塞用户

**成功标准：**
- 缓存命中时 LLM 不被调用（可观测：无 LLM API 调用日志）
- 缓存命中率可观测（debug 日志或 metrics）

---

### E2: 增量索引 (Incremental Index)

**目标：** `/skillscan` 只扫描有变化的文件，不全量扫描

**行为描述：**
- 现有 `source_tracking` 在 directory 级别（git commit hash 或 skills_dir mtime）
- **E2 增强**：在 directory 级 tracking 基础上，增加 per-skill-file mtime 记录
- 调用 `/skillscan` 时对比 mtime，只重建有变化的文件
- 新增文件：增量添加
- 删除文件：从索引移除（对比新旧 index 的 skill 列表）
- skills 目录结构变化（如子目录改名）→ 降级为全量扫描

**用户场景：**
- 用户新增一个 skill → `/skillscan` 只处理新文件，秒级完成
- 用户删除一个 skill → 索引对应移除

**边界：**
- mtime 不可靠时（如 USB 磁盘、NFS）→ 降级为全量扫描
- git repo 内优先使用 git-aware tracking（已实现）

**成功标准：**
- 增量 scan 时间 < 全量 scan 的 20%（当只有 1 个文件变化时）

---

### E3: 向量匹配 (Vector Matching)

**目标：** 用 Embedding 做语义匹配，补充关键词过滤；向量库作为存储层，query engine 可配置

**行为描述：**

**存储层（固定）：**
- 每个 skill 的 description 生成 embedding，存入 ChromaDB（`${CLAUDE_PLUGIN_DATA}/vectors/`）
- 索引构建时自动填充 `/skillscan` 时同步重建

**Query Engine（可配置，默认 `claude`）：**

| 配置值 | 行为 | 适用场景 |
|--------|------|---------|
| `claude`（默认） | 主 Session LLM 直接对 skills 做语义排序，无需向量预处理 | 通用场景，零额外依赖 |
| `model` | fastembed ONNX（bge-small-zh）做向量预过滤，top-20 候选传给 LLM | 超大 skill 集合（500+） |

- 配置项：`embedding_backend: "claude" | "model"`（默认 `"claude"`）
- 写入 `plugin.json` 或 `${CLAUDE_PLUGIN_DATA}/config.json`

**用户场景（默认 claude）：**
- 用户输入 "画图" → LLM 直接理解 intent，从 900 skills 中语义匹配到 "drawio"
- 关键词 "drawio" 不含"图"字，纯关键词过滤可能漏掉

**边界：**
- `"model"` 模式：向量搜索失败时 → 降级回关键词过滤
- `"claude"` 模式：无需降级，LLM 本身就能做语义理解
- E3 不会完全替代 LLM Ranking（混合模式）

**成功标准：**
- 离线评估集（20+ sample queries）上 recall@5 提升 >= 20%（对比纯关键词过滤）
- `"claude"` 模式为主流默认，无需额外模型安装

---

### E4: Rust 核心 (Rust Core)

**目标：** 用 Rust 构建 `skillr-core` 二进制，实现接近零延迟的索引操作，使 `/skillr` 可以在路由时透明重建索引，无需用户手动 scan

**动机澄清：**
> Python 当前 benchmark（1000 skills: 149ms）已经「够快」，但 Rust 的目标是「快到可以忽略」——不是拯救慢 Python，而是让索引重建在路由流程中无感内嵌。

**Benchmark 结论（2026-04-21）：**
- Python 1000 skills: 149ms（YAML 解析占 88%）
- Python 预估 10000 skills: ~1500ms
- Rust 理论预估 1000 skills: ~15-30ms（5-10x 加速）
- Rust 预估 5000 skills: ~75ms（用户无感知阈值 <100ms）

**Rust 价值的正确理解：**
- 不是「Python 太慢所以用 Rust」
- 而是「Rust 快到 `/skillr` 可以在路由时自动重建 index，用户无需手动 `/skillscan`」
- 消除「scan 之后文件变了但 index 还是旧的」状态不一致问题

**架构设计：**

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code (SKILL.md workflow)                              │
│  Python skillr_cli (薄入口)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  router.py    — workflow orchestration                │   │
│  │  intent.py    — LLM intent extraction                 │   │
│  │  matcher.py   — LLM ranking                          │   │
│  │  vectors.py   — fastembed + ChromaDB                 │   │
│  │  config.py    — 只读访问（Rust 已持久化）             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│               ┌──────────────────────┐                      │
│               │   skillr-core        │  (Rust CLI binary)   │
│               │                      │                      │
│               │  scan                │  ← 文件遍历 + YAML  │
│               │  index build         │  ← 索引构建 + 持久化 │
│               │  intent cache r/w    │  ← 磁盘读写        │
│               │  history write       │  ← DuckDB 写入     │
│               │  history query      │  ← DuckDB OLAP     │
│               └──────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

**Rust 二进制职责（完整功能）：**
| 功能 | Python 当前 | Rust 实现 |
|------|------------|----------|
| Scanner（glob + YAML + mtime） | `scanner.py` | `skillr-core scan` |
| Index 构建 + 持久化 | `indexer.py` | 内置于 scan |
| IntentCache 读写 | `cache.py` | `skillr-core cache` |
| Config 读写 | `config.py` | `skillr-core config` |
| SelectionHistory | `history.py` | **留在 Python**（DuckDB SDK 够用） |

**Python 层保留职责（不可 Rust 化）：**
- LLM API 调用（`intent.py`, `matcher.py` 的 OpenAI/Anthropic 调用）
- fastembed ONNX embedding 生成（`vectors.py`）
- SKILL.md workflow 执行（Claude Code 的 interface）

**调用方式：CLI（subprocess），非库绑定**

理由：
- 解耦 release 周期：Rust 二进制独立编译发布
- 无 FFI/GIL 复杂性
- 简单调试：CLI 输出可直接在终端验证
- 零绑定维护：无 PyO3 兼容性担忧

**CLI 接口设计：**
```bash
# 扫描 + 重建索引
skillr-core scan --dir ~/.claude/skills

# 读取选择历史
skillr-core history --get-count drawio --days 30

# 写入选择记录
skillr-core history --add "hash123" "drawio" '["miro"]'

# 缓存操作
skillr-core cache --get "intent_hash"
skillr-core cache --set "intent_hash" '["match_results_json"]'
```

**文件接口：**
- Rust 直接写 `${CLAUDE_PLUGIN_DATA}/index/skillr_index.json`
- 不走 stdout（stdout 只用于短命令的返回值）
- Python 读文件作为「结果」，Rust 负责「执行」

**`/skillr` 行为变化：**
- **Before（当前）：** index 过期 → 提示用户跑 `/skillscan` → 用户手动 scan → 继续路由
- **After（Rust）：** index 过期 → `skillr-core scan`（<30ms）→ 继续路由
- `/skillscan` 保留，变成可选的「预热」命令，不是必须的

**边界：**
- MVP 不做 Rust 绑定，直接 `subprocess.run()`
- Python 代码结构需要重新设计（见下方）
- E5 历史查询保持在 Python（DuckDB Python SDK 已足够）

**Python 层重新设计指引：**

当前 `src/skillr/` 结构 → 目标结构：
```
src/skillr/
├── cli.py           # 薄入口：解析 skillr-core 输出
├── router.py        # 保留：workflow + LLM 调用
├── intent.py        # 保留：LLM prompt + 解析
├── matcher.py       # 保留：LLM prompt + 解析
├── vectors.py       # 保留：fastembed ONNX + ChromaDB
├── models.py        # 保留：共享类型（Rust 输出必须匹配此 schema）
└── (scanner.py, indexer.py, cache.py, history.py, config.py)
    → 迁移到 Rust，不在 Python 层存在
```

**成功标准：**
- Rust `skillr-core scan` 1000 skills < 30ms
- Rust `skillr-core scan` 5000 skills < 100ms（用户无感知阈值）
- `/skillr` 在 index 过期时自动重建，用户无需手动 scan

---

### E5: 用户选择进化 (Selection Evolution)

**目标（分阶段）：**
- **Phase 1（已完成）：** 建立用户选择历史存储基础设施（JSONL）
- **Phase 1.5（立即）：** 展示 skill 被选次数（带时间窗口），辅助用户决策
- **Phase 2（后期）：** 基于历史数据优化 LLM Ranking 权重

---

#### Phase 1（已完成）— 存储基础设施

- 存储格式：`${CLAUDE_PLUGIN_DATA}/selection_history.duckdb`（DuckDB）
- Schema：`{intent_hash, selected_skill, rejected_skills VARCHAR[], created_at TIMESTAMP}`
- 通过 DuckDB 隐式 `rowid` 实现插入顺序（无显式 id 列）
- E5 历史读写暂保持在 Python（DuckDB Python SDK），暂不迁移到 Rust

---

#### Phase 1.5（已完成）— 时间窗口 + 展示选择次数

**设计决策：**

1. **存储升级：JSONL → DuckDB**
   - JSONL 适合纯日志（只追加、不查询），E5 数据从第一天就需要被查询
   - DuckDB 已通过 chromadb 引入（chromadb 依赖 duckdb），无需额外添加依赖
   - 列式存储 + 向量化执行：时间窗口聚合查询比 SQLite 快 10-100x
   - 原生支持复杂 OLAP 聚合（Phase 2 所需的多维度分析无需重写存储层）
   - 迁移：一次性 JSONL → DuckDB 迁移脚本，不丢数据

2. **时间窗口：展示最近活跃度，而非总次数**
   - 总次数的参考价值有限（drawio 总47次，但最近30天只有12次；miro 总5次但最近30天4次）
   - 用户场景：「找最近流行的 skill」→ 时间窗口比总数更有预测力
   - 查询默认窗口：30天（可配置）
   - 展示格式：`已被选 12 次（近30天）`

3. **字段设计（不变）：**
   ```
   intent_hash     — SHA256(intent text)，用于缓存 key 和去重
   selected_skill  — 用户选择的 skill 名称
   rejected_skills — 用户拒绝的 skill 列表（可为空）
   timestamp       — ISO 格式时间戳（窗口过滤依据）
   ```
   无需新增字段，timestamp 本身即窗口依据。

4. **冷热库：暂不做**
   - DuckDB 单库即可做热数据实时查询 + 冷数据批量分析，无需分层
   - 等数据量证明需要时再加（过早抽象）

**用户场景：**
```
找到 4 个匹配的 Skills：

1. `/drawio` (已被选 12 次) — 理由: 通用图表绘制
2. `/floracat-architecture-diagram` (已被选 8 次) — 理由: 架构图专用
3. `/miro` (已被选 4 次) — 理由: 协作白板
4. `/figma` (已被选 1 次) — 理由: UI 设计稿处理

n. 换下一批
```

**成功标准 Phase 1.5：**
- 结果列表每项显示「已被选 X 次（近30天）」
- 窗口内0次的不显示次数
- DuckDB 查询性能 < 10ms（1000条记录下）

---

#### Phase 2 — Ranking 加权（暂不实现）

**在 Phase 1.5 完成后进行。**

基于 `selection_history` 表的聚合数据：

- **选择率**：某 skill 被选次数 / 被展示次数
- **拒绝率**：某 skill 被展示但拒绝的比率
- **时间衰减**：近期选择权重 > 远期

**在线应用：**
- 在 `build_matcher_prompt_for_intent` 注入历史偏好：
  ```
  参考：drawio 用户选择率高（85%），miro 用户普遍不感兴趣（拒绝率90%）
  ```
- 不改变 LLM Ranking 算法，只在 prompt 中附加信号

**DuckDB 聚合（Phase 2 需实现）：**
```sql
-- 选择率 = 被选次数 / 被展示次数
SELECT
    selected_skill,
    COUNT(*) as selection_count,
    list_filter(rejected_skills, x -> x = selected_skill) as rejections
FROM selection_history
WHERE created_at > datetime('now', '-30 days')
GROUP BY selected_skill
ORDER BY selection_count DESC;
```

---

#### 迁移计划（已完成）

**JSONL → DuckDB 一次性迁移（已完成）：**

1. 创建 DuckDB 数据库 `${CLAUDE_PLUGIN_DATA}/selection_history.duckdb`
2. 建表：
```sql
CREATE TABLE IF NOT EXISTS selection_history (
    intent_hash VARCHAR,
    selected_skill VARCHAR,
    rejected_skills VARCHAR[],  -- DuckDB 原生 VARCHAR[]
    created_at TIMESTAMP
);
-- 使用 DuckDB 隐式 rowid 代替显式自增 id
CREATE INDEX ON selection_history(selected_skill);
CREATE INDEX ON selection_history(created_at);
```
3. 读取现有 JSONL，每行解析后写入 DuckDB
4. 迁移完成后删除 JSONL（或备份为 `.bak`）
5. `history.py` 改用 DuckDB：建表、增删改查

**成功标准：**
- 迁移后数据行数一致 ✅
- 原有 `add_record()`, `get_all_records()`, `clear()` 接口不变（调用方无感知）✅
- 新增 `get_skill_selection_count(skill_name, days=30)` 查询函数 ✅

---

## E5 执行规划（Phase 1 + 1.5 已完成）

所有 Step 已完成（见上方 Phase 1 迁移计划 + Phase 1.5 展示层修改）。

---

**预计改动文件（Phase 1 + 1.5 已完成）：**
- `src/skillr/history.py` ✅（已完成）
- `src/skillr/router.py` ✅（已完成）
- `tests/test_history.py` ✅（已完成）
- `skills/skillr/SKILL.md` ✅（已完成）
- `docs/brainstorms/2026-04-21-skillr-enhancements-requirements.md` ✅（已更新）

---

## Open Questions

- E2（增量索引）：如何检测 skills_dir 本身被删除或重建？

## Dependencies

- E1 依赖 E2 的变化检测来实现缓存失效（可独立开发，但运行时有依赖）
- E3（`model` 模式）依赖 E1（缓存基础设施）；E3（`claude` 模式）无额外依赖
- E4（Rust Core）可在任何阶段独立进行
- E5 Phase 1.5（时间窗口展示）不依赖 E1/E2/E3，可独立进行
- E5 Phase 2（Ranking 加权）依赖 Phase 1.5 完成后的 DuckDB 基础设施
- E5 历史查询（Python → Rust）：E5 写入保持 Python（DuckDB Python SDK），暂不迁移

## Non-Goals

- Skillr 不会自动执行用户未选择的命令
- Skillr 不会上传用户选择数据到远程服务器
- E3 不会完全替代 LLM Ranking（混合模式）
- E4 不会用 Rust 绑定替代 subprocess CLI（无 FFI 复杂性）
- E4 不会让 `/skillscan` 消失（保留为可选预热命令）
