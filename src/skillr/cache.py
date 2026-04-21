"""Disk-persistent intent cache for Skillr matching results."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime

from .config import ensure_plugin_data_dir
from .models import IntentCache, IntentCacheEntry, MatchResult


class IntentCacheStore:
    """Disk-persistent cache for intent matching results with TTL and invalidation."""

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache_path = ensure_plugin_data_dir() / "cache" / "intent_cache.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Create the cache directory if it doesn't exist."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> IntentCache:
        """Load the cache from disk, creating empty cache if file doesn't exist."""
        if not self._cache_path.exists():
            return IntentCache()

        try:
            with open(self._cache_path) as f:
                data = json.load(f)
            return IntentCache.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError):
            # Corrupted cache — remove and return empty
            self._remove_cache()
            return IntentCache()

    def _save_cache(self, cache: IntentCache) -> None:
        """Write the cache to disk atomically."""
        # Write to temp file then rename for atomicity
        tmp_path = self._cache_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(cache.model_dump(), f, indent=2)
        tmp_path.rename(self._cache_path)

    def _remove_cache(self) -> None:
        """Remove the corrupted cache file."""
        if self._cache_path.exists():
            self._cache_path.unlink()

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
                # Expired — remove entry
                del cache.entries[intent_hash]
                self._save_cache(cache)
                return None
        except ValueError:
            # Invalid timestamp — treat as expired
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
