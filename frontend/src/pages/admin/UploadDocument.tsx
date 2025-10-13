import React, { useState } from 'react';

export default function UploadDocument() {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState('');

  const uploadJson = async () => {
    setStatus('');
    try {
      const body = { tenantId: '00000000-0000-0000-0000-000000000001', knowledgeBaseId: '00000000-0000-0000-0000-000000000000', title, content };
      const res = await fetch('/api/tenant/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Upload failed');
      setStatus(`Uploaded: ${data.documentId} (chunks: ${data.chunkCount})`);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    }
  };

  const uploadFile = async () => {
    if (!file) { setStatus('Please select a file.'); return; }
    setStatus('');
    try {
      const form = new FormData();
      form.append('tenantId', '00000000-0000-0000-0000-000000000001');
      form.append('knowledgeBaseId', '00000000-0000-0000-0000-000000000000');
      form.append('title', title || file.name);
      form.append('file', file);
      const res = await fetch('/api/tenant/upload_file', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Upload failed');
      setStatus(`Uploaded: ${data.documentId} (chunks: ${data.chunkCount})`);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">Title</label>
          <input className="w-full rounded-md border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <label className="block text-sm font-medium text-gray-700">Content (paste)</label>
          <textarea className="w-full rounded-md border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm" placeholder="Content" value={content} onChange={(e) => setContent(e.target.value)} rows={8} />
          <button onClick={uploadJson} className="inline-flex items-center rounded-md bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2">Upload Text</button>
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">File</label>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="block w-full text-sm text-gray-900 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
          <p className="text-xs text-gray-500">Supported: pdf, docx, pptx, xlsx, csv, txt</p>
          <button onClick={uploadFile} className="inline-flex items-center rounded-md bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2">Upload File</button>
        </div>
      </div>
      {status && <div className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded p-3">{status}</div>}
    </div>
  );
}


