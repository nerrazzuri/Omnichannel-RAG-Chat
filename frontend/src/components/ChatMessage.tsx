import React from "react";
import { Message } from "../types/chat";
import MessageRenderer from "./MessageRenderer";
import { ReasoningAccordion } from "./ReasoningAccordion";
import { FeedbackActions } from "./FeedbackActions";

interface ChatMessageProps {
  message: Message;
  onFeedback: (messageId: string, isPositive: boolean) => void;
}

function relativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onFeedback,
}) => {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isSystem = message.role === "system";

  return (
    <div
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-6`}
    >
      <div
        className={`flex flex-col max-w-[85%] ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div className="flex items-center space-x-2 mb-1">
          <span
            className={`text-xs font-medium uppercase ${isUser ? "text-blue-600" : isAssistant ? "text-emerald-600" : "text-gray-600"}`}
          >
            {isUser ? "You" : isAssistant ? "Assistant" : "System"}
          </span>
          <span className="text-xs text-gray-400">
            {relativeTime(message.timestamp)}
          </span>
        </div>

        <div
          className={`relative px-4 py-3 rounded-lg shadow-sm ${
            isUser
              ? "bg-blue-600 text-white border border-blue-600 rounded-br-none"
              : isSystem
                ? "bg-gray-100 text-gray-800 border border-gray-300 rounded-bl-none"
                : "bg-white text-gray-900 border border-gray-200 rounded-bl-none"
          }`}
        >
          {!isUser &&
            message.reasoningSteps &&
            message.reasoningSteps.length > 0 && (
              <div className="mb-3">
                <ReasoningAccordion steps={message.reasoningSteps} />
              </div>
            )}

          <div className={isUser ? "text-white" : ""}>
            <MessageRenderer
              content={message.content}
              citations={message.citations}
            />
          </div>
        </div>

        {isAssistant && (
          <FeedbackActions
            messageId={message.id}
            existingFeedback={message.feedback}
            onFeedback={onFeedback}
          />
        )}
      </div>
    </div>
  );
};
