"""Vector store of historical resolved faults, backed by ChromaDB."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import chromadb

from . import config
from .embeddings import Embedder, get_embedder


@dataclass
class SimilarFault:
    id: int
    title: str
    category: str
    severity: str
    device_name: str
    root_cause: str
    resolution: str
    similarity: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def document_text(record: dict) -> str:
    """Text that gets embedded. Symptoms carry the most weight because new
    tickets only describe symptoms; the root cause adds useful vocabulary."""
    return f"{record['title']}. {record['description']}. Root cause: {record['root_cause']}"


class KnowledgeBase:
    def __init__(self, embedder: Embedder | None = None, persist_dir: Path | None = None):
        self.embedder = embedder or get_embedder()
        if persist_dir:
            client = chromadb.PersistentClient(path=str(persist_dir))
        else:
            client = chromadb.EphemeralClient()
        # One collection per embedder, so switching backends never mixes vector spaces.
        name = f"{config.COLLECTION}_{self.embedder.name.replace('/', '_')}"[:60]
        self._client = client
        self._collection_name = name
        self.collection = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})

    @classmethod
    def from_history(cls, path: Path = config.HISTORY_PATH, **kwargs) -> "KnowledgeBase":
        kb = cls(**kwargs)
        if kb.collection.count() == 0:
            kb.add(json.loads(Path(path).read_text()))
        return kb

    def add(self, records: list[dict]) -> int:
        if not records:
            return 0
        self.collection.upsert(
            ids=[str(r["id"]) for r in records],
            embeddings=self.embedder.embed([document_text(r) for r in records]),
            documents=[document_text(r) for r in records],
            metadatas=[
                {k: r[k] for k in ("id", "title", "category", "severity", "device_name",
                                   "root_cause", "resolution")}
                for r in records
            ],
        )
        return len(records)

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self.collection = self._client.get_or_create_collection(
            self._collection_name, metadata={"hnsw:space": "cosine"})

    def count(self) -> int:
        return self.collection.count()

    def search(self, query: str, k: int = 5, category: str | None = None) -> list[SimilarFault]:
        if not query.strip():
            return []
        result = self.collection.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=min(k, max(self.count(), 1)),
            where={"category": category} if category else None,
        )
        matches = []
        for meta, distance in zip(result["metadatas"][0], result["distances"][0]):
            matches.append(SimilarFault(
                id=int(meta["id"]), title=meta["title"], category=meta["category"],
                severity=meta["severity"], device_name=meta["device_name"],
                root_cause=meta["root_cause"], resolution=meta["resolution"],
                similarity=round(1 - distance, 4),
            ))
        return matches
