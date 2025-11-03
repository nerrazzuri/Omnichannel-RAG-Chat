import { getRedis } from '../redis/redis';
import axios from 'axios';

const QUEUE_KEY = 'webhook:queue';

export async function enqueueWebhook(item: any) {
  const r = getRedis();
  if (!r) return; // fallback: let controller send directly
  await r.rpush(QUEUE_KEY, JSON.stringify({ ...item, ts: Date.now(), attempts: 0 }));
}

export function startWebhookWorker() {
  const r = getRedis();
  if (!r) return;
  const aiCoreUrl = process.env.AI_CORE_URL || 'http://ai-core:8000';

  async function loop() {
    try {
      const res = await r.blpop(QUEUE_KEY, 2);
      if (!res) return;
      const [, raw] = res as any;
      let msg: any;
      try { msg = JSON.parse(raw); } catch { return; }
      try {
        await axios.post(`${aiCoreUrl}/v1/query`, msg.body, { headers: msg.headers || {} });
      } catch (e) {
        const attempts = (msg.attempts || 0) + 1;
        if (attempts <= 5) {
          msg.attempts = attempts;
          await r.rpush(QUEUE_KEY, JSON.stringify(msg));
        }
      }
    } catch {
      // ignore
    }
  }

  // Polling loop
  setInterval(loop, 500);
}


