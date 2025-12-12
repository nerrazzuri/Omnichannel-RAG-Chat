import React from 'react';
import { Message } from '../types/chat';
import { ChatMessage } from './ChatMessage';

type MessageListProps = {
  messages: Message[];
  loading: boolean;
  onFeedback: (messageId: string, isPositive: boolean) => void;
  onPromptClick?: (text: string) => void;
};

export default function MessageList({ messages, loading, onFeedback, onPromptClick }: MessageListProps) {
  const starters = [
    'Summarize last quarter’s performance',
    'List the top customer questions',
    'What changed in the latest release notes?',
    'Draft a response to a refund request'
  ];

  return (
    <>
      {messages.length === 0 && (
        <div className="mx-auto mt-16 max-w-2xl text-center text-gray-700">
          <h3 className="text-2xl font-semibold text-gray-900 mb-2">Welcome</h3>
          <p className="text-sm text-gray-600">Ask about your uploaded knowledge or try one of these:</p>
          <div className="mt-4 flex flex-wrap gap-2 justify-center">
            {starters.map((s) => (
              <button
                key={s}
                onClick={() => onPromptClick?.(s)}
                className="text-xs rounded-full border border-gray-300 px-3 py-1 hover:bg-gray-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
      {messages.map((m) => (
        <ChatMessage
          key={m.id}
          message={m}
          onFeedback={onFeedback}
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
    </>
  );
}


