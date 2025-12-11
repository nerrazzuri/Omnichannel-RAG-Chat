import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const tenantId = req.cookies['tenant_id'] || '';
    const token = req.cookies['auth_token'] || '';
    if (!tenantId) return res.status(400).json({ detail: 'missing tenant_id' });

    const base = process.env.AI_CORE_URL || 'http://localhost:8000';
    const url = base.endsWith('/') ? `${base}v1/tenant/branding` : `${base}/v1/tenant/branding`;
    const r = await fetch(`${url}?tenant_id=${encodeURIComponent(tenantId)}`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    const j = await r.json();
    return res.status(r.status).json(j);
  } catch (e: any) {
    return res.status(500).json({ detail: e?.message || 'error' });
  }
}


