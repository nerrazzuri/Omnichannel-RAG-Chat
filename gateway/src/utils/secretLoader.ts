import { readFileSync } from 'fs';

// Load *_FILE secrets into env (JWT_SECRET_FILE → JWT_SECRET)
try {
  const filePath = process.env.JWT_SECRET_FILE;
  if (filePath && !process.env.JWT_SECRET) {
    const val = readFileSync(filePath, 'utf8').trim();
    if (val && val.length >= 32) {
      process.env.JWT_SECRET = val;
    }
  }
} catch {
  // ignore
}
