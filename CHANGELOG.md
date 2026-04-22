# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-22

### Added (E4)
- `rust-scanner/` crate: high-performance skill index scanner in pure Rust
- `skillr-core` CLI binary with 5 subcommands: `scan`, `cache-get`, `cache-set`, `config-get`, `index-get`
- Atomic index/cache writes via POSIX `rename` (ADV-001)
- HMAC-SHA256 cache integrity verification (ADV-007)
- SKILL.md YAML frontmatter parsing with per-file mtime tracking
- `tests/test_rust_cli.py` — 13 integration tests for all subcommands
- Rust best practices review: clippy clean, `#[deny(missing_docs)]`, normalized test naming

## [0.1.8] - 2026-04-22

### Added (E3)
- `EmbeddingStore` class in vectors.py — ChromaDB + fastembed ONNX embedding for semantic skill matching
- `embedding_backend` config option: `"claude"` (default, zero deps) or `"model"` (vector pre-filtering)
- `filter_by_intent_vector()` in router.py — pre-filters skills by semantic similarity (model mode)
- `bge-small-zh-v1.5` embedding model via fastembed ONNX (~100MB, no PyTorch)
- Lazy-load vectors: ChromaDB and fastembed only loaded when `embedding_backend = "model"`
- `tests/test_vectors.py` — 12 tests for embedding store health, search, and fallback behavior

### Added (E5 Phase 2)
- `get_skill_stats(skill_names, days)` batch aggregation for multiple skills in one query
- `_build_history_context()` injects per-skill selection counts into LLM matcher prompt
- `history_context` parameter added to `build_matcher_prompt()` — LLM ranks with historical preference signal
- `tests/test_router.py::TestBuildMatcherPromptWithHistory` — verifies context injection

### Added (Security Fixes)
- ADV-001: Orphaned `.tmp` cleanup on cache load — prevents permanent cache loss after crash during rename
- ADV-002: `logger.warning()` on DuckDB write/query failures in history.py (silent failures now observable)
- ADV-006: `cache.invalidate_all()` called after every index rebuild (run_indexer) — cache coherence
- ADV-007: HMAC-SHA256 cache signature with machine-specific `cache_secret` from config.json — tampering detection
- `get_cache_secret()` in config.py — generates and persists 256-bit machine-specific cache HMAC key
- Pre-existing caches (no signature) are trusted on read and re-signed on write

### Added (E1)
- `IntentCacheEntry` and `IntentCache` Pydantic models in models.py
- `IntentCacheStore` class in cache.py — disk-persistent TTL cache at `${CLAUDE_PLUGIN_DATA}/cache/intent_cache.json`
- `route_intent_cached()` and `cache_match_results()` functions in router.py for cache-aware routing
- `tests/test_cache.py` with tests covering cache hit/miss, TTL expiry, invalidation, and persistence

### Added (E2)
- `SourceTracking.file_mtimes` dict for per-skill-file mtime tracking
- `scanner.scan_skills_dir()` now returns `tuple[list[SkillMeta], dict[str, str]]` — skills + per-skill mtimes
- `indexer.build_incremental_index()` — skips dirs whose file_mtimes unchanged since last build
- `indexer._skills_from_dir()` helper — matches skill's `file_path.parent.parent` to skills_dir
- `tests/test_indexer.py::TestIncrementalIndex` — tests for incremental scan, mtime change, and delete detection

### Added (E5 Phase 1)
- `SelectionRecord` Pydantic model in models.py — stores intent_hash, selected_skill, rejected_skills, timestamp
- `SelectionHistoryStore` class in history.py — DuckDB-backed persistent store at `${CLAUDE_PLUGIN_DATA}/selection_history.duckdb`
- Auto-migration from JSONL on first DuckDB init; renames JSONL to `.bak` after migration
- `record_selection_history()` and `get_skill_selection_count()` functions in router.py
- `tests/test_history.py` — tests covering full CRUD, time-windowed queries, and router integration

### Added (E5 Phase 1.5)
- `get_skill_selection_count(skill_name, days=30)` returns count within rolling time window
- `format_match_results_for_display()` shows "已被选 X 次（近30天）" per skill when count > 0
- `tests/test_router.py::TestSelectionCountDisplay` — tests for count display behavior

### Added (E0)
- E0: Cold start guidance — new users with 0 skills see setup instructions instead of generic "no matches"
- `format_cold_start_guidance()` in router.py for empty skills state

### Changed
- `format_match_results_for_display()` now differentiates cold start (empty skills) from generic no-match
- Removed dead `build_index()` function — `run_indexer()` now calls `build_incremental_index()` only
- `run_indexer()` calls `cache.invalidate_all()` after every index rebuild (ADV-006)
- `router.py` imports `_get_history_store` from `history.py` (removed duplicate singleton)
- `indexer.py` now wires `invalidate_by_skill_ids()` into scan flow (E1↔E2 integration)
- Config file `${CLAUDE_PLUGIN_DATA}/config.json` now stores `cache_secret` for HMAC key
- Architecture diagram updated: history.py stays in Python layer; cache.py stays in Python for HMAC

## [0.1.2] - 2026-04-21

### Added
- Pagination selection: up to 4 results per batch, max 3 batches (12 total)
- Batch pagination with "n. 换下一批" option and final batch "n. 没有了（放弃，会话结束）"
- Y/N confirmation after selection before command output
- Slash/non-slash command output routing:
  - With slash command: `/<name> <intent>`
  - Without slash command: `使用 <name> skill <intent>`
- `has_slash_command` field in SkillMeta model
- Automatic session termination after command output (IMPORTANT note in SKILL.md)
- Test suite: 156 tests covering unit, integration, scenario, and performance

### Changed
- Rename scan command: `/skillrscan` → `/skillscan`
- All documentation updated to lowercase command names
- Full test suite added (was marked as missing in TODO)

### Fixed
- Slash-space issue in `assemble_command()` with `.strip()`
- Skill name whitespace stripping in scanner
- JSON regex in intent.py now uses non-greedy matching

### Technical Decisions
- Two independent Skills: `/skillscan` and `/skillr` (not sub-commands)
- Python with uv + ty + ruff + pyproject.toml
- Index stored at `${CLAUDE_PLUGIN_DATA}/index/`
- Skill discovery via YAML frontmatter parsing of `SKILL.md`
- **mtime tiered strategy**: git-aware (git ls-files) > per-file mtime > per-dir mtime (fallback)
- **No index size limit**: retrieval_window for LLM context overflow protection (not a hard limit)
- **LLM invocation**: CE pattern — Markdown Skill drives main session LLM; no sub-agent dispatch
- **intent.py / matcher.py as prompt templates**: not sub-agent dispatch functions
- **userConfig.skills_dirs type**: object `{description, sensitive}`, not string array
- **JSON-only index**: R7 specifies JSON only
- **Command bifurcation**: slash/non-slash routing now implemented
