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

    const contentType = r.headers.get('content-type') || '';
    if (!r.ok) {
      const text = await r.text();
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.status(r.status).send(text);
      return;
    }

    // Prefer JSON; return only the response field as plain text for UI readability
    if (contentType.includes('application/json')) {
      const data = await r.json();
      const text = typeof data === 'string' ? data : (data.response ?? JSON.stringify(data));
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.status(200).send(text);
    } else {
      const text = await r.text();
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.status(200).send(text);
    }
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


