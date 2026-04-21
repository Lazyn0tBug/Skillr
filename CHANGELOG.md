# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- E0: Cold start guidance — new users with 0 skills see setup instructions instead of generic "no matches"
- `format_cold_start_guidance()` in router.py for empty skills state

### Changed
- `format_match_results_for_display()` now differentiates cold start (empty skills) from generic no-match

### Added (E1)
- `IntentCacheEntry` and `IntentCache` Pydantic models in models.py
- `IntentCacheStore` class in cache.py — disk-persistent TTL cache at `${CLAUDE_PLUGIN_DATA}/cache/intent_cache.json`
- `route_intent_cached()` and `cache_match_results()` functions in router.py for cache-aware routing
- `tests/test_cache.py` with 11 tests covering cache hit/miss, TTL expiry, invalidation, and persistence

### Added (E2)
- `SourceTracking.file_mtimes` dict for per-skill-file mtime tracking
- `scanner.scan_skills_dir()` now returns `tuple[list[SkillMeta], dict[str, str]]` — skills + per-skill mtimes
- `indexer.build_incremental_index()` — skips dirs whose file_mtimes unchanged since last build
- `indexer._skills_from_dir()` helper — matches skill's `file_path.parent.parent` to skills_dir
- `tests/test_indexer.py::TestIncrementalIndex` — 5 tests for incremental scan, mtime change detection, and delete detection

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
