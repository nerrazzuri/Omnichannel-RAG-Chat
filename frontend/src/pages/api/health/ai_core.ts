import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const core = process.env.AI_CORE_URL || 'http://localhost:8000';
    const r = await fetch(`${core}/v1/ready`);
    const ok = r.ok;
    res.status(ok ? 200 : r.status).json({ ok, status: r.status });
  } catch (e: any) {
    res.status(503).json({ ok: false, error: e.message });
  }
}


