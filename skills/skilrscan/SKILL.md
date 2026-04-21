---
name: SkillrScan
description: "Scan configured skills_dirs directories and rebuild the Skillr index (skillr_index.json). Run this once after adding or updating Skills, or when index staleness is suspected."
---

# SkillrScan — Scan Skills and Rebuild Index

Skillr helps you find the right Skill and assemble executable command suggestions.

## Usage

Invoke this Skill to scan your configured Skills directories and rebuild the `skillr_index.json` index.

**No arguments required.**

## Workflow

Skillr will:
1. Read `skills_dirs` from plugin userConfig
2. Expand `~` paths using `pathlib.Path.expanduser()`
3. Traverse each skills_dir — find subdirectories containing `SKILL.md`
4. Parse each `SKILL.md` YAML frontmatter to extract `name` and `description`
5. Generate `skillr_index.json` with Skill metadata and tiered mtime tracking info
6. Save the index to `${CLAUDE_PLUGIN_DATA}/index/`

## Output

After scanning, Skillr outputs a summary:

```
✅ 扫描完成，共发现 N 个 Skills
  - /path/to/skills_dir1: M 个 Skills
  - /path/to/skills_dir2: K 个 Skills
索引已保存至: ${CLAUDE_PLUGIN_DATA}/index/skillr_index.json
```

## mtime Tracking Strategy

The scanner uses a tiered approach to detect changes:
- **Tier 1 (git-aware)**: If skills_dir is a git repo, uses `git ls-files --others --modified` compared against stored commit hash
- **Tier 2 (per-file)**: For non-git directories, records each `SKILL.md` file's mtime
- **Tier 3 (per-dir)**: Falls back to parent directory mtime as a last resort

## Error Handling

- Missing `SKILL.md` in a subdirectory → skips with a warning
- Malformed YAML frontmatter → skips with a warning, continues scanning
- skills_dir does not exist → reports warning, skips that directory
- No read permission → reports error, skips
