# Redis Pressure (Evictions)

- Impact: Cache misses spike; latency up.
- Immediate: Increase memory or reduce key TTLs; inspect top keys.
- Long-term: Right-size memory; add partitions for workloads.
- Dashboard: Redis Overview.
