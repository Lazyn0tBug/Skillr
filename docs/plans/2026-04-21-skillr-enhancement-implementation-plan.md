---
date: 2026-04-21
topic: skillr-enhancement-implementation-plan
status: draft
---

# Skillr Enhancement Implementation Plan

基于 `docs/brainstorms/2026-04-21-skillr-enhancements-requirements.md` 的 requirements review 后修订版。

## E0: 冷启动引导 (Cold Start)

### E0-Step 1: `router.py` 空 skills 检测 + 引导信息
- **文件**: `src/skillr/router.py`
- **修改**: `load_skills_or_none()` → 空时返回空列表；`format_match_results_for_display()` → 空 skills 时显示引导
- **交付物**: 引导文案（待确认措辞）

### E0-Step 2: SKILL.md workflow 更新
- **文件**: `skills/skillr/SKILL.md`
- **修改**: Step 2（加载 index 后）添加空 skills 判断分支

### E0-Step 3: 测试
- **文件**: `tests/test_router.py`
- **修改**: 添加空 skills 场景测试

### E0-Step 4: CHANGELOG / TODO 更新
- **文件**: `CHANGELOG.md`, `TODO.md`

---

## E1: 结果缓存 (Result Cache)

### E1-Step 1: 设计缓存数据模型 `IntentCacheEntry`
- **文件**: `src/skillr/models.py`
- **修改**: 添加 `IntentCache`, `IntentCacheEntry` Pydantic model

### E1-Step 2: 实现 `cache.py` 磁盘持久化
- **文件**: `src/skillr/cache.py` (新文件)
- **修改**: 磁盘持久化读写，TTL 逻辑，key = `sha256(intent + skill_ids_hash)`
- **路径**: `${CLAUDE_PLUGIN_DATA}/cache/intent_cache.json`

### E1-Step 3: `router.py` 集成缓存读写
- **文件**: `src/skillr/router.py`
- **修改**: 查询时先查缓存 → 命中返回；未命中调用 LLM → 写入缓存

### E1-Step 4: 降级策略
- **修改**: 缓存损坏/解析失败 → 降级为正常 LLM 调用

### E1-Step 5: 测试
- **文件**: `tests/test_cache.py` (新文件), `tests/test_router.py`
- **修改**: 缓存读写、TTL、失效、损坏降级测试

### E1-Step 6: CHANGELOG 更新
- **文件**: `CHANGELOG.md`

---

## E2: 增量索引 (Incremental Index)

### E2-Step 1: `SourceTracking` model 扩展 per-file tracking
- **文件**: `src/skillr/models.py`
- **修改**: `SourceTracking` 支持 per-file 条目

### E2-Step 2: `scanner.py` 记录 per-skill-file mtime
- **文件**: `src/skillr/scanner.py`
- **修改**: 扫描时记录每个 SKILL.md 的 mtime

### E2-Step 3: `indexer.py` 增量扫描逻辑
- **文件**: `src/skillr/indexer.py`
- **修改**: 对比新旧 mtime，只重建变化的文件

### E2-Step 4: 删除文件检测
- **修改**: 对比新旧 index skill 列表，移除已删除的 skill

### E2-Step 5: 测试
- **文件**: `tests/test_indexer.py`
- **修改**: 增量扫描、删除检测、降级全量扫描测试

### E2-Step 6: CHANGELOG 更新
- **文件**: `CHANGELOG.md`

---

## E3: 向量匹配 (Vector Matching)

### E3-Step 1: 添加 Chroma + bge-small-zh 依赖
- **文件**: `pyproject.toml`
- **修改**: 添加 `chromadb`, `sentence-transformers` 依赖

### E3-Step 2: 索引构建时生成 embedding
- **文件**: `src/skillr/vectors.py` (新文件)
- **修改**: skill description → bge-small-zh embedding → Chroma

### E3-Step 3: 查询时向量相似度搜索
- **文件**: `src/skillr/vectors.py`
- **修改**: intent → embedding → Chroma top-k 搜索

### E3-Step 4: 混合匹配（向量分数 + LLM Ranking）
- **文件**: `src/skillr/matcher.py`, `src/skillr/router.py`
- **修改**: 向量分数作为 LLM Ranking 的补充输入

### E3-Step 5: 降级策略
- **修改**: 向量搜索失败 → 降级回关键词过滤；embedding 模型不可用 → 降级回纯 LLM Ranking

### E3-Step 6: 测试
- **文件**: `tests/test_vectors.py` (新文件)
- **修改**: embedding 生成、向量搜索、混合匹配、降级测试

### E3-Step 7: CHANGELOG 更新
- **文件**: `CHANGELOG.md`

---

## E4: Rust 扫描 (Rust Scanner)

### E4-Step 1: 建立 `.benchmarks/` benchmark harness
- **文件**: `.benchmarks/scan_benchmark.py` (新文件)
- **修改**: 测量当前 Python scan 性能，确认瓶颈

### E4-Step 2: 创建 Rust scanner crate
- **文件**: `rust-scanner/` (新目录)
- **修改**: `Cargo.toml`, `src/main.rs` — 文件遍历 + YAML 解析

### E4-Step 3: 定义 subprocess JSON 接口
- **修改**: Rust stdout 输出 JSON，Python 解析

### E4-Step 4: `scanner.py` 调用 Rust CLI
- **文件**: `src/skillr/scanner.py`
- **修改**: `scan_skills_dir()` → subprocess 调用 Rust 二进制

### E4-Step 5: 测试
- **文件**: `tests/test_scanner_rust.py` (新文件)
- **修改**: CLI 接口测试、性能对比测试

### E4-Step 6: CHANGELOG 更新
- **文件**: `CHANGELOG.md`

---

## E5: 用户选择进化 Phase 1 (Selection History Infrastructure)

### E5-Step 1: `SelectionHistoryStore` 数据模型
- **文件**: `src/skillr/models.py`
- **修改**: `SelectionRecord` Pydantic model

### E5-Step 2: `history.py` 存储读写
- **文件**: `src/skillr/history.py` (新文件)
- **修改**: JSONL 文件读写，`${CLAUDE_PLUGIN_DATA}/selection_history.jsonl`
- **Schema**: `{intent_hash, selected_skill, rejected_skills[], timestamp}`

### E5-Step 3: `router.py` 集成历史记录
- **文件**: `src/skillr/router.py`
- **修改**: 用户选择后写入历史记录

### E5-Step 4: 测试
- **文件**: `tests/test_history.py` (新文件)
- **修改**: 读写、进程重启后恢复、清除历史测试

### E5-Step 5: CHANGELOG 更新
- **文件**: `CHANGELOG.md`

---

## Summary

| Enhancement | Steps | Files Touched |
|-------------|-------|---------------|
| E0: 冷启动引导 | 4 | router.py, SKILL.md, test_router.py, CHANGELOG.md, TODO.md |
| E1: 结果缓存 | 6 | models.py, cache.py (new), router.py, test_cache.py (new), test_router.py, CHANGELOG.md |
| E2: 增量索引 | 6 | models.py, scanner.py, indexer.py, test_indexer.py, CHANGELOG.md |
| E3: 向量匹配 | 7 | pyproject.toml, vectors.py (new), matcher.py, router.py, test_vectors.py (new), CHANGELOG.md |
| E4: Rust 扫描 | 6 | .benchmarks/ (new), rust-scanner/ (new), scanner.py, test_scanner_rust.py (new), CHANGELOG.md |
| E5: 用户选择进化 Phase 1 | 5 | models.py, history.py (new), router.py, test_history.py (new), CHANGELOG.md |

**Total: 34 steps across 6 enhancements**
