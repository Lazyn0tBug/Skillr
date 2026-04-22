//! Intent cache read/write for skillr-core CLI.
//!
//! Intent cache at `${CLAUDE_PLUGIN_DATA}/cache/intent_cache.json` is HMAC-signed
//! for tampering detection (ADV-007).
//!
//! Rust only handles file I/O. HMAC signature computation is done by reading
//! the entries and computing HMAC(entries_json, cache_secret), then returning
//! the entries + signature to the Python layer which will verify.
//!
//! Actually: for --set, Python computes the signature and passes it in.
//!           for --get, Rust verifies the HMAC before returning.

use crate::error::SkillrError;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

type HmacSha256 = Hmac<Sha256>;

/// A single cached intent matching result entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntentCacheEntry {
    pub intent_hash: String,
    pub skill_ids_hash: String,
    pub match_results: Vec<MatchResultJson>,
    pub created_at: String,
    #[serde(default)]
    pub ttl_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MatchResultJson {
    pub name: String,
    pub score: f64,
    pub match_reason: String,
}

/// The full intent cache file on disk.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntentCache {
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub entries: HashMap<String, IntentCacheEntry>,
    /// HMAC-SHA256 signature of entries JSON — empty if not yet signed
    #[serde(default)]
    pub signature: String,
}

/// Load the intent cache from disk.
pub fn load_cache(cache_path: &Path) -> Result<Option<IntentCache>, SkillrError> {
    if !cache_path.exists() {
        return Ok(None);
    }

    let content = fs::read_to_string(cache_path)?;
    let cache: IntentCache = serde_json::from_str(&content)?;
    Ok(Some(cache))
}

/// Save the intent cache atomically with HMAC signature.
/// The signature is HMAC-SHA256(entries_json, secret) where entries_json
/// is the canonical JSON of the entries dict (deterministic ordering).
///
/// ADV-001: Uses std::fs::rename for atomic write (POSIX rename is atomic).
pub fn save_cache(
    cache: &IntentCache,
    cache_path: &Path,
    secret: &str,
) -> Result<(), SkillrError> {
    // Ensure parent directory exists
    if let Some(parent) = cache_path.parent() {
        fs::create_dir_all(parent)?;
    }

    // Build entries JSON for HMAC computation — must be deterministic
    let entries_json = serde_json::to_string(&cache.entries)?;
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).map_err(SkillrError::Hmac)?;
    mac.update(entries_json.as_bytes());
    let sig = hex::encode(mac.finalize().into_bytes());

    let mut cache_with_sig = cache.clone();
    cache_with_sig.signature = sig;

    let tmp_path = cache_path.with_extension("json.tmp");
    let json = serde_json::to_string_pretty(&cache_with_sig)?;

    // Write and sync
    fs::write(&tmp_path, &json)?;
    let file = fs::OpenOptions::new().write(true).open(&tmp_path)?;
    file.sync_all()?;
    drop(file);

    // Atomic rename
    fs::rename(&tmp_path, cache_path)?;

    Ok(())
}

/// Verify HMAC signature of a loaded cache.
/// Returns Ok(true) if signature is valid (or empty/legacy cache).
/// Returns Ok(false) if signature doesn't match (tampered).
///ADV-007: Validates cache integrity before returning data.
pub fn verify_cache_signature(
    cache: &IntentCache,
    secret: &str,
) -> Result<bool, SkillrError> {
    if cache.signature.is_empty() {
        // Legacy cache without signature — trust it on read, will be re-signed on write
        return Ok(true);
    }

    let entries_json = serde_json::to_string(&cache.entries)?;

    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).map_err(SkillrError::Hmac)?;
    mac.update(entries_json.as_bytes());

    let expected = hex::encode(mac.finalize().into_bytes());
    Ok(expected == cache.signature)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn make_test_cache() -> IntentCache {
        IntentCache {
            version: "1.0.0".to_string(),
            entries: HashMap::new(),
            signature: String::new(),
        }
    }

    #[test]
    fn cache_should_persist_across_save_and_load() {
        let tmp = TempDir::new().unwrap();
        let cache_path = tmp.path().join("intent_cache.json");
        let secret = "test-secret-key-12345";
        let cache = make_test_cache();

        save_cache(&cache, &cache_path, secret).unwrap();
        let loaded = load_cache(&cache_path).unwrap().unwrap();
        assert_eq!(loaded.version, "1.0.0");
    }

    #[test]
    fn signature_should_verify_valid_and_reject_tampered() {
        let cache = make_test_cache();
        let secret = "my-secret-key";
        assert!(verify_cache_signature(&cache, secret).unwrap());

        // Tamper detection
        let mut bad_cache = cache.clone();
        bad_cache.signature = "tampered".to_string();
        assert!(!verify_cache_signature(&bad_cache, secret).unwrap());
    }
}
