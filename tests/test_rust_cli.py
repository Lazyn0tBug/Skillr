"""Integration tests for skillr-core Rust CLI binary.

These tests verify that the Rust binary correctly integrates with the Python
layer by testing the subprocess interface: scan -> index output, and
subsequent index-get reads back the same data.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# Path to the Rust release binary
RUST_BINARY = Path(__file__).parent.parent / "rust-scanner" / "target" / "release" / "skillr-core"


class TestRustBinaryExists:
    """Verify the Rust binary is built and accessible."""

    def test_rust_binary_exists(self):
        assert RUST_BINARY.exists(), f"Rust binary not found at {RUST_BINARY}"

    def test_rust_binary_runs(self):
        result = subprocess.run(
            [str(RUST_BINARY), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "skillr-core" in result.stdout


class TestScanSubcommand:
    """Test the scan subcommand that writes skillr_index.json."""

    def test_scan_empty_directory(self, tmp_path: Path):
        """scan on empty dir produces valid empty index."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()

        # Create the directory (Rust scan requires dir to exist, unlike Python fallback)
        empty_dir = tmp_path / "no-skills"
        empty_dir.mkdir()

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "scan",
                "--dir",
                str(empty_dir),
                "--plugin-data",
                str(plugin_data),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        index = json.loads(result.stdout)
        assert index["version"] == "1.0.0"
        assert index["skills"] == []
        assert index["skillsDirs"] == [str(empty_dir)]

    def test_scan_finds_skills(self, tmp_path: Path):
        """scan discovers SKILL.md files in subdirectories."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()

        # Create test skills
        skill_a = tmp_path / "skill-a"
        skill_a.mkdir()
        (skill_a / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: Skill A\n---\n\n# Skill A\n",
            encoding="utf-8",
        )
        skill_b = tmp_path / "skill-b"
        skill_b.mkdir()
        (skill_b / "SKILL.md").write_text(
            "---\nname: skill-b\ndescription: Skill B\n---\n\n# Skill B\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "scan",
                "--dir",
                str(tmp_path),
                "--plugin-data",
                str(plugin_data),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        index = json.loads(result.stdout)
        skill_names = {s["name"] for s in index["skills"]}
        assert "skill-a" in skill_names
        assert "skill-b" in skill_names
        # All skills should have hasSlashCommand defaulting to true
        for s in index["skills"]:
            assert s["hasSlashCommand"] is True

    def test_scan_writes_index_to_plugin_data(self, tmp_path: Path):
        """scan writes skillr_index.json to ${plugin-data}/index/."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()

        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                str(RUST_BINARY),
                "scan",
                "--dir",
                str(tmp_path),
                "--plugin-data",
                str(plugin_data),
            ],
            capture_output=True,
            text=True,
        )

        index_path = plugin_data / "index" / "skillr_index.json"
        assert index_path.exists(), f"Index not written to {index_path}"

        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["version"] == "1.0.0"
        assert len(index["skills"]) == 1
        assert index["skills"][0]["name"] == "test-skill"


