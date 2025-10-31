from __future__ import annotations

from prometheus_client import Counter, Gauge


class _MemoryMetrics:
    def __init__(self) -> None:
        self._entries_total = Counter("ai_core_memory_entries_total", "Memory entries appended", ["tenant"]) 
        self._summary_ops_total = Counter("ai_core_memory_summary_ops_total", "Memory summarization operations", ["tenant"]) 
        self._cleanup_total = Counter("ai_core_memory_cleanup_total", "Memory cleanup deletions", ["tenant"]) 

    def inc_entries(self, tenant_id: str) -> None:
        self._entries_total.labels(tenant=tenant_id).inc()

    def inc_summary_ops(self, tenant_id: str) -> None:
        self._summary_ops_total.labels(tenant=tenant_id).inc()

    def add_cleanup(self, tenant_id: str, count: int) -> None:
        # record count via inc with repeated increments
        for _ in range(max(0, int(count))):
            self._cleanup_total.labels(tenant=tenant_id).inc()


memory_metrics = _MemoryMetrics()


