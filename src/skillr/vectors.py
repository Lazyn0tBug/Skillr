"""Vector embedding store for semantic skill search using ONNX + ChromaDB."""

from __future__ import annotations

from pathlib import Path

import chromadb
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from .config import ensure_plugin_data_dir
from .models import SkillMeta


class EmbeddingStore:
    """ONNX embedding + ChromaDB vector store for skills.

    Uses BAAI/bge-small-zh-v1.5 (ONNX) for embeddings, stored in ChromaDB.
    Falls back to no-op when unavailable.
    """

    MODEL_DIR = Path("~/.cache/fastembed/fast-bge-small-zh-v1.5").expanduser()
    COLLECTION_NAME = "skill_embeddings"
    DIM = 512  # bge-small-zh-v1.5 embedding dimension

    def __init__(self) -> None:
        self._available: bool = False
        self._session: ort.InferenceSession | None = None
        self._tokenizer: AutoTokenizer | None = None
        self._chroma_client: chromadb.Client | None = None
        self._collection: chromadb.Collection | None = None
        self._try_init()

    def _try_init(self) -> None:
        """Initialize embedding model and ChromaDB. Silent failure = unavailable."""
        try:
            # Load ONNX model and tokenizer from local cache
            self._tokenizer = AutoTokenizer.from_pretrained(
                str(self.MODEL_DIR), local_files_only=True
            )
            self._session = ort.InferenceSession(str(self.MODEL_DIR / "model_optimized.onnx"))
        except Exception:
            return  # Not available

        try:
            data_dir = ensure_plugin_data_dir() / "vectors"
            data_dir.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(data_dir))
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        """True if embedding store is initialized and ready."""
        return self._available

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for a list of texts using ONNX model.

        Returns ndarray of shape (len(texts), DIM).
        """
        if self._session is None or self._tokenizer is None:
            raise RuntimeError("Embedding store not available")

        inputs = self._tokenizer(
            texts,
            return_tensors="np",
            padding=True,
            truncation=True,
            max_length=512,
        )
        # ONNX expects int64
        ort_inputs = {
            k: v.astype(np.int64) if v.dtype == np.int32 else v for k, v in inputs.items()
        }
        outputs = self._session.run(None, ort_inputs)
        # outputs[0]: (batch, seq_len, hidden) → mean pool → (batch, DIM)
        return outputs[0].mean(axis=1)

    def add_skill(self, skill_id: str, description: str) -> None:
        """Add or update a skill's description embedding."""
        if not self._available or self._collection is None:
            return
        embedding = self._embed_texts([description])[0]
        self._collection.upsert(
            ids=[skill_id],
            embeddings=[embedding.tolist()],
            documents=[description],
        )

    def search(self, intent_text: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Search top-k skills by semantic similarity to intent_text.

        Returns list of (skill_id, cosine_score) sorted by score descending.
        """
        if not self._available or self._collection is None:
            return []

        query_embedding = self._embed_texts([intent_text])[0]
        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=["distances"],
        )

        skill_ids: list[str] = results["ids"][0]
        distances: list[float] = results["distances"][0]  # ChromaDB uses L2 distance

        # Convert L2 distance to cosine similarity (approximate for normalized vectors)
        # cosine ≈ 1 - (l2² / 2) for normalized vectors
        # For BGE embeddings (already relatively normalized): cosine ≈ 1 - l2²/2
        cosine_scores: list[tuple[str, float]] = []
        for sid, dist in zip(skill_ids, distances):
            cosine = max(0.0, 1.0 - (dist**2) / 2.0)
            cosine_scores.append((sid, round(cosine, 4)))

        # Sort by score descending
        cosine_scores.sort(key=lambda x: x[1], reverse=True)
        return cosine_scores

    def clear(self) -> None:
        """Delete all embeddings (called before rebuilding the index)."""
        if not self._available or self._collection is None:
            return
        try:
            self._chroma_client.delete_collection(name=self.COLLECTION_NAME)
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            # If delete fails, recreate client
            self._try_init()

    def rebuild_from_skills(self, skills: list[SkillMeta]) -> None:
        """Clear and repopulate the vector store from a list of SkillMeta."""
        self.clear()
        for skill in skills:
            self.add_skill(skill.name, skill.description)
