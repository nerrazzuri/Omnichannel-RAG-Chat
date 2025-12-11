import React, { useState, useRef, useEffect } from 'react';
import { postQuery } from '../services/chatService';
import { ChatMessage } from '../components/ChatMessage';
import { Message, ReasoningStep } from '../types/chat';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [planType, setPlanType] = useState<string>('');
  const [usage, setUsage] = useState<{ tokens_used: number; tokens_quota: number } | null>(null);

  const endRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showScrollDown, setShowScrollDown] = useState(false);

  // Seed Omni greeting on initial load
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{
        id: 'init-1',
        role: 'assistant',
        content: "Hello! I'm Omni. How can I help you today?",
        timestamp: Date.now()
      }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch('/api/tenant/plan', { headers: {} });
        if (r.ok) {
          const j = await r.json();
          setPlanType(j?.plan_type || '');
        }
        const u = await fetch('/api/tenant/usage');
        if (u.ok) {
          const ju = await u.json();
          setUsage({ tokens_used: ju?.tokens_used || 0, tokens_quota: ju?.tokens_quota || 0 });
        }
      } catch { }
    })();
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

  const handleFeedback = (messageId: string, isPositive: boolean) => {
    setMessages(prev => prev.map(msg => {
      if (msg.id === messageId) {
        return { ...msg, feedback: { isPositive } };
      }
      return msg;
    }));
    // TODO: Send feedback to backend API
    console.log(`Feedback for ${messageId}: ${isPositive ? 'Positive' : 'Negative'}`);
  };

  const send = async () => {
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: Date.now()
    };

    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const resp = await postQuery({ channel: 'web', message: userMsg.content });
      const content = resp.response || resp.final_response || '';

      // Map backend citations to string array if needed, or keep as is if we update type
      // For now, we'll just store them in the message object as any extra fields
      // But strictly, let's try to map to our new type if possible.
      // The current ChatMessage component doesn't explicitly render citations yet (it uses MessageRenderer),
      // but we should pass them if we want to render them separately.
      // For this refactor, we'll rely on MessageRenderer or add citation support to ChatMessage later.
      // Actually, the previous chat.tsx rendered citations manually. 
      // Let's append citations to content for now or handle them in ChatMessage.
      // To keep it simple and clean, let's append them to content as markdown if they exist, 
      // OR better, let's update ChatMessage to handle them. 
      // For this step, I will just pass them through.

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content,
        timestamp: Date.now(),
        // Mock reasoning steps for demo purposes if backend doesn't send them yet
        reasoningSteps: resp.reasoning_steps as ReasoningStep[] || undefined,
        citations: resp.citations?.map((c: any) => c.source_url || c.title || c.source)
      };

      setMessages((m) => [...m, assistantMsg]);
    } catch (e) {
      console.error(e);
      setMessages((m) => [...m, {
        id: Date.now().toString(),
        role: 'assistant',
        content: "I'm sorry, I encountered an error processing your request.",
        timestamp: Date.now()
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <header className="sticky top-0 z-20 backdrop-blur bg-white/70 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-blue-600 flex items-center justify-center text-white font-bold">O</div>
            <h1 className="text-lg font-semibold text-gray-900">Omnichannel RAG Chat</h1>
            <span className="hidden md:inline-flex ml-2 px-2 py-0.5 text-xs rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">Staging</span>
          </div>
          <div className="flex items-center gap-2">
            <a href="/admin/UploadDocument" className="hidden sm:inline-flex text-sm text-gray-600 hover:text-gray-900">Knowledge</a>
          </div>
        </div>
        {planType && (
          <div className="bg-blue-50 border-t border-blue-100 text-blue-800 text-xs py-2 px-4">
            Plan: <span className="font-medium uppercase">{planType}</span>{planType === 'free' ? ' — Upgrade to Pro for higher limits.' : ''}
            {usage && usage.tokens_quota > 0 && (
              <span className="ml-4">Tokens: {usage.tokens_used}/{usage.tokens_quota}</span>
            )}
          </div>
        )}
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
              {messages.map((m) => (
                <ChatMessage
                  key={m.id}
                  message={m}
                  onFeedback={handleFeedback}
                />
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


