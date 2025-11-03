import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  try {
    const base = process.env.AI_CORE_URL || 'http://localhost:8000';
    const url = base.endsWith('/') ? `${base}v1/query` : `${base}/v1/query`;

    // Require auth and tenant headers (or cookies) and forward them
    const auth = (req.headers['authorization'] as string) || (req.cookies?.auth_token ? `Bearer ${req.cookies.auth_token}` : '');
    const tenantId = (req.headers['x-tenant-id'] as string) || (req.cookies?.tenant_id as string);
    if (!tenantId) {
      res.status(400).json({ error: 'X-Tenant-ID header or tenant_id cookie required' });
      return;
    }
    if (!auth) {
      res.status(401).json({ error: 'Authorization required' });
      return;
    }

    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': auth, 'X-Tenant-ID': tenantId },
      body: JSON.stringify(req.body),
    });

    const contentType = r.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await r.json();
      res.setHeader('Content-Type', 'application/json');
      res.status(r.status).json(data);
    } else {
      const text = await r.text();
      res.status(r.status).send(text);
    }
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


