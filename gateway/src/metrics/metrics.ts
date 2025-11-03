import { Counter } from 'prom-client';

export const requestsTotal = new Counter({
  name: 'gateway_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['path', 'method', 'status'] as const,
});

export const rateLimitHits = new Counter({
  name: 'gateway_rate_limit_hits_total',
  help: 'Rate limit hits',
  labelNames: ['path'] as const,
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


