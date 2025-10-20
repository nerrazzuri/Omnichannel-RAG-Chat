import React, { useState, useRef, useEffect } from 'react';
import { streamQuery } from '../services/chatService';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type Message = { role: 'user' | 'assistant'; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  // Sidebar removed for minimal UI
  const endRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showScrollDown, setShowScrollDown] = useState(false);
  // Seed Omni greeting on initial load for better UX
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{ role: 'assistant', content: "Hello! I’m Omni. How can I help you today?" }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      setShowScrollDown(!nearBottom);
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

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

  const MessageBubble = ({ m }: { m: Message }) => {
    const isUser = m.role === 'user';
    const urls = !isUser ? Array.from(new Set((m.content.match(/https?:\/\/[\w\-\.\/?#=&%]+/g) || []))).slice(0, 5) : [];
    const copy = async () => {
      try { await navigator.clipboard.writeText(m.content); } catch {}
    };
    return (
      <div className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className={`flex items-start gap-3 max-w-[900px] w-full ${isUser ? 'flex-row-reverse' : ''}`}>
          <div className={`h-8 w-8 rounded-full flex items-center justify-center ${isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}>
            {isUser ? 'U' : 'AI'}
          </div>
          <div className={`${isUser ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 border border-gray-200'} px-4 py-3 rounded-2xl shadow-sm w-full`}> 
            {isUser ? (
              <div className="whitespace-pre-wrap leading-relaxed text-sm">{m.content}</div>
            ) : (
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm as any]}>{m.content}</ReactMarkdown>
              </div>
            )}
            {!isUser && urls.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {urls.map((u, idx) => (
                  <a key={idx} href={u} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-gray-100 hover:bg-gray-200 border border-gray-200 text-gray-700">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14L21 3m-7 0h7v7"/></svg>
                    <span className="truncate max-w-[160px]">{u.replace(/^https?:\/\//,'')}</span>
                  </a>
                ))}
              </div>
            )}
            <div className="mt-2 flex justify-end">
              <button onClick={copy} className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded border ${isUser ? 'border-white/40 text-white/90 hover:bg-white/10' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <header className="sticky top-0 z-20 backdrop-blur bg-white/70 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-blue-600" />
            <h1 className="text-lg font-semibold text-gray-900">Omnichannel RAG Chat</h1>
            <span className="hidden md:inline-flex ml-2 px-2 py-0.5 text-xs rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">Staging</span>
          </div>
          <div className="flex items-center gap-2">
            <a href="/admin/UploadDocument" className="hidden sm:inline-flex text-sm text-gray-600 hover:text-gray-900">Knowledge</a>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4">
        <div className="flex py-4">
          {/* Chat area only */}
          <section className="w-full flex flex-col">
            <div ref={scrollRef} className="flex-1 overflow-y-auto pt-4 pb-28 space-y-6">
              {messages.length === 0 && (
                <div className="mx-auto mt-16 max-w-2xl text-center text-gray-500">
                  <h3 className="text-2xl font-semibold text-gray-900 mb-2">Welcome</h3>
                  <p className="text-sm">Ask about documents, policies, or upload knowledge in the Admin panel.</p>
                </div>
              )}
              {messages.map((m, i) => (
                <MessageBubble key={i} m={m} />
              ))}
              {loading && (
                <div className="w-full flex justify-start">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-gray-200" />
                    <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl shadow-sm">
                      <div className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.2s]"></span>
                        <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce"></span>
                        <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0.2s]"></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            {/* Composer */}
            <div className="fixed left-0 right-0 bottom-0 bg-gradient-to-t from-white to-white/70 backdrop-blur border-t border-gray-200">
              <div className="max-w-4xl mx-auto px-4 py-4">
                <div className="flex items-end gap-2">
                  <textarea
                    rows={1}
                    className="flex-1 resize-none rounded-xl border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm px-4 py-3 shadow-sm"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Message Omnichannel RAG..."
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                  />
                  <button
                    onClick={send}
                    disabled={loading}
                    className="inline-flex items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-3 shadow disabled:opacity-50"
                  >
                    {loading ? (
                      <span className="inline-flex items-center gap-2">
                        <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
                        Sending
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 12h14M12 5l7 7-7 7" /></svg>
                        Send
                      </span>
                    )}
                  </button>
                </div>
                <div className="mt-2 text-[11px] text-gray-500">Shift+Enter for new line</div>
              </div>
            </div>

            {showScrollDown && (
              <button
                onClick={() => endRef.current?.scrollIntoView({ behavior: 'smooth' })}
                className="fixed right-5 bottom-24 h-9 w-9 rounded-full shadow bg-white border border-gray-200 flex items-center justify-center text-gray-700 hover:bg-gray-50"
                aria-label="Scroll to bottom"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
              </button>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}


