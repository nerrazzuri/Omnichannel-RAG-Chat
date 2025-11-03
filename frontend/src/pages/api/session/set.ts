import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    const { token, tenant_id } = req.body || {};
    if (!token || !tenant_id) {
      res.status(400).json({ error: 'token and tenant_id required' });
      return;
    }
    const isProd = process.env.NODE_ENV === 'production';
    res.setHeader('Set-Cookie', [
      `auth_token=${encodeURIComponent(token)}; HttpOnly; Path=/; SameSite=Lax${isProd ? '; Secure' : ''}`,
      `tenant_id=${encodeURIComponent(tenant_id)}; HttpOnly; Path=/; SameSite=Lax${isProd ? '; Secure' : ''}`,
    ]);
    res.status(200).json({ ok: true });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


