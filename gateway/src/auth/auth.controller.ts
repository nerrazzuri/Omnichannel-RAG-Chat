import { Controller, Post, Body, Headers } from '@nestjs/common';
import { issueToken } from './jwt.issue';

@Controller('auth')
export class AuthController {
  // Minimal exchange endpoint:
  // - In dev (AUTH_ALLOW_ALL=1), accept user and tenant body to issue a signed token
  // - In prod, require X-Admin-Token match to allow issuing (for service-to-service)
  @Post('exchange')
  exchange(@Body() body: any, @Headers('x-admin-token') adminToken?: string) {
    const env = (process.env.ENV || 'dev').toLowerCase();
    const allowAll = (process.env.AUTH_ALLOW_ALL || '').toLowerCase() === '1';
    const requireAdmin =
      !(env === 'dev' || env === 'local' || env === 'test') || !allowAll;

    if (requireAdmin) {
      const expected = process.env.ADMIN_UPLOAD_BEARER || '';
      if (!expected || adminToken !== expected) {
        return { error: 'forbidden' };
      }
    }

    const user_id = String(body?.user_id || 'dev-user');
    const tenant_id = String(
      body?.tenant_id ||
        process.env.AUTH_BYPASS_TENANT ||
        '00000000-0000-0000-0000-000000000001'
    );
    const role = String(body?.role || 'ADMIN');
    const tier = String(body?.tier || 'free').toLowerCase();
    const expiresIn = body?.expiresIn || '24h';

    const token = issueToken({ user_id, tenant_id, role, tier, expiresIn });
    return { token };
  }
}
