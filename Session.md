# Session

Session tracking for Skillr development.

## Current Session: 2026-04-21

### Work Items

| Item | Status | Notes |
|------|--------|-------|
| Requirements definition | ✅ Complete | `docs/brainstorms/2026-04-21-skillr-skill-routing-framework-requirements.md` |
| Implementation plan | ✅ Complete | `docs/plans/2026-04-21-001-feat-skillr-implementation-plan.md` |
| CHANGELOG.md | ✅ Complete | Initial version |
| TODO.md | ✅ Complete | Initial version |
| Session.md | ✅ Complete | This document |

### Key Decisions Made

| Decision | Rationale |
|----------|----------|
| Two independent Skills (`/SkillrScan`, `/Skillr`) instead of sub-commands | Follows compound-engineering pattern; cleaner separation of concerns; fault isolation |
| Skills stored externally, scanned via userConfig | Allows users to use existing Skills without modifying them |
| SKILL.md as standard skill entry format | Aligns with Claude Code Plugin SDK |
| Python + uv + ty + ruff + pyproject.toml | Modern Python toolchain, fast iteration |
| Index stored at `${CLAUDE_PLUGIN_DATA}/index/` | Persistent across plugin updates, no user directory pollution |
| **mtime tiered strategy** | git-aware (git ls-files) > per-file mtime > per-dir mtime; catches edits reliably across NFS/USB/OS quirks |
| **No index size limit** | Index can hold any number of skills; `retrieval_window` protects LLM context |
| Lazy index rebuild via mtime check | No daemon needed, fast per-call check |
| Pure command string output (copy-paste execution) | Zero friction; user gets a command to copy-paste, not auto-execution |
| **LLM via CE main session** | Markdown Skill drives main session LLM; no sub-agent dispatch (SDK constraint: sub-agents cannot nest) |
| `intent.py` / `matcher.py` as prompt templates | Not sub-agent dispatch functions; main session LLM uses templates for IntentSpec + MatchResult |
| `userConfig.skills_dirs` as object type `{description, sensitive}` | Per SDK schema, not string array |
| JSON-only index (no SKILR_INDEX.md in MVP) | R7 only specifies JSON; Markdown index deferred to vector DB version |
| No independent triggers field | Description itself contains trigger semantics; simplified for MVP |
| **Simplified command output (MVP)** | All Skills output `/<name> <intent>`; bifurcation deferred |

### Technical Stack Confirmed

- **Language:** Python (MVP), Rust (future)
- **Package Manager:** uv
- **CLI Builder:** ty
- **Linter/Formatter:** ruff
- **Project Config:** pyproject.toml
- **LLM:** Claude Code built-in (SKILL.md drives main session; no sub-agent dispatch)
- **Skill Format:** SKILL.md with YAML frontmatter (name, description only — no triggers field)
- **Index:** JSON-only; `retrieval_window` for context overflow protection (no hard limit)

### Architecture Confirmed

```
skillr/                          # Skillr Plugin root
├── .claude-plugin/
│   └── plugin.json              # userConfig.skills_dirs
├── skills/
│   ├── skillrscan/
│   │   └── SKILL.md             # /SkillrScan entry
│   └── skillr/
│       └── SKILL.md             # /Skillr entry
├── src/skillr/
│   ├── scanner.py               # Directory scanning
│   ├── indexer.py               # Index generation
│   ├── models.py                # Data models (Pydantic)
│   ├── config.py                # Config handling
│   ├── router.py                # Main routing logic
│   ├── intent.py                # Intent analysis
│   └── matcher.py               # Keyword + LLM matching
└── pyproject.toml
```

### Deferred to Implementation

| Item | Reason |
|------|--------|
| LLM prompt template details | Need field testing to tune |
| Exact YAML parsing edge cases | Will discover through implementation |
| Vector database upgrade path | MVP-only; will be designed when needed |

### Open Questions (No Blocker)

1. **Python project layout details** — Exact directory structure under `src/skillr/` will be finalized during implementation
2. **LLM prompt tuning** — Will iterate based on actual usage
3. **Vector DB upgrade** — Design when business need is clear

### New Decisions This Session

| Decision | Rationale |
|----------|----------|
| Batch pagination: 4 results/batch, max 3 batches | Avoid information overload; clear "load more" pattern |
| "n" as fixed pagination option | Consistent UX: same key means same action across batches |
| Y/N confirmation before output | Users sometimes mis-select; one chance to correct |
| Slash/non-slash auto-routing | Non-slash skills (hermes agent) need "使用 xxx skill" format |
| No sub-commands for copy/refine | Auto-detection sufficient; no explicit user toggle needed |
| Session terminates after command output | IMPORTANT note in SKILL.md; LLM should not add follow-up |
| Command naming: lowercase `/skillr`, `/skillscan` | Consistency with Claude Code conventions |
| Removing session flow diagram | SKILL.md workflow is self-documenting |

## Previous Sessions

(None yet — this is the first session)
