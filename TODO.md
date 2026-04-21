# TODO

Future work and known issues for Skillr.

## In Progress

- [ ] Unit 1: Project Foundation — pyproject.toml, plugin.json, SKILL.md files (Markdown Skill pattern)
- [ ] Unit 2: Skill Scanner — scanner.py, indexer.py, models.py (SkillMeta, SkilrIndex with tiered mtime), config.py
- [ ] Unit 3: Skill Router — router.py, intent.py, matcher.py + command output bifurcation
- [ ] Unit 4: Output Artifacts — CHANGELOG.md, TODO.md, Session.md

## Known Issues

- [ ] LLM prompt templates need field testing and tuning
- [ ] YAML frontmatter parsing edge cases not yet identified
- [ ] No vector database upgrade path implemented
- [ ] mtime tiered strategy: verify git-aware detection works for project skills_dirs; confirm per-file mtime catches all stale-index scenarios on target OSes
- [ ] retrieval_window default value (50) needs field testing

## Future Enhancements

- [ ] Vector database integration for semantic skill matching
- [ ] Background index refresh via cron/heartbeat
- [ ] Skill auto-discovery from remote registry
- [ ] TUI interactive selection interface
- [ ] Dependency graph / parallel execution for multi-skill plans
- [ ] DAG state machine for execution plans
- [ ] Rust implementation for performance-critical paths
- [ ] **Command bifurcation: `/<cmd> refine(<intent>)` vs `我想用 <skill> skill <intent>`**
- [ ] **Subcommand detection: detect if SKILL.md has subcommand tables**
- [ ] **SKILR_INDEX.md generation: Markdown-format human-readable index**
- [ ] **CLAUDE_PLUGIN_DATA env var verification**: confirm Claude Code Plugin SDK behavior

## Non-Goals (Explicitly Excluded)

- Skillr will not execute Skill commands on behalf of users
- Skillr will not manage Skill lifecycle (install/uninstall/version)
- Skillr will not provide its own LLM API key
- Skillr will not auto-match non-slash-command Skills without user selection
