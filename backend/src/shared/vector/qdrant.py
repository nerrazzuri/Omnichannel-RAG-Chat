"""
Qdrant vector database service for document embeddings and similarity search.
"""
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np
import logging

logger = logging.getLogger(__name__)

class QdrantService:
    """Qdrant vector database service with tenant isolation."""

    def __init__(self, url: str = "http://localhost:6333", api_key: Optional[str] = None):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = "knowledge_chunks"

    def create_collection(self) -> None:
        """Create the knowledge chunks collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")

                # Create payload index for tenant filtering
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_schema="keyword"
                )
                logger.info("Created tenant_id payload index")
            else:
                logger.info(f"Collection {self.collection_name} already exists")

        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            raise

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
                        "metadata": chunk.get("metadata", {})
                    }
                )
                points.append(point)

            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Upserted {len(points)} knowledge chunks for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Failed to upsert knowledge chunks for tenant {tenant_id}: {e}")
            raise

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
            search_results = self.client.search(
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

            self.client.delete(
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
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "name": collection_info.name,
                "vectors_count": collection_info.points_count,
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"status": "error", "error": str(e)}

# Global vector service instance
qdrant_service = QdrantService()
