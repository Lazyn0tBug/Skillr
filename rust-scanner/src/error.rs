//! Unified error types for skillr-core.

use thiserror::Error;

/// All errors that can occur in skillr-core operations.
#[derive(Error, Debug)]
#[allow(missing_docs)]
pub enum SkillrError {
    /// IO error wrapping std::io::Error.
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// JSON serialization/deserialization error.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// YAML parsing error.
    #[error("YAML error: {0}")]
    Yaml(#[from] serde_yaml::Error),

    /// UTF-8 conversion error.
    #[error("UTF-8 error: {0}")]
    Utf8(#[from] std::string::FromUtf8Error),

    /// WalkDir directory traversal error.
    #[error("WalkDir error: {0}")]
    WalkDir(#[from] walkdir::Error),

    /// HMAC initialization error (invalid key length).
    #[error("HMAC error: {0}")]
    Hmac(#[from] hmac::digest::InvalidLength),

    /// Cache HMAC signature mismatch — cache may be tampered.
    #[error("Cache HMAC signature mismatch — cache may be tampered")]
    CacheSignatureMismatch,

    /// Config file not found.
    #[error("Config not found at {0}")]
    ConfigNotFound(String),

    /// Index file not found.
    #[error("Index not found at {0}")]
    IndexNotFound(String),

    /// Invalid skills directory path.
    #[error("Invalid skill directory: {0}")]
    InvalidSkillDir(String),

    /// SKILL.md parse error.
    #[error("Parse error in {path}: {msg}")]
    ParseError { path: String, msg: String },
}

impl SkillrError {
    /// Exit code compatible with CLI.
    pub fn exit_code(&self) -> i32 {
        match self {
            SkillrError::Io(_) => 1,
            SkillrError::Json(_) => 1,
            SkillrError::Yaml(_) => 1,
            SkillrError::Utf8(_) => 1,
            SkillrError::Hmac(_) => 1,
            SkillrError::CacheSignatureMismatch => 2,
            SkillrError::ConfigNotFound(_) => 3,
            SkillrError::IndexNotFound(_) => 4,
            SkillrError::InvalidSkillDir(_) => 5,
            SkillrError::ParseError { .. } => 6,
            SkillrError::WalkDir(_) => 7,
        }
    }
}
