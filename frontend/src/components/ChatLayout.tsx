import React from 'react';

type Usage = { tokens_used: number; tokens_quota: number; docs_count?: number };

type ChatLayoutProps = {
  title: string;
  planType?: string;
  usage?: Usage | null;
  sidebar?: React.ReactNode;
  children: React.ReactNode; // main chat window
  bottomDock: React.ReactNode; // input composer
};

export default function ChatLayout(props: ChatLayoutProps) {
  const { title, planType, usage, sidebar, children, bottomDock } = props;
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <header className="sticky top-0 z-20 backdrop-blur bg-white/70 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-blue-600 flex items-center justify-center text-white font-bold">O</div>
            <h1 className="text-lg font-semibold text-gray-900 truncate max-w-[60vw]" title={title}>{title}</h1>
            {planType && (
              <span className="hidden md:inline-flex ml-2 px-2 py-0.5 text-xs rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                {String(planType).toUpperCase()}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <a href="/admin/UploadDocument" className="hidden sm:inline-flex text-sm text-gray-600 hover:text-gray-900">Knowledge</a>
          </div>
        </div>
        {(planType || usage) && (
          <div className="bg-blue-50 border-t border-blue-100 text-blue-800 text-xs py-2 px-4">
            {planType && (<span className="mr-3">Plan: <span className="font-medium uppercase">{planType}</span></span>)}
            {usage && typeof usage.tokens_quota !== 'undefined' && (
              <span className="mr-3">Tokens: {usage.tokens_used}/{usage.tokens_quota}</span>
            )}
            {usage?.docs_count !== undefined && (<span className="mr-3">Docs: {usage.docs_count}</span>)}
            {planType === 'free' && <span className="ml-2">Consider upgrading to <span className="font-medium">Pro</span> for higher limits.</span>}
          </div>
        )}
      </header>

      <div className="max-w-7xl mx-auto px-4">
        <div className="grid grid-cols-12 gap-4 py-4">
          {sidebar ? (
            <aside className="hidden lg:block col-span-3">
              {sidebar}
            </aside>
          ) : null}
          <main className={sidebar ? 'col-span-12 lg:col-span-9' : 'col-span-12'}>
            {children}
          </main>
        </div>
      </div>

      <div className="fixed left-0 right-0 bottom-0 bg-gradient-to-t from-white to-white/70 backdrop-blur border-t border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {bottomDock}
          <div className="mt-2 text-[11px] text-gray-500">Shift+Enter for new line</div>
          <div className="mt-1 text-[11px] text-gray-500">Answers are grounded in your uploaded knowledge. Sources are listed when available.</div>
        </div>
      </div>
    </div>
  );
}


