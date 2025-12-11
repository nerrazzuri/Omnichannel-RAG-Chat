import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const base = process.env.AI_CORE_URL || 'http://localhost:8000';
    const url = base.endsWith('/') ? `${base}v1/tenant/plan` : `${base}/v1/tenant/plan`;

    const auth = (req.cookies?.auth_token ? `Bearer ${req.cookies.auth_token}` : '');
    const tenantId = (req.cookies?.tenant_id as string);
    if (!tenantId || !auth) {
      return res.status(401).json({ error: 'Missing auth or tenant' });
    }
    const r = await fetch(url, { headers: { 'Authorization': auth } });
    const j = await r.json().catch(() => ({} as any));
    return res.status(r.status).json(j);
  } catch (e: any) {
    return res.status(500).json({ error: e.message });
  }
}


