import React from "react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="relative overflow-hidden bg-white">
        <div className="max-w-7xl mx-auto px-6 py-16 sm:py-20 lg:py-24">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
              Turn your documents into a trusted, enterprise-grade chatbot
            </h1>
            <p className="mt-4 text-lg text-gray-600">
              Omnichannel RAG helps your teams ask better questions, find vetted
              answers, and act with confidence—powered by your knowledge base.
            </p>
            <div className="mt-8 flex items-center justify-center gap-3">
              <a
                href="/chat"
                className="inline-flex items-center rounded-md bg-blue-600 px-5 py-3 text-white font-medium hover:bg-blue-700 shadow"
              >
                Ask Your Knowledge Base
              </a>
              <a
                href="/admin/super"
                className="inline-flex items-center rounded-md border border-gray-300 px-5 py-3 text-gray-900 hover:bg-gray-50"
              >
                Admin Console
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid gap-6 md:grid-cols-3">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="text-sm font-medium text-blue-700 mb-2">
              Retrieve
            </div>
            <p className="text-gray-700 text-sm">
              Connect your docs, emails, and knowledge bases. Our retrieval
              pipeline keeps context fresh and relevant.
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="text-sm font-medium text-emerald-700 mb-2">
              Reason
            </div>
            <p className="text-gray-700 text-sm">
              Enable grounded answers with built-in citations and optional
              reasoning trace to drive trust and transparency.
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="text-sm font-medium text-purple-700 mb-2">
              Govern
            </div>
            <p className="text-gray-700 text-sm">
              Enforce tenant isolation, role-based access, and usage controls
              out of the box. Built for enterprise.
            </p>
          </div>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <a
            href="/chat"
            className="block rounded-lg border border-gray-200 p-6 hover:shadow-sm bg-white"
          >
            <div className="font-semibold text-gray-900 mb-1">Try the Chat</div>
            <div className="text-sm text-gray-600">
              Ask questions about your documents, explore follow-ups, and see
              relevant sources.
            </div>
          </a>
          <a
            href="/admin/super"
            className="block rounded-lg border border-gray-200 p-6 hover:shadow-sm bg-white"
          >
            <div className="font-semibold text-gray-900 mb-1">
              Configure &amp; Monitor
            </div>
            <div className="text-sm text-gray-600">
              Upload content, manage tenants, and review usage—all in one place.
            </div>
          </a>
        </div>
      </main>

      <footer className="border-t border-gray-200 mt-12 py-8 text-center text-sm text-gray-500">
        © {new Date().getFullYear()} Omnichannel RAG. All rights reserved.
      </footer>
    </div>
  );
}
