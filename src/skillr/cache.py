"""Disk-persistent intent cache for Skillr matching results."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from .config import ensure_plugin_data_dir, get_cache_secret
from .models import IntentCache, IntentCacheEntry, MatchResult


def _pydantic_encoder(obj):
    """JSON encoder that handles Pydantic models and datetime."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class IntentCacheStore:
    """Disk-persistent cache for intent matching results with TTL, HMAC integrity, and invalidation.

    Security (ADV-007):
        Cache entries are signed with HMAC-SHA256 using a machine-specific secret.
        On load, any tampering (poisoning, corruption) causes the cache to be discarded.
        The signature protects against other users on shared systems modifying the cache.

    Atomicity (ADV-001):
        Writes use write-to-tmp + rename. On load, orphaned .tmp files are cleaned up
        so crash during rename does not permanently corrupt the cache.
    """

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache_path = ensure_plugin_data_dir() / "cache" / "intent_cache.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Create the cache directory if it doesn't exist."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    # === Signature helpers ===

    def _sign_entries(self, entries: dict[str, IntentCacheEntry]) -> str:
        """Compute HMAC-SHA256 signature of cache entries dict."""
        secret = get_cache_secret()
        # Canonical JSON: sort_keys ensures deterministic serialization for HMAC
        entries_json = json.dumps(entries, sort_keys=True, default=_pydantic_encoder)
        return hmac.new(secret.encode(), entries_json.encode(), hashlib.sha256).hexdigest()

    def _verify_signature(self, entries: dict[str, IntentCacheEntry], signature: str) -> bool:
        """Verify entries match the stored HMAC signature.

        Empty signature means pre-fix cache (v1.0.0 before ADV-007) — treat as valid.
        """
        if not signature:
            return True  # Pre-existing cache without signature — trust it
        expected = self._sign_entries(entries)
        return hmac.compare_digest(expected, signature)

    # === Load / Save ===

    def _load_cache(self) -> IntentCache:
        """Load the cache from disk, creating empty cache if file doesn't exist."""
        tmp_path = self._cache_path.with_suffix(".tmp")

        # ADV-001: Clean up orphaned .tmp from interrupted write.
        # After a successful rename, .tmp no longer exists. If .tmp exists, the
        # previous write's rename failed — but .json may still be valid.
        # - If .json doesn't exist: remove orphaned .tmp, start fresh.
        # - If .json exists: .tmp is a leftover from a failed rename, remove .tmp only.
        if tmp_path.exists():
            if not self._cache_path.exists():
                tmp_path.unlink()
            else:
                tmp_path.unlink()

        if not self._cache_path.exists():
            return IntentCache()

        try:
            with open(self._cache_path) as f:
                data = json.load(f)
            cache = IntentCache.model_validate(data)
        except (OSError, json.JSONDecodeError, ValidationError):
            self._remove_cache()
            return IntentCache()

        # ADV-007: Verify HMAC signature — discard if tampered
        if not self._verify_signature(cache.entries, cache.signature):
            self._remove_cache()
            return IntentCache()

        return cache

    def _save_cache(self, cache: IntentCache) -> None:
        """Write the cache to disk atomically with fsync for durability."""
        # ADV-007: Sign entries before writing
        cache.signature = self._sign_entries(cache.entries)

        tmp_path = self._cache_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(cache.model_dump(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.rename(self._cache_path)

    def _remove_cache(self) -> None:
        """Remove the corrupted cache file."""
        if self._cache_path.exists():
            self._cache_path.unlink()

    # === Public API ===

    @staticmethod
    def hash_intent(intent: str) -> str:
        """Return SHA256 hash of intent text."""
        return hashlib.sha256(intent.encode()).hexdigest()

    @staticmethod
    def hash_skill_ids(skill_ids: list[str]) -> str:
        """Return SHA256 hash of sorted skill IDs."""
        sorted_ids = sorted(skill_ids)
        combined = ",".join(sorted_ids).encode()
        return hashlib.sha256(combined).hexdigest()

    def get(
        self,
        intent_hash: str,
        skill_ids_hash: str,
    ) -> list[MatchResult] | None:
        """Look up cached match results if they exist and haven't expired.

        Returns None if:
        - Entry doesn't exist
        - Entry has expired (TTL exceeded)
        - skill_ids_hash doesn't match (skills changed)
        - Cache HMAC signature invalid (tampering detected)
        """
        cache = self._load_cache()
        entry = cache.entries.get(intent_hash)

        if entry is None:
            return None

        # Check TTL
        try:
            created = datetime.fromisoformat(entry.created_at)
            age_seconds = time.time() - created.timestamp()
            if age_seconds > entry.ttl_seconds:
                del cache.entries[intent_hash]
                self._save_cache(cache)
                return None
        except ValueError:
            del cache.entries[intent_hash]
            self._save_cache(cache)
            return None

        # Check skill IDs match
        if entry.skill_ids_hash != skill_ids_hash:
            return None

        return entry.match_results

    def set(
        self,
        intent_hash: str,
        skill_ids_hash: str,
        match_results: list[MatchResult],
    ) -> None:
        """Store match results in the cache."""
        cache = self._load_cache()

        now = datetime.now(UTC).isoformat()
        entry = IntentCacheEntry(
            intent_hash=intent_hash,
            skill_ids_hash=skill_ids_hash,
            match_results=match_results,
            created_at=now,
            ttl_seconds=self.ttl_seconds,
        )
        cache.entries[intent_hash] = entry
        self._save_cache(cache)

    def invalidate_by_skill_ids(self, skill_ids_hash: str) -> None:
        """Remove all cache entries whose skill_ids_hash matches (skill content changed)."""
        cache = self._load_cache()
        to_remove = [
            h for h, entry in cache.entries.items() if entry.skill_ids_hash == skill_ids_hash
        ]
        for h in to_remove:
            del cache.entries[h]

        if to_remove:
            self._save_cache(cache)

    def invalidate_all(self) -> None:
        """Remove all cache entries (ADV-006: index rebuild invalidates all cache).

        Called from run_indexer() after any index rebuild — skill set or content
        may have changed, making all cached match results potentially stale.
        """
        cache = self._load_cache()
        if cache.entries:
            cache.entries = {}
            self._save_cache(cache)
