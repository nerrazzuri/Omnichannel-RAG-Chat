import type { NextApiRequest, NextApiResponse } from 'next';

export const config = {
  api: {
    bodyParser: false, // keep raw stream for multipart
    responseLimit: false, // allow large upstream responses
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    // Buffer the incoming multipart request body to preserve boundaries
    const chunks: Buffer[] = [];
    for await (const chunk of req) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    const bodyBuffer = Buffer.concat(chunks);

    const ct = req.headers['content-type'] || 'application/octet-stream';
    const incomingAuth = (req.headers['authorization'] as string) || (req.headers['x-admin-token'] as string);
    const qToken = (req.query['token'] as string) || (req.query['auth'] as string);
    const qBearer = qToken ? (qToken.startsWith('Bearer ') ? qToken : `Bearer ${qToken}`) : undefined;
    const staticAuth = process.env.ADMIN_UPLOAD_BEARER ? `Bearer ${process.env.ADMIN_UPLOAD_BEARER}` : undefined;
    const authHeader = incomingAuth || qBearer || staticAuth;
    const upstream = await fetch((process.env.AI_CORE_URL || 'http://localhost:8000') + '/v1/tenant/upload_file', {
      method: 'POST',
      headers: {
        'Content-Type': Array.isArray(ct) ? ct[0] : ct,
        ...(authHeader ? { 'Authorization': authHeader } : {}),
      },
      body: bodyBuffer,
    });

    const respCt = upstream.headers.get('content-type') || '';
    if (respCt.includes('application/json')) {
      const data = await upstream.json();
      res.status(upstream.status).json(data);
    } else {
      const text = await upstream.text();
      res.status(upstream.status).send(text);
    }
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}


