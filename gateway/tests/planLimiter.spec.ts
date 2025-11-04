import { planRateLimit } from '../src/rate/planLimiter';

jest.mock('../src/redis/redis', () => ({ getRedis: () => ({ incr: async () => 9999, expire: async () => {} }) }));

function mockReq(plan: string, path: string='/'): any { return { path, method: 'GET', claims: { subscription_tier: plan } }; }
function mockRes() {
  const headers: Record<string,string> = {};
  return { status: (s: number) => ({ json: (j: any) => ({ status: s, body: j }) }), setHeader: (k: string, v: string) => { headers[k]=v; } } as any;
}

describe('planRateLimit', () => {
  it('blocks free over limit', async () => {
    const mw = planRateLimit();
    const out = await mw(mockReq('free'), mockRes(), (()=>{}) as any);
    expect(out).toBeDefined();
  });
});


