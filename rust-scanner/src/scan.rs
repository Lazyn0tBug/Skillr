//! Skill scanner — walks skills directories and parses SKILL.md files.
//!
//! A skill is expected at: `<skills_dir>/<skill_name>/SKILL.md`
//! with YAML frontmatter containing `name` and `description` fields.

use crate::error::SkillrError;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// A parsed skill from a SKILL.md file.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkillMeta {
    pub name: String,
    pub description: String,
    pub file_path: PathBuf,
    #[serde(default = "default_has_slash_command")]
    pub has_slash_command: bool,
}

fn default_has_slash_command() -> bool {
    true
}

/// YAML frontmatter extracted from a SKILL.md file.
#[derive(Debug, Deserialize)]
struct SkillFrontmatter {
    name: String,
    description: String,
    #[serde(default)]
    has_slash_command: Option<bool>,
}

/// Scanned skills from a single directory, plus per-file mtimes for change detection.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DirScanResult {
    pub skills: Vec<SkillMeta>,
    /// Map of skill_name -> file mtime (ISO string)
    pub file_mtimes: HashMap<String, String>,
}

/// Incremental scan: only parse files whose mtime has changed since last scan.
///
/// Returns a DirScanResult where unchanged skills are omitted from `skills`
/// but their mtime is preserved. The boolean indicates whether any change was detected.
pub fn scan_skills_dir_incremental(
    skills_dir: &Path,
    prev_mtimes: &HashMap<String, String>,
) -> Result<(DirScanResult, bool), SkillrError> {
    if !skills_dir.is_dir() {
        return Err(SkillrError::InvalidSkillDir(skills_dir.display().to_string()));
    }

    let mut skills = Vec::new();
    let mut file_mtimes = HashMap::new();
    let mut any_changed = false;

    for entry in WalkDir::new(skills_dir)
        .max_depth(2)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        if path.file_name().and_then(|n| n.to_str()) != Some("SKILL.md") {
            continue;
        }

        let skill_name = path
            .parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        if skill_name.is_empty() || skill_name.starts_with('.') {
            continue;
        }

        let mtime = entry.metadata()?.modified()?;
        let mtime_str = chrono::DateTime::<chrono::Utc>::from(mtime)
            .format("%Y-%m-%dT%H:%M:%S%.f")
            .to_string();
        file_mtimes.insert(skill_name.clone(), mtime_str.clone());

        // Check if this file has changed since last scan
        let prev_mtime = prev_mtimes.get(&skill_name);
        if prev_mtime == Some(&mtime_str) {
            // Unchanged — skip YAML parsing entirely
            continue;
        }

        // Changed — parse the file
        any_changed = true;
        match parse_skill_md(path) {
            Ok(skill) => skills.push(skill),
            Err(e) => {
                eprintln!("WARN: skipping {} due to parse error: {}", path.display(), e);
            }
        }
    }

    Ok((DirScanResult { skills, file_mtimes }, any_changed))
}

/// Scan a skills directory, recursively finding all SKILL.md files.
///
/// Returns skills and per-file mtimes for incremental tracking.
pub fn scan_skills_dir(skills_dir: &Path) -> Result<DirScanResult, SkillrError> {
    if !skills_dir.is_dir() {
        return Err(SkillrError::InvalidSkillDir(skills_dir.display().to_string()));
    }

    let mut skills = Vec::new();
    let mut file_mtimes = HashMap::new();

    for entry in WalkDir::new(skills_dir)
        .max_depth(2)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        if path.file_name().and_then(|n| n.to_str()) != Some("SKILL.md") {
            continue;
        }

        let skill_name = path
            .parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        if skill_name.is_empty() || skill_name.starts_with('.') {
            continue;
        }

        let mtime = entry.metadata()?.modified()?;
        let mtime_str = chrono::DateTime::<chrono::Utc>::from(mtime)
            .format("%Y-%m-%dT%H:%M:%S%.f")
            .to_string();
        file_mtimes.insert(skill_name.clone(), mtime_str);

        match parse_skill_md(path) {
            Ok(skill) => skills.push(skill),
            Err(e) => {
                eprintln!("WARN: skipping {} due to parse error: {}", path.display(), e);
            }
        }
    }

    Ok(DirScanResult { skills, file_mtimes })
}

/// Parse a SKILL.md file, extracting YAML frontmatter.
///
/// Uses fast line-scanning instead of full YAML parser for the 3 fixed fields:
/// `name`, `description`, and `has_slash_command`. Falls back to serde_yaml
/// if the simple parser fails.
pub fn parse_skill_md(path: &Path) -> Result<SkillMeta, SkillrError> {
    let content = fs::read_to_string(path)?;

    let frontmatter = content
        .strip_prefix("---\n")
        .or_else(|| content.strip_prefix("---\r\n"))
        .and_then(|rest| rest.find("\n---\n").or_else(|| rest.find("\n---\r\n")).map(|idx| &rest[..idx]))
        .ok_or_else(|| SkillrError::ParseError {
            path: path.display().to_string(),
            msg: "Missing YAML frontmatter delimiters".to_string(),
        })?;

    // Fast path: extract name + description via line scan (avoids serde_yaml overhead)
    if let Some((name, description, has_slash)) = extract_frontmatter_fast(frontmatter) {
        return Ok(SkillMeta {
            name: name.to_string(),
            description: description.to_string(),
            file_path: path.to_path_buf(),
            has_slash_command: has_slash,
        });
    }

    // Fallback: full YAML parser
    let fm: SkillFrontmatter = serde_yaml::from_str(frontmatter)?;

    Ok(SkillMeta {
        name: fm.name,
        description: fm.description,
        file_path: path.to_path_buf(),
        has_slash_command: fm.has_slash_command.unwrap_or(true),
    })
}

