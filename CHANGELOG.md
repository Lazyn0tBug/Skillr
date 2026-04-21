# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and requirements definition
- Requirements document: `docs/brainstorms/2026-04-21-skilr-skill-routing-framework-requirements.md`
- Implementation plan: `docs/plans/2026-04-21-001-feat-skilr-implementation-plan.md`
- SDK reference: `docs/plugins-reference.md`

### Technical Decisions
- Two independent Skills: `/SkilrScan` and `/Skilr` (not sub-commands)
- Python with uv + ty + ruff + pyproject.toml
- Index stored at `${CLAUDE_PLUGIN_DATA}/index/`
- Skill discovery via YAML frontmatter parsing of `SKILL.md`
- **mtime per-file**: tracks individual SKILL.md mtimes, not parent directory mtime
- **No index size limit**: retrieval_window for LLM context overflow protection (not a hard limit)
- **LLM invocation**: CE pattern — Markdown Skill + Task dispatch sub-agent (model: inherit), no direct API calls
- **userConfig.skills_dirs type**: object `{description, sensitive}`, not string array
- **JSON-only index**: R7 specifies JSON only; SKILR_INDEX.md deferred to vector DB version
- **No independent triggers field**: use full `description` for LLM matching (contains trigger semantics)
- **Simplified command output (MVP)**: all Skills output `/<name> <intent>`, bifurcation deferred
- **Sub-agent interface**: IntentSpec + MatchResult + keyword_filter/llm_rank functions, per CE pattern
