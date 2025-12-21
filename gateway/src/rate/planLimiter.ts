import { Request, Response, NextFunction } from 'express';
import { getRedis } from '../redis/redis';
import {
  rateLimitHits,
  requestsTotal,
  rateLimitExceeded,
} from '../metrics/metrics';

function planFromClaims(req: Request): string {
  const claims: any = (req as any).claims || {};
  const p = (claims.plan || claims.subscription_tier || 'free')
    .toString()
    .toLowerCase();
  return ['free', 'pro', 'enterprise'].includes(p) ? p : 'free';
}

function tenantFromClaims(req: Request): string {
  const claims: any = (req as any).claims || {};
  const t = (claims.tenant_id || '').toString();
  return t || 'unknown';
}

function limitForPlan(plan: string): number {
  if (plan === 'free') return 10;
  if (plan === 'pro') return 60;
  return Number.MAX_SAFE_INTEGER;
}

export function planRateLimit() {
  return async function (req: Request, res: Response, next: NextFunction) {
    const plan = planFromClaims(req);
    try {
      const r = getRedis();
      if (!r) return next();
      const minute = Math.floor(Date.now() / 60000);
      const tenant = tenantFromClaims(req);
      const key = `rate:tenant:${tenant}:${plan}:${minute}`;
      const val = await r.incr(key);
      if (val === 1) await r.expire(key, 60);
      const max = limitForPlan(plan);
      if (val > max) {
        try {
          rateLimitHits.labels(req.path || '/', plan).inc();
        } catch {}
        try {
          rateLimitExceeded.labels(plan).inc();
        } catch {}
        res.setHeader(
          'X-Upgrade-Suggestion',
          plan === 'free'
            ? 'Upgrade to Pro for 60 req/min'
            : 'Contact sales for Enterprise'
        );
        return res
          .status(429)
          .json({ detail: 'Rate limit exceeded', plan_type: plan });
      }
      // Note: requestsTotal with status should be incremented at controller layer for accurate status codes.
      next();
    } catch {
      next();
    }
  };
}
