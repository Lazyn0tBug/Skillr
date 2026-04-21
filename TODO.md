# TODO

Future work and known issues for Skillr.

## In Progress

- [x] Unit 1: Project Foundation — pyproject.toml, plugin.json, SKILL.md files (Markdown Skill pattern)
- [x] Unit 2: Skill Scanner — scanner.py, indexer.py, models.py (SkillMeta, SkillrIndex with tiered mtime), config.py
- [x] Unit 3: Skill Router — router.py, intent.py, matcher.py
- [x] Unit 4: Output Artifacts — CHANGELOG.md, TODO.md, Session.md
- [x] Full test suite — 156 tests: unit, integration, scenario, performance
- [x] Pagination selection — 4 results/batch, max 3 batches, Y/N confirmation
- [x] Slash/non-slash auto-routing — `has_slash_command` field, dual output format
- [x] **E0: Cold start guidance** — 0 skills users see setup instructions

## Known Issues

- [ ] LLM prompt templates need field testing and tuning
- [ ] YAML frontmatter parsing edge cases not yet identified
- [ ] mtime tiered strategy: verify git-aware detection works for project skills_dirs; confirm per-file mtime catches all stale-index scenarios on target OSes
- [ ] retrieval_window default value (50) needs field testing

## Enhancement Roadmap (E1-E5)

- [ ] **E1: Result cache** — disk-persistent intent cache with TTL
- [ ] **E2: Incremental index** — per-file mtime tracking, delta scan
- [ ] **E3: Vector matching** — Chroma + bge-small-zh embedding
- [ ] **E4: Rust scanner** — Rust CLI subprocess for file/YAML scanning
- [ ] **E5: Selection history** — JSONL-based selection tracking (Phase 1 infrastructure)

## Future Enhancements

- [ ] Background index refresh via cron/heartbeat
- [ ] Skill auto-discovery from remote registry
- [ ] TUI interactive selection interface
- [ ] Dependency graph / parallel execution for multi-skill plans
- [ ] DAG state machine for execution plans
- [ ] **SKILR_INDEX.md generation: Markdown-format human-readable index**
- [ ] **CLAUDE_PLUGIN_DATA env var verification**: confirm Claude Code Plugin SDK behavior

## Non-Goals (Explicitly Excluded)

- Skillr will not execute Skill commands on behalf of users
- Skillr will not manage Skill lifecycle (install/uninstall/version)
- Skillr will not provide its own LLM API key
- Skillr will not auto-match non-slash-command Skills without user selection
