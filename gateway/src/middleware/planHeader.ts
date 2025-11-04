import { Request, Response, NextFunction } from 'express';

function planFromClaims(req: Request): string {
  const claims: any = (req as any).claims || {};
  const p = (claims.plan || claims.subscription_tier || 'free').toString().toLowerCase();
  return ['free','pro','enterprise'].includes(p) ? p : 'free';
}

export function planHeader() {
  return function (req: Request, res: Response, next: NextFunction) {
    const plan = planFromClaims(req);
    res.setHeader('X-Plan-Type', plan);
    next();
  };
}