/// Fast frontmatter extraction via O(n) line scan.
///
/// Only parses the 3 fields we care about: `name`, `description`, `has_slash_command`.
/// Returns None if any required field is missing (triggers serde_yaml fallback).
fn extract_frontmatter_fast(frontmatter: &str) -> Option<(&str, &str, bool)> {
    let mut name: Option<&str> = None;
    let mut description: Option<&str> = None;
    let mut has_slash_command = true;

    for line in frontmatter.lines() {
        let line = line.trim();
        if let Some(val) = line.strip_prefix("name:") {
            let val = val.trim();
            if !val.is_empty() && !val.starts_with('[') && !val.starts_with('{') {
                name = Some(val);
            }
        } else if let Some(val) = line.strip_prefix("description:") {
            let val = val.trim();
            if !val.is_empty() && !val.starts_with('[') && !val.starts_with('{') {
                description = Some(val);
            }
        } else if let Some(val) = line.strip_prefix("has_slash_command:") {
            let val = val.trim();
            has_slash_command = val == "true" || val == "yes" || val == "1";
        }
    }

    let name = name?;
    let description = description?;

    // Sanity check: both fields should be reasonable length
    if name.len() > 200 || description.len() > 5000 {
        return None;
    }

    Some((name, description, has_slash_command))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn create_temp_skill(dir: &Path, name: &str, description: &str) -> PathBuf {
        let skill_dir = dir.join(name);
        std::fs::create_dir_all(&skill_dir).unwrap();
        let md_path = skill_dir.join("SKILL.md");
        let content = format!(
            "---\nname: {}\ndescription: {}\n---\n# {}\n",
            name, description, name
        );
        std::fs::write(&md_path, content).unwrap();
        md_path
    }

    #[test]
    fn scan_skills_dir_should_find_skills_recursively() {
        let tmp = TempDir::new().unwrap();
        create_temp_skill(tmp.path(), "drawio", "Draw diagrams");
        create_temp_skill(tmp.path(), "miro", "Collaborative whiteboard");

        let result = scan_skills_dir(tmp.path()).unwrap();
        assert_eq!(result.skills.len(), 2);
        assert!(result.file_mtimes.contains_key("drawio"));
        assert!(result.file_mtimes.contains_key("miro"));
    }

    #[test]
    fn parse_skill_md_should_extract_frontmatter() {
        let tmp = TempDir::new().unwrap();
        let path = create_temp_skill(tmp.path(), "test-skill", "A test skill");
        let skill = parse_skill_md(&path).unwrap();
        assert_eq!(skill.name, "test-skill");
        assert_eq!(skill.description, "A test skill");
        assert!(skill.has_slash_command);
    }

    #[test]
    fn scan_skills_dir_should_return_empty_for_empty_directory() {
        let tmp = TempDir::new().unwrap();
        let result = scan_skills_dir(tmp.path()).unwrap();
        assert!(result.skills.is_empty());
        assert!(result.file_mtimes.is_empty());
    }

    #[test]
    fn incremental_scan_should_skip_unchanged_files() {
        let tmp = TempDir::new().unwrap();
        create_temp_skill(tmp.path(), "skill-a", "Skill A");
        create_temp_skill(tmp.path(), "skill-b", "Skill B");

        // First scan to get mtimes
        let result = scan_skills_dir(tmp.path()).unwrap();
        let prev_mtimes = result.file_mtimes;

        // Second scan with same mtimes — nothing should be parsed
        let (result2, any_changed) =
            scan_skills_dir_incremental(tmp.path(), &prev_mtimes).unwrap();
        assert!(!any_changed);
        assert!(result2.skills.is_empty()); // unchanged skills omitted
        assert_eq!(result2.file_mtimes.len(), 2); // but mtimes still tracked
    }

    #[test]
    fn incremental_scan_should_parse_changed_files() {
        use std::time::Duration;
        let tmp = TempDir::new().unwrap();
        let path = create_temp_skill(tmp.path(), "skill-x", "Original desc");

        // First scan
        let result = scan_skills_dir(tmp.path()).unwrap();
        let prev_mtimes = result.file_mtimes;

        // Touch to change mtime
        std::thread::sleep(Duration::from_millis(10));
        std::fs::write(
            &path,
            "---\nname: skill-x\ndescription: Updated desc\n---\n# Updated\n",
        )
        .unwrap();

        let (result2, any_changed) =
            scan_skills_dir_incremental(tmp.path(), &prev_mtimes).unwrap();
        assert!(any_changed);
        assert_eq!(result2.skills.len(), 1);
        assert_eq!(result2.skills[0].description, "Updated desc");
    }

    #[test]
    fn fast_frontmatter_parser_should_handle_standard_fields() {
        let tmp = TempDir::new().unwrap();
        let path = create_temp_skill(tmp.path(), "test-skill", "A test skill");
        let skill = parse_skill_md(&path).unwrap();
        assert_eq!(skill.name, "test-skill");
        assert_eq!(skill.description, "A test skill");
        assert!(skill.has_slash_command);
    }

    #[test]
    fn fast_frontmatter_parser_should_handle_has_slash_false() {
        let tmp = TempDir::new().unwrap();
        let skill_dir = tmp.path().join("no-slash");
        std::fs::create_dir_all(&skill_dir).unwrap();
        let md_path = skill_dir.join("SKILL.md");
        std::fs::write(
            &md_path,
            "---\nname: no-slash\ndescription: No slash\nhas_slash_command: false\n---\n# No\n",
        )
        .unwrap();
        let skill = parse_skill_md(&md_path).unwrap();
        assert!(!skill.has_slash_command);
    }
}
