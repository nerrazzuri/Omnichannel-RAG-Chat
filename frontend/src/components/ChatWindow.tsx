import React, { useEffect, useRef, useState } from "react";

type ChatWindowProps = {
  children: React.ReactNode;
  autoScrollTrigger?: any;
};

export default function ChatWindow({
  children,
  autoScrollTrigger,
}: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const [showScrollDown, setShowScrollDown] = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoScrollTrigger]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      setShowScrollDown(!nearBottom);
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto pt-4 pb-28 space-y-6"
      >
        {children}
        <div ref={endRef} />
      </div>
      {showScrollDown && (
        <button
          onClick={() => endRef.current?.scrollIntoView({ behavior: "smooth" })}
          className="fixed right-5 bottom-24 h-9 w-9 rounded-full shadow bg-white border border-gray-200 flex items-center justify-center text-gray-700 hover:bg-gray-50"
          aria-label="Scroll to bottom"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
      )}
    </>
  );
}
