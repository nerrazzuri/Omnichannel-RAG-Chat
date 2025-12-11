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
    const auth = (req.cookies?.auth_token ? `Bearer ${req.cookies.auth_token}` : '');
    const tenantId = (req.cookies?.tenant_id as string);
    if (!auth || !tenantId) {
      res.status(401).json({ error: 'Authorization required' });
      return;
    }

    // Normalize body to include camelCase tenantId required by AI Core
    const body = typeof req.body === 'object' && req.body ? { ...req.body } : {};
    if (!('tenantId' in body) || !body.tenantId) {
      (body as any).tenantId = tenantId;
    }
    // Keep snake_case for backward compatibility if callers expect it
    if (!('tenant_id' in body) || !body.tenant_id) {
      (body as any).tenant_id = (body as any).tenantId;
    }

    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': auth },
      body: JSON.stringify(body),
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


