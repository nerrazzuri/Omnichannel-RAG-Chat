import { CanActivate, ExecutionContext, Injectable, UnauthorizedException, ForbiddenException } from '@nestjs/common';
import { verifyToken } from './jwt.util';

@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private requiredScope?: string) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const auth = req.headers['authorization'] as string | undefined;

    // Allow anonymous webhooks only in dev/local/test when explicitly enabled
    const env = (process.env.ENV || 'dev').toLowerCase();
    const allowAnon = ['dev', 'local', 'test'].includes(env) && (process.env.ALLOW_ANON_WEBHOOKS || '').toLowerCase() === '1';

    if (!auth) {
      if (allowAnon) return true;
      throw new UnauthorizedException('Authorization header required');
    }

    const [scheme, token] = auth.split(' ');
    if (!scheme || scheme.toLowerCase() !== 'bearer' || !token) {
      throw new UnauthorizedException('Invalid authorization header');
    }

    const claims = verifyToken(token);
    if (!claims) {
      throw new UnauthorizedException('Invalid token');
    }

    // Basic RBAC: if requiredScope provided, ensure role ADMIN or scopes include it
    if (this.requiredScope) {
      const role = String(claims.role || '').toUpperCase();
      const scopes: string[] = Array.isArray(claims.scopes) ? claims.scopes : [];
      if (role !== 'ADMIN' && !scopes.includes(this.requiredScope)) {
        throw new ForbiddenException('Forbidden');
      }
    }

    // Attach claims for downstream usage
    req.user = claims;
    return true;
  }
}
