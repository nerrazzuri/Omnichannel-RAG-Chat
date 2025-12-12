import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CodeBlock from './CodeBlock';
import { beautifyMarkdown } from '../lib/beautify';

type Props = {
  content: string;
  citations?: string[];
};

function isUrl(s: string) {
  try { const u = new URL(s); return u.protocol === 'http:' || u.protocol === 'https:'; } catch { return false; }
}

export default function MessageRenderer({ content, citations }: Props) {
  const enabled = process.env.NEXT_PUBLIC_RESPONSE_BEAUTIFY === 'true';
  const text = enabled ? beautifyMarkdown(content || '') : (content || '');
  return (
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm as any]}
        skipHtml
        components={{
          code: (props) => <div className="not-prose"><CodeBlock {...props} /></div> as any,
          table: (props) => <div className="overflow-x-auto"><table {...props} /></div> as any,
          a: (props) => <a target="_blank" rel="noopener noreferrer" {...props} />
        }}
      >
        {text}
      </ReactMarkdown>

      {Array.isArray(citations) && citations.length > 0 && (
        <div className="mt-3 border-t border-gray-200 pt-2">
          <div className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-1">Sources</div>
          <ol className="list-decimal list-inside space-y-1">
            {citations.map((c, idx) => (
              <li key={idx} className="text-xs text-gray-600 break-words">
                {isUrl(c) ? (
                  <a href={c} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    {c}
                  </a>
                ) : (
                  <code className="bg-gray-100 px-1 py-0.5 rounded">{c}</code>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}


