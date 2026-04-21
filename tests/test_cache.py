"""Tests for IntentCacheStore (E1 result cache)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from skillr.cache import IntentCacheStore
from skillr.models import MatchResult


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_path = tmp_path / "cache" / "intent_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def store(cache_dir: Path) -> IntentCacheStore:
    """Create a cache store with mocked plugin data dir."""
    with patch.object(IntentCacheStore, "__init__", lambda self, ttl=3600: None):
        store = IntentCacheStore.__new__(IntentCacheStore)
        store.ttl_seconds = 3600
        store._cache_path = cache_dir / "cache" / "intent_cache.json"
        store._cache_path.parent.mkdir(parents=True, exist_ok=True)
        return store


class TestIntentCacheStore:
    """Test IntentCacheStore basic operations."""

    def test_set_and_get(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """Cache hit returns stored match results."""
        results = [
            MatchResult(name="test-skill", score=0.9, match_reason="exact match"),
        ]

        intent_hash = IntentCacheStore.hash_intent("build a fastapi project")
        skill_ids_hash = IntentCacheStore.hash_skill_ids(["test-skill"])

        store.set(intent_hash, skill_ids_hash, results)
        cached = store.get(intent_hash, skill_ids_hash)

        assert cached is not None
        assert len(cached) == 1
        assert cached[0].name == "test-skill"
        assert cached[0].score == 0.9

    def test_cache_miss_returns_none(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """Cache miss returns None (no LLM call)."""
        intent_hash = IntentCacheStore.hash_intent("some random task")
        skill_ids_hash = IntentCacheStore.hash_skill_ids(["skill-a"])

        cached = store.get(intent_hash, skill_ids_hash)
        assert cached is None

    def test_ttl_expiry(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """Expired TTL causes cache miss."""
        # Set TTL to 1 second
        store.ttl_seconds = 1

        results = [MatchResult(name="skill", score=0.8, match_reason="test")]
        intent_hash = IntentCacheStore.hash_intent("task")
        skill_ids_hash = IntentCacheStore.hash_skill_ids(["skill"])

        store.set(intent_hash, skill_ids_hash, results)

        # Wait for TTL to expire
        time.sleep(1.1)

        cached = store.get(intent_hash, skill_ids_hash)
        assert cached is None

    def test_skill_change_invalidates(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """New skill IDs hash causes cache miss (skills changed)."""
        results = [MatchResult(name="skill-a", score=0.9, match_reason="test")]

        intent_hash = IntentCacheStore.hash_intent("task")
        skill_ids_hash_old = IntentCacheStore.hash_skill_ids(["skill-a"])

        store.set(intent_hash, skill_ids_hash_old, results)

        # New skill set
        skill_ids_hash_new = IntentCacheStore.hash_skill_ids(["skill-a", "skill-b"])
        cached = store.get(intent_hash, skill_ids_hash_new)
        assert cached is None

    def test_corrupted_cache_falls_back(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """Corrupted cache file returns empty cache (no crash)."""
        # Write garbage
        store._cache_path.write_text("not valid json {{{")

        # Should not raise — falls back to empty cache
        cached = store.get("any", "any")
        assert cached is None

    def test_persistence_across_restarts(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """Cache persists and is readable after store recreation."""
        results = [MatchResult(name="persist-skill", score=0.95, match_reason="stays")]

        intent_hash = IntentCacheStore.hash_intent("persistent task")
        skill_ids_hash = IntentCacheStore.hash_skill_ids(["persist-skill"])

        store.set(intent_hash, skill_ids_hash, results)

        # Create new store instance (simulating restart)
        with patch.object(IntentCacheStore, "__init__", lambda self, ttl=3600: None):
            store2 = IntentCacheStore.__new__(IntentCacheStore)
            store2.ttl_seconds = 3600
            store2._cache_path = cache_dir / "cache" / "intent_cache.json"

        cached = store2.get(intent_hash, skill_ids_hash)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].name == "persist-skill"

    def test_invalidate_by_skill_ids(
        self,
        store: IntentCacheStore,
        cache_dir: Path,
    ) -> None:
        """invalidate_by_skill_ids removes all matching entries."""
        intent_hash_1 = IntentCacheStore.hash_intent("task 1")
        intent_hash_2 = IntentCacheStore.hash_intent("task 2")
        skill_ids_hash = IntentCacheStore.hash_skill_ids(["skill-a"])

        store.set(
            intent_hash_1, skill_ids_hash, [MatchResult(name="s1", score=0.9, match_reason="r1")]
        )
        store.set(
            intent_hash_2, skill_ids_hash, [MatchResult(name="s2", score=0.8, match_reason="r2")]
        )

        # Invalidate by skill hash
        store.invalidate_by_skill_ids(skill_ids_hash)

        # Both entries should be gone
        assert store.get(intent_hash_1, skill_ids_hash) is None
        assert store.get(intent_hash_2, skill_ids_hash) is None


class TestHashFunctions:
    """Test hash utility functions."""

    def test_hash_intent_deterministic(self) -> None:
        """Same intent produces same hash."""
        h1 = IntentCacheStore.hash_intent("build fastapi auth")
        h2 = IntentCacheStore.hash_intent("build fastapi auth")
        assert h1 == h2

    def test_hash_intent_different_for_different_tasks(self) -> None:
        """Different intents produce different hashes."""
        h1 = IntentCacheStore.hash_intent("task a")
        h2 = IntentCacheStore.hash_intent("task b")
        assert h1 != h2

    def test_hash_skill_ids_order_independent(self) -> None:
        """['a', 'b'] and ['b', 'a'] produce same hash."""
        h1 = IntentCacheStore.hash_skill_ids(["a", "b"])
        h2 = IntentCacheStore.hash_skill_ids(["b", "a"])
        assert h1 == h2

    def test_hash_skill_ids_empty_list(self) -> None:
        """Empty skill list produces a valid hash."""
        h = IntentCacheStore.hash_skill_ids([])
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex length
