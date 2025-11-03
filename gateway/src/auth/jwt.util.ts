import * as jwt from 'jsonwebtoken';
import * as fs from 'fs';

function loadSecret(): string {
  const file = process.env.JWT_SECRET_FILE;
  if (file && fs.existsSync(file)) {
    try {
      return fs.readFileSync(file, 'utf-8').trim();
    } catch {
      // ignore
    }
  }
  return process.env.JWT_SECRET || '';
}

const secret = loadSecret();

export function verifyToken(token: string): any | null {
  try {
    if (!secret || secret.length < 16) return null;
    return jwt.verify(token, secret, { algorithms: ['HS256'] });
  } catch {
    return null;
  }
}
