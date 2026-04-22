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

    let fm: SkillFrontmatter = serde_yaml::from_str(frontmatter)?;

    Ok(SkillMeta {
        name: fm.name,
        description: fm.description,
        file_path: path.to_path_buf(),
        has_slash_command: fm.has_slash_command.unwrap_or(true),
    })
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
}
