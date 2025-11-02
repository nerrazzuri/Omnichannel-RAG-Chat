# Redis Durability Policy

- Durable (AI-Core retry queue): AOF everysec enabled; survives restarts.
- Cache (Gateway rate-limit/temp): no persistence; allkeys-lru for performance.

Files:
- `config/redis/redis.conf` (durable)
- `config/redis/redis-cache.conf` (cache)

Validation:
1) Restart durable Redis; jobs persist.
2) Restart cache Redis; state rebuilt without errors.
3) Monitor AOF rewrite size and duration in Grafana.
