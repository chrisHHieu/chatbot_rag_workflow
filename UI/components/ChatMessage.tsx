import React from 'react';
import { Message } from '../types';
import { OOSBrandIcon, UserIcon } from './icons';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage = React.memo<ChatMessageProps>(({ message }) => {
  const isModel = message.role === 'model';

  return (
    <div className={`flex items-start gap-4 group ${isModel ? 'animate-slideInLeft' : 'flex-row-reverse animate-slideInRight'}`}>
      {/* Avatar với animation đẹp */}
      <div
        className="flex-shrink-0 rounded-full flex items-center justify-center shadow-lg transform transition-all duration-300 group-hover:scale-110 overflow-hidden"
        style={{
          width: isModel ? '48px' : '40px',
          height: isModel ? '48px' : '40px',
          background: isModel 
            ? 'var(--color-surface)'
            : `linear-gradient(to bottom right, var(--color-primary), var(--color-primaryHover))`,
          boxShadow: isModel 
            ? '0 10px 15px -3px rgba(37, 99, 235, 0.3), 0 4px 6px -2px rgba(37, 99, 235, 0.2)'
            : '0 10px 15px -3px rgba(29, 78, 216, 0.4), 0 4px 6px -2px rgba(29, 78, 216, 0.3)',
          border: isModel ? '2px solid var(--color-border)' : 'none',
          padding: '0'
        }}
      >
        {isModel ? (
          <OOSBrandIcon style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <UserIcon className="w-6 h-6 text-white" />
        )}
      </div>
      
      {/* Message bubble với hiệu ứng đẹp - Enhanced */}
      <div
        className={`rounded-2xl p-4 max-w-3xl transition-all duration-300 group-hover:-translate-y-1 hover-lift ${
          isModel ? 'modern-card' : 'shadow-colored'}`}
        style={{
          background: isModel
            ? 'rgba(255, 255, 255, 0.9)'
            : 'var(--gradient-blue)',
          color: isModel ? 'var(--color-text)' : '#ffffff',
          border: isModel ? '1px solid var(--color-borderGlass)' : 'none',
          boxShadow: isModel 
            ? '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.6)'
            : '0 10px 25px rgba(30, 64, 175, 0.35), 0 4px 10px rgba(30, 64, 175, 0.2)',
          backdropFilter: isModel ? 'blur(20px) saturate(180%)' : 'none',
          WebkitBackdropFilter: isModel ? 'blur(20px) saturate(180%)' : 'none'
        }}
      >
        {isModel ? (
          <MarkdownRenderer text={message.content} isStreaming={false} />
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        )}
        
        {/* Timestamp (hiển thị luôn) */}
        <div 
          className="mt-2 text-xs transition-opacity duration-300"
          style={{
            color: isModel ? 'var(--color-textSecondary)' : 'rgba(255, 255, 255, 0.8)'
          }}
        >
          {new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  return prevProps.message.content === nextProps.message.content &&
         prevProps.message.role === nextProps.message.role;
});