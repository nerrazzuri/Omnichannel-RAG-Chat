import { Request, Response, NextFunction } from 'express';
import { customDomainRequests } from '../metrics/metrics';

// Simple in-memory cache placeholder; in production, use Redis or DB lookup
const hostToTenantCache = new Map<
  string,
  { tenant_id: string; plan_type: string }
>();

export function hostTenant() {
  return async function (req: Request, res: Response, next: NextFunction) {
    try {
      const host =
        (req.headers['x-forwarded-host'] as string) ||
        (req.headers['host'] as string) ||
        '';
      let tenantId = (req.headers['x-tenant-id'] as string) || '';
      let planType = (req.headers['x-plan-type'] as string) || '';

      if (!tenantId && host) {
        const cached = hostToTenantCache.get(host.toLowerCase());
        if (cached) {
          tenantId = cached.tenant_id;
          planType = cached.plan_type;
        }
        // TODO: add DB lookup for custom_domain → tenant
      }

      if (tenantId) {
        // Attach to request for downstream middlewares
        (req as any).tenant_id = tenantId;
        if (planType) (req as any).plan_type = planType;
        if (host) {
          customDomainRequests.labels(host, tenantId).inc();
          res.setHeader('X-Tenant-ID', tenantId);
          if (planType) res.setHeader('X-Plan-Type', planType);
        }
      }

      // Security headers (can be refined per-tenant CSP later)
      res.setHeader('X-Frame-Options', 'DENY');
      res.setHeader('Referrer-Policy', 'no-referrer-when-downgrade');
      res.setHeader('X-Content-Type-Options', 'nosniff');

      return next();
    } catch (e) {
      return next();
    }
  };
}
