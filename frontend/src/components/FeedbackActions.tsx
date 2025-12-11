import React, { useState } from 'react';
import { Feedback } from '../types/chat';

interface FeedbackActionsProps {
    messageId: string;
    existingFeedback?: Feedback;
    onFeedback: (messageId: string, isPositive: boolean) => void;
}

export const FeedbackActions: React.FC<FeedbackActionsProps> = ({
    messageId,
    existingFeedback,
    onFeedback,
}) => {
    const [feedback, setFeedback] = useState<Feedback | undefined>(existingFeedback);

    const handleFeedback = (isPositive: boolean) => {
        const newFeedback = { isPositive };
        setFeedback(newFeedback);
        onFeedback(messageId, isPositive);
    };

    return (
        <div className="flex items-center space-x-2 mt-2 text-gray-400">
            <button
                onClick={() => handleFeedback(true)}
                className={`p-1 rounded hover:bg-gray-100 transition-colors ${feedback?.isPositive === true ? 'text-green-600 bg-green-50' : ''
                    }`}
                title="Helpful"
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-5 h-5"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a2.25 2.25 0 012.25 2.25V7.38a2.25 2.25 0 11-4.5 0 .21.21 0 00-.103.024 4.878 4.878 0 01-1.423 2.3.75.75 0 00-.217.447v5.853c0 .414.336.75.75.75h2.842a.75.75 0 01.694.954l-1.216 4.562A1.125 1.125 0 0113.781 22h-2.811a4.5 4.5 0 01-3.63-1.845 4.5 4.5 0 01-.87-2.929 2.5 2.5 0 11-5 0V9.75a2.25 2.25 0 012.161-2.25z"
                    />
                </svg>
            </button>
            <button
                onClick={() => handleFeedback(false)}
                className={`p-1 rounded hover:bg-gray-100 transition-colors ${feedback?.isPositive === false ? 'text-red-600 bg-red-50' : ''
                    }`}
                title="Not Helpful"
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-5 h-5"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M7.5 15h2.25a2.25 2.25 0 100-4.5H7.5a2.25 2.25 0 000 4.5zM15.75 15h2.25a2.25 2.25 0 100-4.5h-2.25a2.25 2.25 0 000 4.5z"
                    />
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
                    />
                </svg>
            </button>
        </div>
    );
};
