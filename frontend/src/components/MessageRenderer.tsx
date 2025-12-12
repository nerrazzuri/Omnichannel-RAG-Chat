import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CodeBlock from './CodeBlock';
import { beautifyMarkdown } from '../lib/beautify/index';

export default function MessageRenderer({ content }: { content: string }) {
  const enabled = process.env.NEXT_PUBLIC_RESPONSE_BEAUTIFY === 'true';
  const text = enabled ? beautifyMarkdown(content || '') : (content || '');
  return (
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm as any]}
        skipHtml
        components={{
          code: (props) => <CodeBlock {...props} /> as any,
          table: (props) => <div className="overflow-x-auto"><table {...props} /></div> as any,
          a: (props) => <a target="_blank" rel="noopener noreferrer" {...props} />
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}


