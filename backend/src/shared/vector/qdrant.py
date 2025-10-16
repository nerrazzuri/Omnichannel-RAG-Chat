"""
Qdrant vector database service for document embeddings and similarity search.
"""
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np
import logging
import time
import os
from shared.config.settings import settings

logger = logging.getLogger(__name__)

class QdrantService:
    """Qdrant vector database service with tenant isolation."""

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        qdrant_url = url or settings.qdrant_url
        qdrant_api_key = api_key or settings.qdrant_api_key
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = "knowledge_chunks"

    def _with_retries(self, func, *args, **kwargs):
        attempts = int(os.getenv("QDRANT_RETRIES", "10"))
        delay = float(os.getenv("QDRANT_RETRY_DELAY", "1.0"))
        last_exc: Optional[Exception] = None
        for _ in range(attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                time.sleep(delay)
        if last_exc:
            raise last_exc
        return None

    def create_collection(self) -> None:
        """Create the knowledge chunks collection if it doesn't exist."""
        try:
            # Check if collection exists (with retries while Qdrant warms up)
            collections = self._with_retries(self.client.get_collections)
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self._with_retries(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")

                # Create payload index for tenant filtering
                self._with_retries(
                    self.client.create_payload_index,
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_schema="keyword"
                )
                logger.info("Created tenant_id payload index")
                # Create payload indices for chapter metadata to speed chapter queries
                try:
                    self._with_retries(
                        self.client.create_payload_index,
                        collection_name=self.collection_name,
                        field_name="chapter_num",
                        field_schema="integer"
                    )
                    self._with_retries(
                        self.client.create_payload_index,
                        collection_name=self.collection_name,
                        field_name="chapter_title",
                        field_schema="text"
                    )
                    logger.info("Created chapter_num and chapter_title payload indices")
                except Exception as ie:
                    logger.warning(f"Chapter payload index creation skipped: {ie}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")

        except Exception as e:
            # Degrade gracefully; caller may retry later
            logger.warning(f"Failed to create Qdrant collection (will retry later): {e}")

    def upsert_knowledge_chunks(self, tenant_id: str, chunks: List[Dict[str, Any]]) -> None:
        """Upsert knowledge chunks for a specific tenant."""
        try:
            points = []
            for chunk in chunks:
                point = PointStruct(
                    id=chunk["id"],
                    vector=chunk["embedding"],
                    payload={
                        "tenant_id": tenant_id,
                        "document_id": chunk["document_id"],
                        "content": chunk["content"],
                        "chunk_index": chunk["chunk_index"],
                        # include structured fields if present
                        "chapter_num": chunk.get("chapter_num"),
                        "chapter_title": chunk.get("chapter_title"),
                        "page": chunk.get("page"),
                        # retain any nested metadata
                        "metadata": chunk.get("metadata", {})
                    }
                )
                points.append(point)

            if points:
                self._with_retries(
                    self.client.upsert,
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Upserted {len(points)} knowledge chunks for tenant {tenant_id}")

        except Exception as e:
            # Degrade gracefully; embeddings remain available in SQL, upsert can be retried later
            logger.warning(f"Failed to upsert knowledge chunks for tenant {tenant_id} (will retry later): {e}")

    def search_similar_chunks(
        self,
        query_embedding: List[float],
        tenant_id: str,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar knowledge chunks within a tenant."""
        try:
            # Create filter for tenant isolation
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    )
                ]
            )

            # Search with filter
            search_results = self._with_retries(
                self.client.search,
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=top_k,
                score_threshold=threshold
            )

            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                })

            logger.info(f"Found {len(results)} similar chunks for tenant {tenant_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar chunks for tenant {tenant_id}: {e}")
            return []

    def delete_tenant_chunks(self, tenant_id: str) -> bool:
        """Delete all knowledge chunks for a specific tenant."""
        try:
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    )
                ]
            )

            self._with_retries(
                self.client.delete,
                collection_name=self.collection_name,
                points_selector=filter_condition
            )

            logger.info(f"Deleted all knowledge chunks for tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks for tenant {tenant_id}: {e}")
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the knowledge chunks collection."""
        try:
            collection_info = self._with_retries(self.client.get_collection, self.collection_name)
            return {
                "name": collection_info.name,
                "vectors_count": collection_info.points_count,
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"status": "error", "error": str(e)}

    def list_chapters(self, tenant_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Return points that have chapter_num or chapter_title for a tenant.

        Uses scroll to page through limited results. Best-effort; returns empty on error.
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, HasIdCondition
            collected: List[Dict[str, Any]] = []
            next_page = None
            fetched = 0
            while fetched < limit:
                response = self._with_retries(
                    self.client.scroll,
                    collection_name=self.collection_name,
                    scroll_filter=Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]),
                    with_payload=True,
                    with_vectors=False,
                    limit=min(256, limit - fetched),
                    offset=next_page
                )
                if not response or not response[0]:
                    break
                points, next_page = response
                for p in points:
                    pl = p.payload or {}
                    if (pl.get("chapter_num") is not None) or (pl.get("chapter_title")):
                        collected.append(pl)
                fetched += len(points)
                if not next_page:
                    break
            return collected
        except Exception as e:
            logger.warning(f"list_chapters failed: {e}")
            return []

# Global vector service instance (configured via environment settings)
qdrant_service = QdrantService()
