import React, { useRef, useEffect } from 'react';

export interface ChatSession {
  id: string;
  title: string; // Title hiển thị (từ file đầu tiên hoặc "New Chat")
  createdAt: number; // Timestamp
  lastMessage?: string; // Last message preview (optional, for future)
}

interface ChatTabsProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSessionSelect: (sessionId: string | null) => void;
  onNewChat: () => void;
  onCloseSession?: (sessionId: string) => void;
}

export const ChatTabs: React.FC<ChatTabsProps> = ({
  sessions,
  activeSessionId,
  onSessionSelect,
  onNewChat,
  onCloseSession,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // ✅ Enable mouse wheel horizontal scrolling
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      // Chỉ xử lý khi scroll vertical (deltaY) trong container ngang
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        // Convert vertical scroll thành horizontal scroll
        e.preventDefault();
        container.scrollLeft += e.deltaY;
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, []);

  // ✅ Ẩn ChatTabs hoàn toàn khi chưa có session nào
  if (sessions.length === 0) {
    return null;
  }

  return (
    <div className="flex-shrink-0 flex items-center gap-2 px-4 py-2 border-b border-slate-200/80 bg-white/95 backdrop-blur-sm">
      {/* New Chat Button - Chỉ hiển thị khi đã có session */}
      <button
        onClick={onNewChat}
        className="flex-shrink-0 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 hover:scale-105 active:scale-95 btn-gradient-blue text-white shadow-colored hover:shadow-colored-hover"
      >
        <span className="flex items-center gap-2">
          <span className="text-lg font-bold">+</span>
          <span>New Chat</span>
        </span>
      </button>

      {/* Divider */}
      <div className="flex-shrink-0 w-px h-6 bg-slate-300"></div>

      {/* Session Tabs Container - Scrollable */}
      <div 
        ref={scrollContainerRef}
        className="flex items-center gap-2 overflow-x-auto scrollbar-visible"
        style={{
          flex: '1 1 0',
          minWidth: 0,
          maxWidth: '100%',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        <div className="flex items-center gap-2" style={{ minWidth: 'max-content' }}>
          {sessions.map((session) => {
            const isActive = activeSessionId === session.id;
            return (
              <div
                key={session.id}
                className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 group relative ${
                  isActive
                    ? 'modern-card border-2 border-blue-400 shadow-colored'
                    : 'glass-card border border-slate-300 hover:shadow-medium hover-lift'
                }`}
                onClick={() => onSessionSelect(session.id)}
                style={{
                  minWidth: '120px',
                  maxWidth: '250px',
                }}
              >
                {/* Active indicator */}
                {isActive && (
                  <div className="absolute -top-0.5 left-1/2 transform -translate-x-1/2 w-8 h-1 bg-blue-500 rounded-b-full"></div>
                )}
                
                {/* Session title */}
                <span
                  className="text-sm font-medium truncate flex-1 text-left"
                  style={{
                    color: isActive
                      ? 'var(--color-primary)'
                      : 'var(--color-textPrimary)',
                  }}
                  title={session.title}
                >
                  {session.title}
                </span>
                
              {/* Close button - Luôn hiển thị */}
              {onCloseSession && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCloseSession(session.id);
                  }}
                  className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center transition-all duration-200 ${
                    isActive
                      ? 'opacity-70 hover:opacity-100 hover:bg-blue-200 text-blue-700'
                      : 'opacity-60 group-hover:opacity-100 hover:bg-slate-300 text-slate-600'
                  }`}
                  style={{ fontSize: '18px', lineHeight: '1' }}
                  title="Close session"
                >
                  ×
                </button>
              )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

