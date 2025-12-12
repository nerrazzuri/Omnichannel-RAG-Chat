import React, { useEffect, useState } from 'react';
import { ReasoningStep } from '../types/chat';

interface ReasoningAccordionProps {
    steps: ReasoningStep[];
}

export const ReasoningAccordion: React.FC<ReasoningAccordionProps> = ({ steps }) => {
    const STORAGE_KEY = 'reasoningExpanded';
    const [isOpen, setIsOpen] = useState<boolean>(false);

    useEffect(() => {
        try {
            const saved = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null;
            if (saved === 'true') setIsOpen(true);
        } catch {
            // no-op
        }
    }, []);

    if (!steps || steps.length === 0) return null;

    const toggle = () => {
        setIsOpen((prev) => {
            const next = !prev;
            try {
                if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, String(next));
            } catch {
                // ignore
            }
            return next;
        });
    };

    return (
        <div className="mt-2 border border-gray-200 rounded-md overflow-hidden">
            <button
                onClick={toggle}
                className="w-full px-4 py-2 bg-gray-50 flex items-center justify-between text-sm text-gray-700 hover:bg-gray-100 transition-colors"
            >
                <span className="font-medium">Supporting Explanation</span>
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
                    <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 text-amber-900 p-3 text-xs">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mt-0.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.72-1.36 3.485 0l6.518 11.6A2 2 0 0 1 16.518 18H3.482a2 2 0 0 1-1.742-3.3l6.517-11.6zM11 13a1 1 0 1 0-2 0v1a1 1 0 0 0 2 0v-1zm-1-2a1 1 0 0 0 1-1V7a1 1 0 1 0-2 0v3a1 1 0 0 0 1 1z" clipRule="evenodd" /></svg>
                        <p>This is a high‑level supporting explanation of how the answer was assembled. It is not raw model chain‑of‑thought and may be imperfect—verify critical steps.</p>
                    </div>
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
