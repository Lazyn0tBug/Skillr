//! skillr-core library crate.
//!
//! Re-exports all modules for use by the binary.

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

#[allow(missing_docs)]
pub mod cache;
#[allow(missing_docs)]
pub mod config;
#[allow(missing_docs)]
pub mod error;
#[allow(missing_docs)]
pub mod index;
#[allow(missing_docs)]
pub mod scan;

pub use error::SkillrError;
pub use cache::IntentCache;
