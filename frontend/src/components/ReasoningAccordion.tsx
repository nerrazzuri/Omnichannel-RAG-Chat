import React, { useState } from 'react';
import { ReasoningStep } from '../types/chat';

interface ReasoningAccordionProps {
    steps: ReasoningStep[];
}

export const ReasoningAccordion: React.FC<ReasoningAccordionProps> = ({ steps }) => {
    const [isOpen, setIsOpen] = useState(false);

    if (!steps || steps.length === 0) return null;

    return (
        <div className="mt-2 border border-gray-200 rounded-md overflow-hidden">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full px-4 py-2 bg-gray-50 flex items-center justify-between text-sm text-gray-600 hover:bg-gray-100 transition-colors"
            >
                <span className="font-medium">View Thought Process</span>
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
            </button>
            {isOpen && (
                <div className="p-4 bg-white space-y-4">
                    {steps.map((step, index) => (
                        <div key={index} className="text-sm">
                            <div className="flex items-center space-x-2 mb-1">
                                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-mono uppercase">
                                    {step.action}
                                </span>
                            </div>
                            <div className="pl-2 border-l-2 border-gray-100 ml-1 space-y-1">
                                <div className="text-gray-600">
                                    <span className="font-semibold text-xs text-gray-400 uppercase tracking-wider">Input:</span>{' '}
                                    <span className="font-mono text-xs">{step.input}</span>
                                </div>
                                {step.thought && (
                                    <div className="text-gray-700 italic">
                                        <span className="font-semibold text-xs text-gray-400 uppercase tracking-wider">Thought:</span>{' '}
                                        {step.thought}
                                    </div>
                                )}
                                {step.output && (
                                    <div className="text-gray-800 bg-gray-50 p-2 rounded font-mono text-xs whitespace-pre-wrap">
                                        <span className="font-semibold text-xs text-gray-400 uppercase tracking-wider block mb-1">
                                            Output:
                                        </span>
                                        {step.output}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
