import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  try {
    const gw = process.env.GATEWAY_URL || "http://localhost:3001";
    const r = await fetch(`${gw}/api/ready`);
    const ok = r.ok;
    res.status(ok ? 200 : r.status).json({ ok, status: r.status });
  } catch (e: any) {
    res.status(503).json({ ok: false, error: e.message });
  }
}
