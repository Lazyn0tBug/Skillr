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

**目标：** 用 Embedding 做语义匹配，替代纯关键词过滤

**行为描述：**
- 索引构建时：每个 skill 的 description 生成 embedding，存入向量库
- 查询时：用户 intent 生成 embedding，向量相似度搜索替代关键词过滤
- 混合匹配：向量分数 + LLM Ranking 组合

**技术路径（MVP 选定）：**
- 向量库：**Chroma**（轻量，本地存储，${CLAUDE_PLUGIN_DATA}/vectors/）
- Embedding 模型：**bge-small-zh**（中文优化，本地离线，无需 API key）
- 向量库作为索引的一部分存储

**用户场景：**
- 用户输入 "画图" → 匹配到 "drawio"（description 含"架构图"），即使名称不含"图"字

**边界：**
- MVP 阶段：向量匹配作为关键词过滤的补充，不完全替代
- 向量搜索失败时 → 降级回关键词过滤（当前行为）
- Embedding 模型不可用时 → 降级回纯 LLM Ranking

**成功标准：**
- 在积累 >= 50 条用户选择历史后，向量匹配结果被选中的比例 >= 关键词匹配被选中比例 + 10 个百分点
- 或：离线评估集（20+ sample queries）上 recall@5 提升 >= 20%

---

### E4: Rust 扫描 (Rust Scanner)

**目标：** 用 Rust 重写文件扫描和 YAML 解析，提升 `/skillscan` 性能

**前置条件：**
- 先建立 benchmark harness（`.benchmarks/`）测量当前扫描性能
- 只有 benchmark 证明当前 Python 实现是瓶颈时，才开始 E4

**行为描述：**
- Rust 二进制作为 CLI 工具被 Python 调用（subprocess）
- 核心路径：文件遍历、YAML 解析、frontmatter 提取
- 清晰的接口边界：Rust 输出 JSON（stdout），Python 负责 git-aware tracking

**用户场景：**
- 1000+ skills 目录，扫描时间从 >10s 降至 <1s

**边界：**
- MVP 不做 Rust 绑定，直接 subprocess 调用
- Python 代码结构不变，只替换 scanner 模块

**成功标准：**
- benchmark 证明扫描时间 >2s 且瓶颈在文件/YAML 处理时，启动 E4
- 扫描性能提升 10x（基于 benchmark）

---

### E5: 用户选择进化 (Selection Evolution)

**目标（分阶段）：**
- **Phase 1（立即）：** 建立用户选择历史存储基础设施
- **Phase 2（后期）：** 基于历史数据优化 LLM Ranking 权重

**行为描述 Phase 1：**
- 存储格式：`${CLAUDE_PLUGIN_DATA}/selection_history.jsonl`（每行一条选择记录）
- Schema：`{intent_hash, selected_skill, rejected_skills[], timestamp}`
- 用户可清除选择历史（通过 `/skillr reset` 或配置文件）
- 数据本地存储，不上传

**行为描述 Phase 2（暂不实现）：**
- 离线计算：skill 的"选择率"和"被拒绝率"
- 在线应用：选择率高的 skill 在 LLM Ranking 时加权

**用户场景 Phase 2：**
- 用户多次选择 `drawio` 而非 `miro` → drawio 排名提升

**边界：**
- 不做实时在线学习（计算密集）
- 数据本地存储，不上传

**成功标准 Phase 1：**
- SelectionHistoryStore 可正常读写，进程重启后历史不丢失

---

## Open Questions

- E2（增量索引）：如何检测 skills_dir 本身被删除或重建？

## Dependencies

- E1 依赖 E2 的变化检测来实现缓存失效（可独立开发，但运行时有依赖）
- E3 依赖 E1（需要缓存基础设施存储向量搜索结果）
- E4 可在任何阶段独立进行（先建立 benchmark）
- E5 Phase 1（基础设施）不依赖 E1/E2，可独立进行
- E5 Phase 2（ Ranking 加权）依赖 E1 + E2

## Non-Goals

- Skillr 不会自动执行用户未选择的命令
- Skillr 不会上传用户选择数据到远程服务器
- E3 不会完全替代 LLM Ranking（混合模式）
