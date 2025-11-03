import { Request, Response, NextFunction } from 'express';
import { getRedis } from '../redis/redis';
import { rateLimitHits } from '../metrics/metrics';

export function redisRateLimit(maxPerMinute: number) {
  return async function (req: Request, res: Response, next: NextFunction) {
    try {
      const r = getRedis();
      if (!r) return next();
      const ip = (req.headers['x-forwarded-for'] as string) || req.ip || 'unknown';
      const minute = Math.floor(Date.now() / 60000);
      const key = `rate:ip:${ip}:${minute}`;
      const val = await r.incr(key);
      if (val === 1) {
        await r.expire(key, 60);
      }
      if (val > maxPerMinute) {
        try { rateLimitHits.labels(req.path || '/').inc(); } catch {}
        return res.status(429).json({ detail: 'Rate limit exceeded' });
      }
      next();
    } catch {
      next();
    }
  };
}


