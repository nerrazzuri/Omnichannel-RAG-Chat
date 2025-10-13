import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  try {
    const base = process.env.AI_CORE_URL || 'http://localhost:8000';
    const url = base.endsWith('/') ? `${base}v1/query` : `${base}/v1/query`;

    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    });

    if (!r.ok) {
      const text = await r.text();
      res.status(r.status).send(text);
      return;
    }

    const data = await r.json();
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.status(200).send(data.response);
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


