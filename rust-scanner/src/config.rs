//! Config file read/write for skillr-core CLI.
//!
//! Reads and writes ${CLAUDE_PLUGIN_DATA}/config.json.
//! Used to get embedding_backend, cache_secret, and skills_dirs.

use crate::error::SkillrError;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

/// The config.json file format.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PluginConfig {
    /// Path to skills directories.
    #[serde(default)]
    pub skills_dirs: Vec<SkillDirEntry>,

    /// Embedding backend: "claude" or "model"
    #[serde(default = "default_embedding_backend")]
    pub embedding_backend: String,

    /// Machine-specific HMAC secret for cache integrity (ADV-007)
    /// Generated once on first cache write.
    #[serde(default)]
    pub cache_secret: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkillDirEntry {
    pub path: String,
    #[serde(default = "default_dir_type")]
    pub dir_type: String,
}

fn default_embedding_backend() -> String {
    "claude".to_string()
}

fn default_dir_type() -> String {
    "mtime".to_string()
}

/// Load config from ${CLAUDE_PLUGIN_DATA}/config.json
pub fn load_config(config_path: &Path) -> Result<PluginConfig, SkillrError> {
    if !config_path.exists() {
        return Ok(PluginConfig {
            skills_dirs: vec![],
            embedding_backend: "claude".to_string(),
            cache_secret: None,
        });
    }

    let content = fs::read_to_string(config_path)?;
    let config: PluginConfig = serde_json::from_str(&content)?;
    Ok(config)
}

/// Save config to config.json atomically.
pub fn save_config(config: &PluginConfig, config_path: &Path) -> Result<(), SkillrError> {
    if let Some(parent) = config_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let tmp_path = config_path.with_extension("json.tmp");
    let json = serde_json::to_string_pretty(config)?;
    fs::write(&tmp_path, &json)?;
    let file = fs::OpenOptions::new().write(true).open(&tmp_path)?;
    file.sync_all()?;
    drop(file);
    fs::rename(&tmp_path, config_path)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn config_should_persist_across_save_and_load() {
        let tmp = TempDir::new().unwrap();
        let config_path = tmp.path().join("config.json");

        let config = PluginConfig {
            skills_dirs: vec![SkillDirEntry {
                path: "~/.claude/skills".to_string(),
                dir_type: "git".to_string(),
            }],
            embedding_backend: "model".to_string(),
            cache_secret: Some("my-secret".to_string()),
        };

        save_config(&config, &config_path).unwrap();
        let loaded = load_config(&config_path).unwrap();
        assert_eq!(loaded.embedding_backend, "model");
        assert_eq!(loaded.cache_secret, Some("my-secret".to_string()));
    }

    #[test]
    fn config_should_return_defaults_when_file_missing() {
        let tmp = TempDir::new().unwrap();
        let config_path = tmp.path().join("nonexistent.json");
        let loaded = load_config(&config_path).unwrap();
        assert_eq!(loaded.embedding_backend, "claude");
        assert!(loaded.cache_secret.is_none());
    }
}
