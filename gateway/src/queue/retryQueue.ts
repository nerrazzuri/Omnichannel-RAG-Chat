import { getRedis } from '../redis/redis';
import axios from 'axios';
import crypto from 'crypto';
import { queueEnqueued, queueFailed, queueDLQ } from '../metrics/metrics';

const QUEUE_KEY = 'webhook:queue';

function sign(body: any): string {
  const secret = (process.env.JWT_SECRET || '').toString();
  const h = crypto.createHmac('sha256', secret);
  h.update(JSON.stringify(body || {}));
  return h.digest('hex');
}

export async function enqueueWebhook(item: any): Promise<boolean> {
  const r = getRedis();
  if (!r) {
    try {
      queueFailed.inc();
    } catch {}
    return false;
  }
  const payload = { ...item, ts: Date.now(), attempts: 0 };
  payload.sig = sign(payload.body);
  await r.rpush(QUEUE_KEY, JSON.stringify(payload));
  try {
    queueEnqueued.inc();
  } catch {}
  return true;
}

export function startWebhookWorker() {
  const r = getRedis();
  if (!r) return;
  const aiCoreUrl = process.env.AI_CORE_URL || 'http://ai-core:8000';

  function verify(body: any, sig: string): boolean {
    try {
      return sign(body) === sig;
    } catch {
      return false;
    }
  }

  async function loop() {
    try {
      const res = await r.blpop(QUEUE_KEY, 2);
      if (!res) return;
      const [, raw] = res as any;
      let msg: any;
      try {
        msg = JSON.parse(raw);
      } catch {
        return;
      }
      if (!verify(msg.body, msg.sig)) {
        try {
          queueDLQ.inc();
        } catch {}
        await r.rpush(`${QUEUE_KEY}:dlq`, raw);
        return;
      }
      try {
        await axios.post(`${aiCoreUrl}/v1/query`, msg.body, {
          headers: msg.headers || {},
        });
      } catch (e) {
        const attempts = (msg.attempts || 0) + 1;
        if (attempts <= 5) {
          msg.attempts = attempts;
          await r.rpush(QUEUE_KEY, JSON.stringify(msg));
        } else {
          try {
            queueDLQ.inc();
          } catch {}
          await r.rpush(`${QUEUE_KEY}:dlq`, JSON.stringify(msg));
        }
      }
    } catch {
      // ignore
    }
  }

  // Polling loop
  setInterval(loop, 500);
}
