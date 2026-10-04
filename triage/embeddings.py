"""Text embedding backends.

- SentenceTransformerEmbedder: semantic embeddings (all-MiniLM-L6-v2). Recommended.
- HashingEmbedder: dependency-light fallback that works fully offline. It uses
  hashed word n-grams plus character n-grams, so it still matches related wording.
"""
from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

from . import config

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    name = "hashing"

    def __init__(self, n_features: int = 2**12):
        from sklearn.feature_extraction.text import HashingVectorizer

        self._word = HashingVectorizer(
            n_features=n_features, ngram_range=(1, 2), stop_words="english",
            alternate_sign=False, norm=None,
        )
        self._char = HashingVectorizer(
            n_features=n_features, analyzer="char_wb", ngram_range=(3, 5),
            alternate_sign=False, norm=None,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        word = self._word.transform(texts).toarray()
        char = self._char.transform(texts).toarray()
        vec = np.hstack([np.log1p(word) * 2.0, np.log1p(char)])
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vec / norms).tolist()


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.name = f"sentence-transformers/{model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def get_embedder(backend: str = config.EMBEDDING_BACKEND) -> Embedder:
    if backend in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder()
        except Exception as exc:  # not installed or model download blocked
            if backend == "sentence-transformers":
                raise
            log.warning("sentence-transformers unavailable (%s); using hashing embedder", exc)
    return HashingEmbedder()
