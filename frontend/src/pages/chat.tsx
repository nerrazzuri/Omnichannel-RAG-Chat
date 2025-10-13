import React, { useState, useRef, useEffect } from 'react';
import { streamQuery } from '../services/chatService';

type Message = { role: 'user' | 'assistant'; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = { role: 'user', content: input };
    setMessages((m) => [...m, userMsg, { role: 'assistant', content: '' }]);
    setInput('');
    setLoading(true);
    let assistant = '';
    try {
      for await (const chunk of streamQuery({ tenantId: '00000000-0000-0000-0000-000000000001', userId: '00000000-0000-0000-0000-000000000002', channel: 'web', message: userMsg.content })) {
        assistant += chunk.data;
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: 'assistant', content: assistant };
          return copy;
        });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-blue-600" />
            <h1 className="text-lg font-semibold text-gray-900">Omnichannel RAG Chat</h1>
          </div>
          <div className="text-sm text-gray-500">Staging</div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <section className="lg:col-span-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-700">Conversation</h2>
              </div>
              <div className="h-[60vh] overflow-y-auto p-4 space-y-4">
                {messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'} max-w-[75%] rounded-2xl px-4 py-2 shadow-sm`}> 
                      {m.content}
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <div className="p-4 border-t border-gray-100">
                <div className="flex items-center gap-2">
                  <input
                    className="flex-1 rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your message..."
                    onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
                  />
                  <button
                    onClick={send}
                    disabled={loading}
                    className="inline-flex items-center justify-center rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 disabled:opacity-50"
                  >
                    {loading ? 'Sending...' : 'Send'}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <aside className="lg:col-span-4 space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Session</h3>
              <p className="text-xs text-gray-500">Tenant: 00000000-0000-0000-0000-000000000001</p>
              <p className="text-xs text-gray-500">User: 00000000-0000-0000-0000-000000000002</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Tips</h3>
              <ul className="text-xs text-gray-600 list-disc pl-4 space-y-1">
                <li>Ask about policies, SOPs, or knowledge topics.</li>
                <li>Switch channels and maintain context via Redis.</li>
              </ul>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}