class TestIndexGetSubcommand:
    """Test the index-get subcommand."""

    def test_index_get_returns_null_for_missing_file(self, tmp_path: Path):
        """index-get returns null when the index file does not exist."""
        result = subprocess.run(
            [
                str(RUST_BINARY),
                "index-get",
                "--index-path",
                str(tmp_path / "nonexistent.json"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "null"

    def test_index_get_returns_stored_index(self, tmp_path: Path):
        """index-get returns the previously stored index JSON."""
        index_data = {
            "version": "1.0.0",
            "generatedAt": "2026-04-22T00:00:00.000000",
            "skillsDirs": ["/tmp/skills"],
            "skills": [
                {
                    "name": "fetch-skill",
                    "description": "Web content fetching",
                    "filePath": "/tmp/skills/fetch-skill/SKILL.md",
                    "hasSlashCommand": True,
                }
            ],
            "sourceTracking": {},
            "retrievalWindow": 50,
        }
        index_path = tmp_path / "skillr_index.json"
        index_path.write_text(json.dumps(index_data), encoding="utf-8")

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "index-get",
                "--index-path",
                str(index_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        loaded = json.loads(result.stdout)
        assert loaded["version"] == "1.0.0"
        assert len(loaded["skills"]) == 1
        assert loaded["skills"][0]["name"] == "fetch-skill"


class TestConfigGetSubcommand:
    """Test the config-get subcommand."""

    def test_config_get_returns_defaults_for_missing_file(self, tmp_path: Path):
        """config-get returns default values when file does not exist."""
        result = subprocess.run(
            [
                str(RUST_BINARY),
                "config-get",
                "--config-path",
                str(tmp_path / "nonexistent.json"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        cfg = json.loads(result.stdout)
        assert cfg["embeddingBackend"] == "claude"
        assert cfg["cacheSecret"] is None

    def test_config_get_returns_stored_config(self, tmp_path: Path):
        """config-get returns the stored config JSON."""
        config_data = {
            "skillsDirs": [{"path": "/tmp/skills", "dirType": "mtime"}],
            "embeddingBackend": "model",
            "cacheSecret": "my-secret",
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "config-get",
                "--config-path",
                str(config_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        cfg = json.loads(result.stdout)
        assert cfg["embeddingBackend"] == "model"
        assert cfg["cacheSecret"] == "my-secret"


class TestCacheSubcommands:
    """Test cache-get and cache-set subcommands."""

    def test_cache_get_returns_empty_for_missing_file(self, tmp_path: Path):
        """cache-get with no file returns empty cache JSON."""
        config_data = {"skillsDirs": [], "embeddingBackend": "claude", "cacheSecret": "secret123"}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "cache-get",
                "--cache-path",
                str(tmp_path / "nonexistent.json"),
                "--config-path",
                str(config_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Should return empty entries with empty signature
        loaded = json.loads(result.stdout)
        assert loaded["entries"] == {}
        assert loaded["signature"] == ""

    def test_cache_set_signs_and_stores_entries(self, tmp_path: Path):
        """cache-set computes HMAC signature and stores the cache."""
        config_data = {
            "skillsDirs": [],
            "embeddingBackend": "claude",
            "cacheSecret": "test-secret-123",
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")
        cache_path = tmp_path / "intent_cache.json"

        payload = {
            "version": "1.0.0",
            "entries": {
                "intent-abc": {
                    "intentHash": "intent-abc",
                    "skillIdsHash": "ids-123",
                    "matchResults": [
                        {"name": "skilr", "score": 0.95, "matchReason": "exact match"}
                    ],
                    "createdAt": "2026-04-22T10:00:00.000000",
                    "ttlSeconds": 3600,
                }
            },
            "signature": "",
        }

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "cache-set",
                "--cache-path",
                str(cache_path),
                "--config-path",
                str(config_path),
                "--payload",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert cache_path.exists()

        # Verify the stored cache has a non-empty signature
        stored = json.loads(cache_path.read_text(encoding="utf-8"))
        assert stored["signature"] != ""
        assert len(stored["signature"]) == 64  # SHA256 hex = 64 chars

    def test_cache_get_verifies_signature_and_rejects_tampering(self, tmp_path: Path):
        """cache-get verifies HMAC and rejects tampered cache."""
        config_data = {
            "skillsDirs": [],
            "embeddingBackend": "claude",
            "cacheSecret": "test-secret-456",
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")
        cache_path = tmp_path / "intent_cache.json"

        # Write a cache with a bad signature
        bad_cache = {
            "version": "1.0.0",
            "entries": {
                "intent-xyz": {
                    "intentHash": "intent-xyz",
                    "skillIdsHash": "ids-789",
                    "matchResults": [],
                    "createdAt": "2026-04-22T11:00:00.000000",
                    "ttlSeconds": 7200,
                }
            },
            "signature": "bad_signature_value_that_should_fail",
        }
        cache_path.write_text(json.dumps(bad_cache), encoding="utf-8")

        result = subprocess.run(
            [
                str(RUST_BINARY),
                "cache-get",
                "--cache-path",
                str(cache_path),
                "--config-path",
                str(config_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2  # CacheSignatureMismatch exit code
        assert "tampered" in result.stderr.lower()


class TestScanAndIndexGetRoundTrip:
    """End-to-end round-trip: scan writes index, index-get reads it back."""

    def test_scan_output_matches_index_get_output(self, tmp_path: Path):
        """The JSON printed by scan is identical to what index-get returns."""
        plugin_data = tmp_path / "plugin_data"
        plugin_data.mkdir()

        skill_dir = tmp_path / "round-trip-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: round-trip-skill\ndescription: Testing round trip\n---\n\n# Round Trip\n",
            encoding="utf-8",
        )

        # Run scan
        scan_result = subprocess.run(
            [
                str(RUST_BINARY),
                "scan",
                "--dir",
                str(tmp_path),
                "--plugin-data",
                str(plugin_data),
            ],
            capture_output=True,
            text=True,
        )
        assert scan_result.returncode == 0
        scan_index = json.loads(scan_result.stdout)

        # Read via index-get
        index_path = plugin_data / "index" / "skillr_index.json"
        get_result = subprocess.run(
            [
                str(RUST_BINARY),
                "index-get",
                "--index-path",
                str(index_path),
            ],
            capture_output=True,
            text=True,
        )
        assert get_result.returncode == 0
        get_index = json.loads(get_result.stdout)

        assert get_index["version"] == scan_index["version"]
        assert get_index["skills"] == scan_index["skills"]
        assert get_index["skillsDirs"] == scan_index["skillsDirs"]
        assert get_index["retrievalWindow"] == scan_index["retrievalWindow"]
