"""Tests for E3 vector embedding store."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillr.models import SkillMeta
from skillr.vectors import EmbeddingStore


class TestEmbeddingStore:
    """Test EmbeddingStore with mocked dependencies."""

    def setup_method(self):
        """Reset the router module-level vector store singleton before each test."""
        import skillr.router as router_module

        router_module._vector_store = None

    def test_health_check_available(self, mocker):
        """Store reports available when ONNX and ChromaDB initialize successfully."""
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()
        mock_chroma = mocker.MagicMock()
        mock_collection = mocker.MagicMock()

        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session
        store._tokenizer = mock_tokenizer
        store._chroma_client = mock_chroma
        store._collection = mock_collection

        assert store.available is True

    def test_add_and_search_returns_results(self, mocker):
        """Adding skills and searching returns relevant matches."""
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()
        mock_chroma = mocker.MagicMock()
        mock_collection = mocker.MagicMock()

        # Simulate embedding output: (1, seq, 512) mean → (1, 512)
        import numpy as np

        mock_session.run.return_value = [np.random.randn(2, 8, 512).mean(axis=1)]
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((2, 8), dtype=np.int64),
            "attention_mask": np.ones((2, 8), dtype=np.int64),
        }
        mock_collection.query.return_value = {
            "ids": [["auth-skill", "backend-skill"]],
            "distances": [[0.1, 0.3]],
        }

        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session
        store._tokenizer = mock_tokenizer
        store._chroma_client = mock_chroma
        store._collection = mock_collection

        store.add_skill("auth-skill", "用户认证和登录管理")
        store.add_skill("backend-skill", "FastAPI 后端开发")

        results = store.search("我想做用户认证系统", top_k=5)

        assert len(results) == 2
        names = [r[0] for r in results]
        assert "auth-skill" in names
        assert "backend-skill" in names

    def test_search_returns_top_k(self, mocker):
        """Search returns at most top_k results."""
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()
        mock_chroma = mocker.MagicMock()
        mock_collection = mocker.MagicMock()

        import numpy as np

        mock_session.run.return_value = [np.random.randn(3, 8, 512).mean(axis=1)]
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((3, 8), dtype=np.int64),
            "attention_mask": np.ones((3, 8), dtype=np.int64),
        }
        # ChromaDB query returns n_results items (respects top_k)
        mock_collection.query.return_value = {
            "ids": [["a", "b"]],
            "distances": [[0.1, 0.2]],
        }

        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session
        store._tokenizer = mock_tokenizer
        store._chroma_client = mock_chroma
        store._collection = mock_collection

        results = store.search("test intent", top_k=2)

        assert len(results) == 2

    def test_fallback_when_unavailable(self, mocker):
        """When vector store unavailable, filter returns original skills list."""
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()

        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session  # but search raises
        store._tokenizer = mock_tokenizer

        # Simulate search failure
        mock_session.run.side_effect = Exception("ONNX runtime error")

        skills = [
            SkillMeta(
                name="a", description="desc a", file_path=Path("/a.md"), has_slash_command=True
            ),
            SkillMeta(
                name="b", description="desc b", file_path=Path("/b.md"), has_slash_command=True
            ),
        ]

        from skillr.router import filter_by_intent_vector

        result = filter_by_intent_vector("test", skills, top_k=5)
        assert result == skills

    def test_filter_returns_top_k_from_vector(self, mocker):
        """filter_by_intent_vector returns only top_k results from vector search."""
        import numpy as np

        # Create fully-mocked store with pre-set available state
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()
        mock_chroma = mocker.MagicMock()
        mock_collection = mocker.MagicMock()

        # search() calls embed_texts once with [intent_text] → shape (1, 512)
        mock_session.run.return_value = [np.random.randn(1, 8, 512).mean(axis=1)]
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((1, 8), dtype=np.int64),
            "attention_mask": np.ones((1, 8), dtype=np.int64),
        }
        mock_collection.query.return_value = {
            "ids": [["skill-a", "skill-b", "skill-c"]],
            "distances": [[0.05, 0.15, 0.25]],
        }

        # Patch _try_init to be a no-op, then manually set _available
        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session
        store._tokenizer = mock_tokenizer
        store._chroma_client = mock_chroma
        store._collection = mock_collection

        # Override _get_vector_store to return our pre-built mock store
        import skillr.router as router_module

        router_module._vector_store = store

        # Patch get_embedding_backend to return "model" so vector path is exercised
        mocker.patch("skillr.config.get_embedding_backend", return_value="model")

        from skillr.router import filter_by_intent_vector

        skills = [
            SkillMeta(
                name="skill-a",
                description="desc a",
                file_path=Path("/a.md"),
                has_slash_command=True,
            ),
            SkillMeta(
                name="skill-b",
                description="desc b",
                file_path=Path("/b.md"),
                has_slash_command=True,
            ),
            SkillMeta(
                name="skill-c",
                description="desc c",
                file_path=Path("/c.md"),
                has_slash_command=True,
            ),
            SkillMeta(
                name="skill-d",
                description="desc d",
                file_path=Path("/d.md"),
                has_slash_command=True,
            ),
            SkillMeta(
                name="skill-e",
                description="desc e",
                file_path=Path("/e.md"),
                has_slash_command=True,
            ),
        ]

        result = filter_by_intent_vector("test intent", skills, top_k=3)
        assert len(result) == 3
        # First 3 should be the vector-matched ones
        assert result[0].name == "skill-a"
        assert result[1].name == "skill-b"
        assert result[2].name == "skill-c"


class TestCosineConversion:
    """Test L2 distance to cosine similarity conversion."""

    def test_cosine_conversion(self, mocker):
        """Distance-to-cosine conversion produces valid scores."""
        mock_session = mocker.MagicMock()
        mock_tokenizer = mocker.MagicMock()
        mock_chroma = mocker.MagicMock()
        mock_collection = mocker.MagicMock()

        import numpy as np

        mock_session.run.return_value = [np.random.randn(2, 8, 512).mean(axis=1)]
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((2, 8), dtype=np.int64),
            "attention_mask": np.ones((2, 8), dtype=np.int64),
        }
        # L2 distance = 0 means identical → cosine = 1
        mock_collection.query.return_value = {
            "ids": [["same", "different"]],
            "distances": [[0.0, 1.414]],  # 0 L2 = cos 1, sqrt(2) L2 ≈ cos 0
        }

        mocker.patch.object(EmbeddingStore, "_try_init", lambda self: None)
        store = EmbeddingStore.__new__(EmbeddingStore)
        store._available = True
        store._session = mock_session
        store._tokenizer = mock_tokenizer
        store._chroma_client = mock_chroma
        store._collection = mock_collection

        results = store.search("test", top_k=2)
        scores = {name: score for name, score in results}

        assert scores["same"] == pytest.approx(1.0, abs=0.01)
        assert scores["different"] < scores["same"]
