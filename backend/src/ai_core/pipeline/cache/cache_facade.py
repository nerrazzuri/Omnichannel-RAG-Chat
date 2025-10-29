from typing import Optional, Any

from shared.cache.redis import redis_cache


class PipelineCache:
    """Thin cache facade to store retrieval/rerank artifacts per tenant+query hash."""

    def _key(self, tenant_id: str, scope: str, query: str) -> str:
        return f"pipeline:{scope}:{tenant_id}:{hash(query)}"

    def get(self, tenant_id: str, scope: str, query: str) -> Optional[Any]:
        try:
            return redis_cache.get_tenant_key(tenant_id, self._key(tenant_id, scope, query))
        except Exception:
            return None

    def set(self, tenant_id: str, scope: str, query: str, value: Any, ttl: int = 600) -> None:
        try:
            redis_cache.set_tenant_key(tenant_id, self._key(tenant_id, scope, query), value, ttl=ttl)
        except Exception:
            pass


