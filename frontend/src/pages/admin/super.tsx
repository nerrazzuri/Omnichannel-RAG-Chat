import React, { useEffect, useMemo, useState } from 'react';
import {
  getFeatures,
  setFeatures,
  listApprovals,
  decideApproval,
  listRetentionPolicies,
  updateRetentionPolicy,
} from '../../services/adminService';

export default function SuperAdmin() {
  const [apiBase, setApiBase] = useState<string>(process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000');
  const [token, setToken] = useState<string>('');
  const [tenantId, setTenantId] = useState<string>('00000000-0000-0000-0000-000000000001');
  const cfg = useMemo(() => ({ apiBase, token }), [apiBase, token]);

  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(false);
  const [loadingFeatures, setLoadingFeatures] = useState(false);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loadingApprovals, setLoadingApprovals] = useState(false);
  const [retention, setRetention] = useState<any[]>([]);
  const [loadingRetention, setLoadingRetention] = useState(false);
  const [msg, setMsg] = useState<string>('');

  const loadFeatures = async () => {
    setLoadingFeatures(true);
    setMsg('');
    try {
      const f = await getFeatures(cfg, tenantId);
      setWebSearchEnabled(!!f.web_search_enabled);
    } catch (e: any) {
      setMsg(`Load features failed: ${e.message || e}`);
    } finally {
      setLoadingFeatures(false);
    }
  };

  const saveFeatures = async () => {
    setLoadingFeatures(true);
    setMsg('');
    try {
      await setFeatures(cfg, tenantId, webSearchEnabled);
      setMsg('Features saved');
    } catch (e: any) {
      setMsg(`Save features failed: ${e.message || e}`);
    } finally {
      setLoadingFeatures(false);
    }
  };

  const loadApprovals = async () => {
    setLoadingApprovals(true);
    setMsg('');
    try {
      const rows = await listApprovals(cfg, tenantId, 'pending');
      setApprovals(rows);
    } catch (e: any) {
      setMsg(`Load approvals failed: ${e.message || e}`);
    } finally {
      setLoadingApprovals(false);
    }
  };

  const onDecide = async (id: string, decision: 'approved' | 'denied') => {
    setMsg('');
    try {
      await decideApproval(cfg, id, decision);
      await loadApprovals();
    } catch (e: any) {
      setMsg(`Decision failed: ${e.message || e}`);
    }
  };

  const loadRetention = async () => {
    setLoadingRetention(true);
    setMsg('');
    try {
      const rows = await listRetentionPolicies(cfg, tenantId);
      setRetention(rows);
    } catch (e: any) {
      setMsg(`Load retention failed: ${e.message || e}`);
    } finally {
      setLoadingRetention(false);
    }
  };

  const onRetentionSave = async (row: any) => {
    setMsg('');
    try {
      await updateRetentionPolicy(cfg, {
        tenant_id: tenantId,
        data_type: row.data_type,
        max_age_days: Number(row.max_age_days || 30),
        archive_before_delete: !!row.archive_before_delete,
        encryption_required: !!row.encryption_required,
      });
      await loadRetention();
    } catch (e: any) {
      setMsg(`Retention update failed: ${e.message || e}`);
    }
  };

  useEffect(() => {
    // no auto-load token; user sets it
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-semibold text-gray-900 mb-4">Super Admin</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="font-medium mb-3">Connection</h2>
            <label className="block text-sm text-gray-600">API Base</label>
            <input className="w-full border rounded px-3 py-2 mb-2" value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
            <label className="block text-sm text-gray-600">Bearer Token</label>
            <input className="w-full border rounded px-3 py-2 mb-2" value={token} onChange={(e) => setToken(e.target.value)} placeholder="paste admin JWT/API key here" />
            <label className="block text-sm text-gray-600">Tenant ID</label>
            <input className="w-full border rounded px-3 py-2" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="font-medium mb-3">Features</h2>
            <div className="flex items-center gap-2 mb-2">
              <input id="ws" type="checkbox" checked={webSearchEnabled} onChange={(e) => setWebSearchEnabled(e.target.checked)} />
              <label htmlFor="ws" className="text-sm">Web Search Enabled</label>
            </div>
            <div className="flex gap-2">
              <button onClick={loadFeatures} disabled={loadingFeatures} className="px-3 py-2 text-sm rounded border bg-white hover:bg-gray-50">Load</button>
              <button onClick={saveFeatures} disabled={loadingFeatures} className="px-3 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700">Save</button>
            </div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">Approvals</h2>
            <button onClick={loadApprovals} disabled={loadingApprovals} className="px-3 py-2 text-sm rounded border bg-white hover:bg-gray-50">Refresh</button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="p-2 border-b">ID</th>
                  <th className="p-2 border-b">Tool</th>
                  <th className="p-2 border-b">Requested</th>
                  <th className="p-2 border-b">Actions</th>
                </tr>
              </thead>
              <tbody>
                {approvals.map((r) => (
                  <tr key={r.id} className="border-b">
                    <td className="p-2">{r.id}</td>
                    <td className="p-2">{r.tool_id}</td>
                    <td className="p-2">{r.created_at}</td>
                    <td className="p-2 flex gap-2">
                      <button onClick={() => onDecide(r.id, 'approved')} className="px-2 py-1 text-xs rounded bg-emerald-600 text-white">Approve</button>
                      <button onClick={() => onDecide(r.id, 'denied')} className="px-2 py-1 text-xs rounded bg-rose-600 text-white">Deny</button>
                    </td>
                  </tr>
                ))}
                {approvals.length === 0 && (
                  <tr><td className="p-2 text-gray-500" colSpan={4}>No pending approvals</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">Retention Policies</h2>
            <button onClick={loadRetention} disabled={loadingRetention} className="px-3 py-2 text-sm rounded border bg-white hover:bg-gray-50">Refresh</button>
          </div>
          <div className="space-y-2">
            {retention.map((p, idx) => (
              <div key={idx} className="border rounded p-2 flex flex-wrap items-center gap-2">
                <div className="text-sm font-mono">{p.data_type}</div>
                <label className="text-sm">Max Days</label>
                <input className="border rounded px-2 py-1 w-24" defaultValue={p.max_age_days} onBlur={(e) => (p.max_age_days = Number(e.target.value))} />
                <label className="text-sm">Archive before delete</label>
                <input type="checkbox" defaultChecked={p.archive_before_delete} onChange={(e) => (p.archive_before_delete = e.target.checked)} />
                <label className="text-sm">Encryption required</label>
                <input type="checkbox" defaultChecked={p.encryption_required} onChange={(e) => (p.encryption_required = e.target.checked)} />
                <button onClick={() => onRetentionSave(p)} className="ml-auto px-3 py-1 text-xs rounded bg-blue-600 text-white">Save</button>
              </div>
            ))}
            {retention.length === 0 && <div className="text-sm text-gray-500">No policies found</div>}
          </div>
        </div>

        {msg && <div className="text-sm text-rose-600">{msg}</div>}

        <div className="mt-6 text-xs text-gray-500">Set a valid admin token to use management APIs. API base defaults to http://localhost:8000.</div>
      </div>
    </div>
  );
}


