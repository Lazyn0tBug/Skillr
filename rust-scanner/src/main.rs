//! skillr-core — High-performance CLI binary for Skillr.
//!
//! Subcommands:
//!   scan       — Scan skills directories and write index
//!   cache-get  — Load and verify intent cache
//!   cache-set  — Save intent cache with HMAC signature
//!   config-get — Load config.json
//!   index-get  — Load skillr_index.json

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process;

use skillr_core::{cache, config, index, scan, IntentCache, SkillrError};

#[derive(Parser, Debug)]
#[command(name = "skillr-core")]
#[command(version = "0.1.8")]
#[command(about = "High-performance skill index scanner for Skillr")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Scan a skills directory and write skillr_index.json atomically.
    Scan {
        /// Path to the skills directory to scan.
        #[arg(long = "dir")]
        dir: PathBuf,

        /// Path to ${CLAUDE_PLUGIN_DATA} directory (for index output).
        #[arg(long = "plugin-data")]
        plugin_data: PathBuf,

        /// Source tracking type: "mtime" or "git".
        #[arg(long = "tracking", default_value = "mtime")]
        tracking: String,
    },

    /// Load and verify the intent cache.
    CacheGet {
        /// Path to intent_cache.json.
        #[arg(long = "cache-path")]
        cache_path: PathBuf,

        /// Path to config.json to read cache_secret.
        #[arg(long = "config-path")]
        config_path: PathBuf,
    },

    /// Save the intent cache with HMAC signature.
    CacheSet {
        /// Path to intent_cache.json to write.
        #[arg(long = "cache-path")]
        cache_path: PathBuf,

        /// Path to config.json to read cache_secret.
        #[arg(long = "config-path")]
        config_path: PathBuf,

        /// JSON payload to write (entire IntentCache object).
        #[arg(long = "payload")]
        payload: String,
    },

    /// Load config.json.
    ConfigGet {
        /// Path to config.json.
        #[arg(long = "config-path")]
        config_path: PathBuf,
    },

    /// Load skillr_index.json.
    IndexGet {
        /// Path to skillr_index.json.
        #[arg(long = "index-path")]
        index_path: PathBuf,
    },
}

fn main() {
    if let Err(e) = run() {
        eprintln!("ERROR: {}", e);
        process::exit(e.exit_code());
    }
}

fn run() -> Result<(), SkillrError> {
    let cli = Cli::parse();

    match cli.command {
        Command::Scan {
            dir,
            plugin_data,
            tracking: _,
        } => {
            // Scan the directory
            let scan_result = scan::scan_skills_dir(&dir)?;

            // Build index
            let index_path = plugin_data.join("index").join("skillr_index.json");
            let skillr_index = index::build_index(&[&dir], &[(dir.clone(), scan_result)], &Default::default());

            // Save atomically
            index::save_index(&skillr_index, &index_path)?;

            // Output JSON to stdout for verification
            let json = serde_json::to_string_pretty(&skillr_index).map_err(SkillrError::Json)?;
            println!("{}", json);
        }

        Command::CacheGet { cache_path, config_path } => {
            let cache = match cache::load_cache(&cache_path)? {
                Some(c) => c,
                None => {
                let empty = IntentCache {
                    version: "1.0.0".to_string(),
                    entries: Default::default(),
                    signature: String::new(),
                };
                println!("{}", serde_json::to_string_pretty(&empty).map_err(SkillrError::Json)?);
                return Ok(());
            }
            };

            // Verify signature if secret available
            let cfg = config::load_config(&config_path)?;
            if let Some(secret) = &cfg.cache_secret {
                if !cache::verify_cache_signature(&cache, secret)? {
                    return Err(SkillrError::CacheSignatureMismatch);
                }
            }

            let json = serde_json::to_string_pretty(&cache).map_err(SkillrError::Json)?;
            println!("{}", json);
        }

        Command::CacheSet {
            cache_path,
            config_path,
            payload,
        } => {
            let cfg = config::load_config(&config_path)?;
            let secret = cfg
                .cache_secret
                .ok_or_else(|| SkillrError::ConfigNotFound("cache_secret not set".to_string()))?;

            let cache: cache::IntentCache = serde_json::from_str(&payload).map_err(SkillrError::Json)?;
            cache::save_cache(&cache, &cache_path, &secret)?;
        }

        Command::ConfigGet { config_path } => {
            let cfg = config::load_config(&config_path)?;
            let json = serde_json::to_string_pretty(&cfg).map_err(SkillrError::Json)?;
            println!("{}", json);
        }

        Command::IndexGet { index_path } => {
            let idx = match index::load_index(&index_path)? {
                Some(i) => i,
                None => {
                    println!("null");
                    return Ok(());
                }
            };
            let json = serde_json::to_string_pretty(&idx).map_err(SkillrError::Json)?;
            println!("{}", json);
        }
    }

    Ok(())
}
