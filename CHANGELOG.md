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
- Lazy index rebuild via mtime check
- User config for skills_dirs via plugin.json userConfig
- **LLM invocation**: CE pattern — Markdown Skill + Task dispatch sub-agent (model: inherit), no direct API calls
- **Command output bifurcation**: slash command Skills output `/<command> <intent>`; non-slash-command Skills output `我想用 <skill_name> skill <intent>`
- **userConfig.skills_dirs type**: object `{description, sensitive}`, not string array
- **JSON-only index**: R7 specifies JSON format only, no SKILR_INDEX.md generation
- **No independent triggers field**: use full `description` for LLM matching (contains trigger semantics)
- **Simplified command output (MVP)**: all Skills output `/<name> <intent>`, bifurcation deferred
