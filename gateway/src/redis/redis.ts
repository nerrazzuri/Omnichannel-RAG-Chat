import Redis from 'ioredis';

let client: Redis | null = null;

export function getRedis(): Redis | null {
  if (client) return client;
  const url = process.env.REDIS_URL || 'redis://redis:6379/0';
  try {
    client = new Redis(url, {
      maxRetriesPerRequest: 3,
      enableAutoPipelining: true,
    });
    client.on('error', () => {});
    return client;
  } catch (e) {
    return null;
  }
}


