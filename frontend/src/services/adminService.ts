export type AdminConfig = { apiBase: string; token: string };

function headers(token: string) {
  return {
    'Content-Type': 'application/json',
    Authorization: token ? `Bearer ${token}` : '',
  } as Record<string, string>;
}

export async function getFeatures(cfg: AdminConfig, tenantId: string) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/features/get?tenant_id=${encodeURIComponent(tenantId)}`, {
    headers: headers(cfg.token),
  });
  if (!r.ok) throw new Error(`features get failed: ${r.status}`);
  return r.json();
}

export async function setFeatures(cfg: AdminConfig, tenantId: string, webSearchEnabled: boolean) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/features/set`, {
    method: 'POST',
    headers: headers(cfg.token),
    body: JSON.stringify({ tenant_id: tenantId, web_search_enabled: webSearchEnabled }),
  });
  if (!r.ok) throw new Error(`features set failed: ${r.status}`);
  return r.json();
}

export async function listTenants(cfg: AdminConfig) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/tenants/list`, {
    headers: headers(cfg.token),
  });
  if (!r.ok) throw new Error(`tenants list failed: ${r.status}`);
  return r.json();
}

export async function getTenantSummary(cfg: AdminConfig, tenantId: string) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/tenants/summary?tenant_id=${encodeURIComponent(tenantId)}`, {
    headers: headers(cfg.token),
  });
  if (!r.ok) throw new Error(`tenant summary failed: ${r.status}`);
  return r.json();
}

export async function createTenant(cfg: AdminConfig, body: { name: string; domain: string; subscription_tier?: string; settings?: Record<string, any> }) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/tenants/create`, {
    method: 'POST',
    headers: headers(cfg.token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`tenant create failed: ${r.status}`);
  return r.json();
}

export async function listApprovals(cfg: AdminConfig, tenantId: string, status?: string) {
  const qs = new URLSearchParams({ tenant_id: tenantId, ...(status ? { status } : {}) });
  const r = await fetch(`${cfg.apiBase}/v1/agent/approvals/list?${qs.toString()}`, { headers: headers(cfg.token) });
  if (!r.ok) throw new Error(`approvals list failed: ${r.status}`);
  return r.json();
}

export async function decideApproval(cfg: AdminConfig, approvalId: string, decision: 'approved' | 'denied', reason?: string, decidedBy?: string) {
  const r = await fetch(`${cfg.apiBase}/v1/agent/approvals/decide`, {
    method: 'POST',
    headers: headers(cfg.token),
    body: JSON.stringify({ approval_id: approvalId, status: decision, reason, decided_by: decidedBy }),
  });
  if (!r.ok) throw new Error(`approval decide failed: ${r.status}`);
  return r.json();
}

export async function listRetentionPolicies(cfg: AdminConfig, tenantId: string) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/retention/policies?tenant_id=${encodeURIComponent(tenantId)}`, {
    headers: headers(cfg.token),
  });
  if (!r.ok) throw new Error(`retention list failed: ${r.status}`);
  return r.json();
}

export async function updateRetentionPolicy(
  cfg: AdminConfig,
  body: { tenant_id: string; data_type: string; max_age_days: number; archive_before_delete: boolean; encryption_required?: boolean }
) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/retention/update`, {
    method: 'POST',
    headers: headers(cfg.token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`retention update failed: ${r.status}`);
  return r.json();
}

export async function getGatewayHealth(base='http://localhost:3001') {
  const r = await fetch(`${base}/api/ready`);
  return { ok: r.ok, status: r.status };
}

export async function getAiCoreHealth(baseApi: string) {
  const r = await fetch(`${baseApi}/v1/ready`);
  return { ok: r.ok, status: r.status };
}

export async function getComplianceSummary(cfg: AdminConfig) {
  const r = await fetch(`${cfg.apiBase}/v1/admin/reports/summary`, {
    headers: headers(cfg.token),
  });
  if (!r.ok) throw new Error(`compliance summary failed: ${r.status}`);
  return r.json();
}


