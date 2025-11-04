import { Request, Response, NextFunction } from 'express';

function planFromClaims(req: Request): string {
  const claims: any = (req as any).claims || {};
  const p = (claims.plan || claims.subscription_tier || 'free').toString().toLowerCase();
  return ['free','pro','enterprise'].includes(p) ? p : 'free';
}

export function planGuard() {
  const blockedForFree = ['/api/v1/keys', '/api/v1/teams', '/api/v1/connectors/enterprise'];
  return function (req: Request, res: Response, next: NextFunction) {
    const plan = planFromClaims(req);
    if (plan === 'free' && blockedForFree.some(p => (req.path || '').startsWith(p))) {
      res.setHeader('X-Upgrade-Suggestion', 'Upgrade to Pro/Enterprise to access this feature');
      return res.status(403).json({ detail: 'Feature not available on Free plan', plan_type: plan });
    }
    next();
  };
}


