import * as jwt from 'jsonwebtoken';
import type { SignOptions, Secret } from 'jsonwebtoken';
import * as fs from 'fs';

function loadSecret(): string {
  const file = process.env.JWT_SECRET_FILE;
  if (file && fs.existsSync(file)) {
    try {
      const val = fs.readFileSync(file, 'utf8').trim();
      if (val && val.length >= 32) {
        return val;
      }
    } catch {}
  }
  return process.env.JWT_SECRET || '';
}

const secret = loadSecret();

export type IssueTokenInput = {
  user_id: string;
  tenant_id: string;
  role: 'ADMIN' | 'MEMBER' | 'OWNER' | string;
  tier?: 'free' | 'pro' | 'enterprise' | string;
  expiresIn?: string | number; // e.g. '24h'
};

export function issueToken(input: IssueTokenInput): string {
  if (!secret || secret.length < 32) {
    throw new Error('JWT secret not configured/weak');
  }
  const now = Math.floor(Date.now() / 1000);
  const payload: any = {
    user_id: input.user_id,
    tenant_id: input.tenant_id,
    role: input.role,
    subscription_tier: input.tier || 'free',
    type: 'access',
    iss: 'omnichannel-chatbot',
    iat: now,
  };
  const expires: any = input.expiresIn || '24h';
  const opts: SignOptions = {
    algorithm: 'HS256',
    expiresIn: expires,
  } as unknown as SignOptions;
  return jwt.sign(payload, secret as Secret, opts);
}
