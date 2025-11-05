# Observability & SLOs (13.0-D)

## SLOs & SLIs

- Availability: 1 - (error_rate) per plan_type
- Latency p95: histogram_quantile over ai_core_latency_seconds_bucket per plan_type
- Error Rate: ai_core_error_total / ai_core_requests_total
- Data Freshness: time since last backup success (or connector sync)
- Cost Guard: token usage vs plan quota

## Metrics (labels include tenant_id and plan_type)

- AI-Core: ai_core_requests_total, ai_core_latency_seconds, ai_core_error_total, ai_core_tokens_total
- Gateway: gateway_requests_total, gateway_latency_seconds, gateway_rate_limit_exceeded_total
- Connectors: connector_sync_total, connector_sync_failures_total, connector_duration_seconds

## Dashboards

- Executive Overview, Service Health, Tenant Health, SLO Compliance

## Alerts

- See observability/prometheus/rules/slo-core.yaml

## CI/CD Gates

- Burn rate > 2 blocks production deploy; availability below target blocks deploy


