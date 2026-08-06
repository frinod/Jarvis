"""JARVIS OS - Vector Memory Store using Qdrant"""
from __future__ import annotations
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid

from app.memory.manager import MemoryEntry, MemoryStore, MemoryType


class VectorMemoryStore(MemoryStore):
    COLLECTION = "jarvis_memory"

    def __init__(self, qdrant_url: str, embedding_model: str = "all-MiniLM-L6-v2"):
        self.client = QdrantClient(url=qdrant_url)
        self.encoder = SentenceTransformer(embedding_model)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in collections:
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(
                    size=self.encoder.get_sentence_embedding_dimension(),
                    distance=Distance.COSINE
                )
            )

    async def store(self, entry: MemoryEntry) -> str:
        embedding = self.encoder.encode(entry.content).tolist()
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[PointStruct(
                id=entry.id,
                vector=embedding,
                payload={
                    "content": entry.content,
                    "type": entry.type.value,
                    "importance": entry.importance,
                    "timestamp": entry.timestamp.isoformat(),
                    "metadata": entry.metadata,
                    "tags": entry.tags
                }
            )]
        )
        return entry.id

    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        embedding = self.encoder.encode(query).tolist()
        results = self.client.search(
            collection_name=self.COLLECTION,
            query_vector=embedding,
            limit=top_k
        )
        return [self._point_to_entry(r) for r in results]

    async def search_by_type(self, mem_type: MemoryType, limit: int = 10) -> List[MemoryEntry]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        results = self.client.scroll(
            collection_name=self.COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="type", match=MatchValue(value=mem_type.value))
            ]),
            limit=limit
        )
        return [self._point_to_entry(r) for r in results[0]]

    def _point_to_entry(self, point) -> MemoryEntry:
        p = point.payload if hasattr(point, 'payload') else point
        from datetime import datetime
        return MemoryEntry(
            id=str(point.id) if hasattr(point, 'id') else str(uuid.uuid4()),
            type=MemoryType(p["type"]),
            content=p["content"],
            metadata=p.get("metadata", {}),
            importance=p.get("importance", 0.5),
            timestamp=datetime.fromisoformat(p["timestamp"]),
            tags=p.get("tags", [])
        )
