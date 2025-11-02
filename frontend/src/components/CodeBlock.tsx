import React from 'react';

type Props = React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
};

export default function CodeBlock(props: Props) {
  const { inline, className, children, ...rest } = props;
  const code = String(children || '');
  const match = /language-(\w+)/.exec(className || '');
  if (inline) {
    return <code className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-800" {...rest}>{children}</code>;
  }
  const text = code.replace(/\n$/, '');
  const onCopy = async () => {
    try { await navigator.clipboard.writeText(text); } catch {}
  };
  return (
    <div className="relative group">
      <pre className={`rounded-lg border border-gray-200 bg-gray-50 p-3 overflow-x-auto ${className || ''}`} {...rest}>
        <code>{text}</code>
      </pre>
      <button
        type="button"
        onClick={onCopy}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-300 bg-white hover:bg-gray-50 text-gray-700"
        aria-label="Copy code"
      >
        Copy
      </button>
    </div>
  );
}


