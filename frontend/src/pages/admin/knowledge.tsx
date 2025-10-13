import React, { useEffect, useState } from 'react';
import UploadDocument from './UploadDocument';

type Doc = { id: string; title: string; status: string };

export default function AdminKnowledgePage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [error, setError] = useState('');
  const [role] = useState('ADMIN');

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const token = localStorage.getItem('admin_jwt') || '';
        const res = await fetch('/api/internal/knowledge/list', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setDocs(data);
      } catch (e: any) {
        setError(e.message);
      }
    };
    fetchDocs();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">Admin Knowledge</h1>
          <span className="text-xs text-gray-500">Role: {role}</span>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{error}</div>}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-700">Documents</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td className="px-4 py-2 text-xs text-gray-600">{d.id}</td>
                    <td className="px-4 py-2 text-sm text-gray-900">{d.title}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{d.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-700">Upload Document</h2>
          </div>
          <UploadDocument />
        </div>
      </main>
    </div>
  );
}


