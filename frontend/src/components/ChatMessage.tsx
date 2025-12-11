import React from 'react';
import { Message } from '../types/chat';
import MessageRenderer from './MessageRenderer';
import { ReasoningAccordion } from './ReasoningAccordion';
import { FeedbackActions } from './FeedbackActions';

interface ChatMessageProps {
    message: Message;
    onFeedback: (messageId: string, isPositive: boolean) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onFeedback }) => {
    const isUser = message.role === 'user';

    return (
        <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
            <div
                className={`flex flex-col max-w-[85%] ${isUser ? 'items-end' : 'items-start'
                    }`}
            >
                <div className="flex items-center space-x-2 mb-1">
                    <span className="text-xs font-semibold text-gray-500 uppercase">
                        {message.role === 'user' ? 'You' : 'AI Assistant'}
                    </span>
                    <span className="text-xs text-gray-400">
                        {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                </div>

                <div
                    className={`relative px-4 py-3 rounded-lg shadow-sm ${isUser
                            ? 'bg-blue-600 text-white rounded-br-none'
                            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'
                        }`}
                >
                    {!isUser && message.reasoningSteps && message.reasoningSteps.length > 0 && (
                        <div className="mb-3">
                            <ReasoningAccordion steps={message.reasoningSteps} />
                        </div>
                    )}

                    <div className={isUser ? 'text-white' : ''}>
                        <MessageRenderer content={message.content} />
                    </div>
                </div>

                {!isUser && (
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
