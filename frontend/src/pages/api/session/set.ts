import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }
  try {
    const { token, tenant_id } = req.body || {};
    if (!token || !tenant_id) {
      res.status(400).json({ error: "token and tenant_id required" });
      return;
    }
    // In containers NODE_ENV is 'production', but in local HTTP we must not set Secure or the browser will drop cookies.
    const forwardedProto = (req.headers["x-forwarded-proto"] as string) || "";
    const isHttps = forwardedProto.toLowerCase() === "https";
    const forceSecure = (process.env.COOKIE_SECURE || "").toLowerCase() === "1";
    const isSecure = isHttps || forceSecure;
    res.setHeader("Set-Cookie", [
      `auth_token=${encodeURIComponent(token)}; HttpOnly; Path=/; SameSite=Lax${isSecure ? "; Secure" : ""}`,
      `tenant_id=${encodeURIComponent(tenant_id)}; HttpOnly; Path=/; SameSite=Lax${isSecure ? "; Secure" : ""}`,
    ]);
    res.status(200).json({ ok: true });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}
