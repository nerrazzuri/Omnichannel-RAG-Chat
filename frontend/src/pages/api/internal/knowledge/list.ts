import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    const auth = req.headers.authorization || '';
    const r = await fetch((process.env.AI_CORE_URL || 'http://localhost:8000') + '/v1/internal/knowledge/list', {
      headers: { Authorization: auth },
    });
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


