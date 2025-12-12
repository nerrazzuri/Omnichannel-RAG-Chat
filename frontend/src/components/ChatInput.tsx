import React from 'react';

type ChatInputProps = {
  value: string;
  loading: boolean;
  onChange: (v: string) => void;
  onSend: () => void;
};

export default function ChatInput({ value, loading, onChange, onSend }: ChatInputProps) {
  return (
    <div className="flex items-end gap-2">
      <button
        type="button"
        className="h-10 w-10 flex items-center justify-center rounded-xl border border-gray-300 text-gray-600 hover:bg-gray-50"
        title="Attach files (coming soon)"
        disabled
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 6a4 4 0 0 1 8 0v8a3 3 0 1 1-6 0V8a1 1 0 0 1 2 0v7a1 1 0 0 0 2 0V6a2 2 0 1 0-4 0v9a4 4 0 0 0 8 0V8a1 1 0 1 1 2 0v7a6 6 0 1 1-12 0V8A4 4 0 0 1 8 6z"/></svg>
      </button>
      <textarea
        rows={1}
        className="flex-1 resize-none rounded-xl border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm px-4 py-3 shadow-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Ask about your knowledge…"
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (value.trim()) onSend(); } }}
      />
      <button
        onClick={onSend}
        disabled={loading || !value.trim()}
        className="inline-flex items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-3 shadow disabled:opacity-50"
      >
        {loading ? (
          <span className="inline-flex items-center gap-2">
            <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 0 0-4 4H4z"></path></svg>
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
  );
}


