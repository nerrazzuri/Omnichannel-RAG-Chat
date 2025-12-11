import { Counter } from 'prom-client';

export const requestsTotal = new Counter({
  name: 'gateway_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['path', 'method', 'status', 'plan_type', 'domain_type'] as const,
});

export const rateLimitHits = new Counter({
  name: 'gateway_rate_limit_hits_total',
  help: 'Rate limit hits',
  labelNames: ['path', 'plan_type'] as const,
});

export const rateLimitExceeded = new Counter({
  name: 'gateway_rate_limit_exceeded_total',
  help: 'Rate limit exceeded events',
  labelNames: ['plan_type'] as const,
});

export const queueEnqueued = new Counter({
  name: 'gateway_queue_enqueued_total',
  help: 'Webhook jobs enqueued',
});

export const queueFailed = new Counter({
  name: 'gateway_queue_failed_total',
  help: 'Webhook enqueue failures',
});

export const queueDLQ = new Counter({
  name: 'gateway_queue_dlq_total',
  help: 'Webhook jobs moved to DLQ',
});

export const customDomainRequests = new Counter({
  name: 'custom_domain_requests_total',
  help: 'Requests served via custom domains',
  labelNames: ['host', 'tenant_id'] as const,
});

export const customDomainErrors = new Counter({
  name: 'custom_domain_errors_total',
  help: 'Errors on custom domains',
  labelNames: ['host', 'tenant_id'] as const,
});


