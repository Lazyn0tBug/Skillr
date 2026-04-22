//! Index builder and persistence for Skillr.
//!
//! Builds a SkillrIndex from scanned skills and writes it atomically.
//! Uses std::fs::rename for atomic replace (POSIX rename is atomic).

use crate::error::SkillrError;
use crate::scan::{DirScanResult, SkillMeta};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

/// Source tracking for incremental index rebuilds.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "type")]
pub enum SourceTracking {
    Git {
        value: String,  // git commit hash
        #[serde(default)]
        file_mtimes: HashMap<String, String>,
    },
    Mtime {
        value: String,  // ISO timestamp of directory mtime
        #[serde(default)]
        file_mtimes: HashMap<String, String>,
    },
}

/// The full Skillr index — written to ${CLAUDE_PLUGIN_DATA}/index/skillr_index.json
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkillrIndex {
    pub version: String,
    pub generated_at: String,
    pub skills_dirs: Vec<String>,
    pub skills: Vec<SkillMeta>,
    #[serde(default)]
    pub source_tracking: HashMap<String, SourceTracking>,
    #[serde(default = "default_retrieval_window")]
    pub retrieval_window: usize,
}

fn default_retrieval_window() -> usize {
    50
}

/// Build a SkillrIndex from scan results across all configured skills directories.
pub fn build_index(
    skills_dirs: &[&Path],
    all_scan_results: &[(PathBuf, DirScanResult)],
    tracking: &HashMap<String, SourceTracking>,
) -> SkillrIndex {
    let all_skills: Vec<SkillMeta> = all_scan_results
        .iter()
        .flat_map(|(_, r)| r.skills.clone())
        .collect();

    SkillrIndex {
        version: "1.0.0".to_string(),
        generated_at: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%S%.f").to_string(),
        skills_dirs: skills_dirs.iter().map(|p| p.display().to_string()).collect(),
        skills: all_skills,
        source_tracking: tracking.clone(),
        retrieval_window: 50,
    }
}

/// Save the index atomically: write to .tmp then rename.
/// This is atomic on POSIX (the rename syscall is atomic).
pub fn save_index(index: &SkillrIndex, index_path: &Path) -> Result<(), SkillrError> {
    // Ensure parent directory exists
    if let Some(parent) = index_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let tmp_path = index_path.with_extension("json.tmp");
    let json = serde_json::to_string(index)?;
    
    // Write to temp file
    fs::write(&tmp_path, &json)?;
    
    // Flush and sync (best-effort durability)
    let file = fs::OpenOptions::new().write(true).open(&tmp_path)?;
    file.sync_all()?;
    drop(file);

    // Atomic rename — this is the critical ADV-001 fix
    fs::rename(&tmp_path, index_path)?;

    Ok(())
}

/// Load the index from disk, or return None if not found.
pub fn load_index(index_path: &Path) -> Result<Option<SkillrIndex>, SkillrError> {
    if !index_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(index_path)?;
    let index: SkillrIndex = serde_json::from_str(&content)?;
    Ok(Some(index))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn make_index() -> SkillrIndex {
        SkillrIndex {
            version: "1.0.0".to_string(),
            generated_at: "2026-04-22T00:00:00".to_string(),
            skills_dirs: vec!["/tmp/skills".to_string()],
            skills: vec![],
            source_tracking: HashMap::new(),
            retrieval_window: 50,
        }
    }

    #[test]
    fn index_should_persist_across_save_and_load() {
        let tmp = TempDir::new().unwrap();
        let index_path = tmp.path().join("skillr_index.json");
        let index = make_index();

        save_index(&index, &index_path).unwrap();
        assert!(index_path.exists());

        let loaded = load_index(&index_path).unwrap().unwrap();
        assert_eq!(loaded.version, "1.0.0");
    }

    #[test]
    fn load_index_should_return_none_when_file_missing() {
        let tmp = TempDir::new().unwrap();
        let index_path = tmp.path().join("nonexistent.json");
        let loaded = load_index(&index_path).unwrap();
        assert!(loaded.is_none());
    }
}
