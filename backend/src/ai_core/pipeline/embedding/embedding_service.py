from typing import List, Optional

import os
from openai import OpenAI
from shared.security.secret_manager import secret_manager

from shared.cache.redis import redis_cache
from shared.config.tuning import retrieval, cost as cost_cfg
from shared.utils.retry import retry_with_backoff
from shared.utils.circuit_breaker import circuit_breaker
from shared.queue.retry_queue import retry_queue
from shared.metrics.cost_metrics import cost_metrics
from shared.metrics.cost_aggregator import rolling_cost
from shared.throttling.quota import throttle
from shared.config.tuning import retries
import hashlib
import logging


class EmbeddingService:
    def __init__(self) -> None:
        api_key = secret_manager.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = getattr(retrieval, 'embedding_model', os.getenv("RAG_EMBED_MODEL", "text-embedding-3-large"))

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        return f"emb:{self.model}:{digest}"

    def embed_query(self, query: str, tenant_id: str) -> Optional[List[float]]:
        if not query or not self.client:
            return None
        k = self._cache_key(query)
        cached = redis_cache.get_tenant_key(tenant_id, k)
        if isinstance(cached, list):
            try:
                cost_metrics.hit(tenant_id, "emb")
            except Exception:
                pass
            return cached
        else:
            try:
                cost_metrics.miss(tenant_id, "emb")
            except Exception:
                pass

        if not circuit_breaker.allow("openai_embed", tenant_id):
            # Degrade to None, let caller choose fallback
            return None

        # Throttling
        try:
            # TODO: optionally load tenant tier from DB if available; default BASIC
            ok = throttle.acquire(tenant_id, kind="embed", tenant_tier=None)
            if not ok:
                return None
        except Exception:
            pass

        @retry_with_backoff("openai.embed")
        def _do_embed() -> Optional[List[float]]:
            resp = self.client.embeddings.create(model=self.model, input=[query])
            vec = resp.data[0].embedding if resp and resp.data else None
            # Token/cost accounting (OpenAI embeds may not return usage; estimate)
            try:
                usage = getattr(resp, 'usage', None)
                ptoks = int(getattr(usage, 'prompt_tokens', 0) or 0)
            except Exception:
                # rough estimate
                ptoks = int(len(query)/4)
            m = self.model
            in_rate = float(cost_cfg.model_in_usd_per_1k.get(m, cost_cfg.model_in_usd_per_1k.get("default", 0.0001)))
            usd = (ptoks/1000.0)*in_rate
            cost_metrics.record_tokens(tenant_id, m, "embed", ptoks, 0, usd)
            rolling_cost.add(tenant_id, m, "embed", ptoks, 0, usd)
            return vec if isinstance(vec, list) else None

        try:
            vec = _do_embed()
            if vec:
                redis_cache.set_tenant_key(tenant_id, k, vec, ttl=1800)
                circuit_breaker.record_success("openai_embed", tenant_id)
                try:
                    throttle.release(tenant_id, kind="embed")
                except Exception:
                    pass
                return vec
            # No vec -> treat as failure path
            circuit_breaker.record_failure("openai_embed", tenant_id)
        except Exception as e:  # noqa: BLE001
            circuit_breaker.record_failure("openai_embed", tenant_id)
            # enqueue for async retry (best-effort)
            if hasattr(retries, "queue_enabled") and retries.queue_enabled:
                try:
                    retry_queue.enqueue(
                        job_type="embed_query",
                        tenant_id=tenant_id,
                        payload={"query": query, "model": self.model},
                        last_error=str(e),
                    )
                except Exception:
                    pass
        finally:
            try:
                throttle.release(tenant_id, kind="embed")
        except Exception as e:
            logging.getLogger(__name__).exception("[embedding.throttle_release] error", extra={"tenant_id": tenant_id})
        return None


