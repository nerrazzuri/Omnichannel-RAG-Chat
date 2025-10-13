"""
Redis cache configuration and utilities.
"""
import json
import pickle
from typing import Any, Optional, Union
from redis import Redis
from redis.cluster import RedisCluster
from redis.exceptions import ConnectionError
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache service with tenant isolation."""

    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.url = url
        self._client: Optional[Union[Redis, RedisCluster]] = None

    def get_client(self) -> Union[Redis, RedisCluster]:
        """Get or create Redis client."""
        if self._client is None:
            try:
                # Try cluster first
                self._client = RedisCluster.from_url(self.url)
                logger.info("Connected to Redis Cluster")
            except Exception:
                # Fall back to single instance
                self._client = Redis.from_url(self.url)
                logger.info("Connected to Redis single instance")

        return self._client

    def set_tenant_key(self, tenant_id: str, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set a tenant-specific cache key."""
        try:
            tenant_key = f"tenant:{tenant_id}:{key}"
            serialized_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            return self.get_client().setex(tenant_key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Failed to set cache key {key} for tenant {tenant_id}: {e}")
            return False

    def get_tenant_key(self, tenant_id: str, key: str) -> Optional[Any]:
        """Get a tenant-specific cache key."""
        try:
            tenant_key = f"tenant:{tenant_id}:{key}"
            value = self.get_client().get(tenant_key)
            if value is None:
                return None

            # Try to parse as JSON, fall back to string
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.decode('utf-8') if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"Failed to get cache key {key} for tenant {tenant_id}: {e}")
            return None

    def delete_tenant_key(self, tenant_id: str, key: str) -> bool:
        """Delete a tenant-specific cache key."""
        try:
            tenant_key = f"tenant:{tenant_id}:{key}"
            return bool(self.get_client().delete(tenant_key))
        except Exception as e:
            logger.error(f"Failed to delete cache key {key} for tenant {tenant_id}: {e}")
            return False

    def clear_tenant_cache(self, tenant_id: str) -> bool:
        """Clear all cache keys for a specific tenant."""
        try:
            client = self.get_client()
            pattern = f"tenant:{tenant_id}:*"
            keys = client.keys(pattern)

            if keys:
                return bool(client.delete(*keys))

            return True
        except Exception as e:
            logger.error(f"Failed to clear cache for tenant {tenant_id}: {e}")
            return False

    def set_session(self, session_id: str, data: dict, ttl: int = 1800) -> bool:
        """Set session data."""
        try:
            session_key = f"session:{session_id}"
            return self.get_client().setex(session_key, ttl, json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to set session {session_id}: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        try:
            session_key = f"session:{session_id}"
            data = self.get_client().get(session_key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete session data."""
        try:
            session_key = f"session:{session_id}"
            return bool(self.get_client().delete(session_key))
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return bool(self.get_client().ping())
        except Exception:
            return False

# Global cache instance
redis_cache = RedisCache()
