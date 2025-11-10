import React from 'react';
import { createPortal } from 'react-dom';
import { CloseIcon } from './icons';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string | React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmButtonStyle?: 'danger' | 'primary';
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Xác nhận',
  cancelText = 'Hủy',
  confirmButtonStyle = 'danger'
}) => {
  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Handle ESC key
  React.useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  const modalContent = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 animate-fadeIn"
      onClick={handleBackdropClick}
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0
      }}
    >
      {/* Modal Container - Modern Glass Card */}
      <div
        className="relative w-full max-w-md modern-card animate-scaleUp"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          border: '1px solid rgba(255, 255, 255, 0.5)',
          borderRadius: '20px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
          padding: '0',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button - Top Right */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-lg transition-all duration-200 hover:scale-110 active:scale-95 z-10"
          style={{
            backgroundColor: 'rgba(0, 0, 0, 0.05)',
            color: 'var(--color-textSecondary)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';
            e.currentTarget.style.color = 'var(--color-text)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.05)';
            e.currentTarget.style.color = 'var(--color-textSecondary)';
          }}
          title="Đóng (ESC)"
        >
          <CloseIcon />
        </button>

        {/* Icon Header - Warning/Danger */}
        <div className="flex flex-col items-center pt-8 pb-4 px-6">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mb-4 pulse-glow"
            style={{
              backgroundColor: confirmButtonStyle === 'danger' 
                ? 'rgba(239, 68, 68, 0.1)' 
                : 'rgba(59, 130, 246, 0.1)',
              border: `2px solid ${confirmButtonStyle === 'danger' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)'}`
            }}
          >
            <span
              className="text-3xl"
              style={{
                filter: confirmButtonStyle === 'danger' 
                  ? 'drop-shadow(0 2px 4px rgba(239, 68, 68, 0.3))' 
                  : 'drop-shadow(0 2px 4px rgba(59, 130, 246, 0.3))'
              }}
            >
              {confirmButtonStyle === 'danger' ? '⚠️' : 'ℹ️'}
            </span>
          </div>

          {/* Title */}
          <h2
            className="text-xl font-bold text-center mb-2"
            style={{
              color: 'var(--color-text)',
              fontWeight: '700',
              letterSpacing: '-0.01em'
            }}
          >
            {title}
          </h2>
        </div>

        {/* Message */}
        <div className="px-6 pb-6">
          {typeof message === 'string' ? (
            <p
              className="text-sm text-center leading-relaxed"
              style={{
                color: 'var(--color-textSecondary)',
                fontWeight: '400',
                lineHeight: '1.6'
              }}
            >
              {message}
            </p>
          ) : (
            <div style={{ color: 'var(--color-textSecondary)' }}>
              {message}
            </div>
          )}
        </div>

        {/* Divider */}
        <div
          style={{
            height: '1px',
            background: 'linear-gradient(to right, transparent, var(--color-border), transparent)',
            margin: '0 24px'
          }}
        />

        {/* Action Buttons */}
        <div className="flex gap-3 p-6">
          {/* Cancel Button */}
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 hover:scale-105 active:scale-95"
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.05)',
              color: 'var(--color-textPrimary)',
              border: '1px solid var(--color-border)',
              fontWeight: '600'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--color-surfaceHover)';
              e.currentTarget.style.borderColor = 'var(--color-border)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.05)';
              e.currentTarget.style.borderColor = 'var(--color-border)';
            }}
          >
            {cancelText}
          </button>

          {/* Confirm Button - Gradient */}
          <button
            onClick={handleConfirm}
            className={`flex-1 px-4 py-3 rounded-xl text-sm font-semibold text-white transition-all duration-200 hover:scale-105 active:scale-95 shadow-colored hover:shadow-colored-hover ${
              confirmButtonStyle === 'danger' ? 'btn-gradient' : 'btn-gradient-blue'
            }`}
            style={{
              fontWeight: '600',
              boxShadow: confirmButtonStyle === 'danger'
                ? '0 4px 15px 0 rgba(239, 68, 68, 0.4)'
                : '0 4px 15px 0 rgba(30, 64, 175, 0.4)'
            }}
            onMouseEnter={(e) => {
              if (confirmButtonStyle === 'danger') {
                e.currentTarget.style.boxShadow = '0 6px 20px 0 rgba(239, 68, 68, 0.6)';
              } else {
                e.currentTarget.style.boxShadow = '0 6px 20px 0 rgba(30, 64, 175, 0.6)';
              }
            }}
            onMouseLeave={(e) => {
              if (confirmButtonStyle === 'danger') {
                e.currentTarget.style.boxShadow = '0 4px 15px 0 rgba(239, 68, 68, 0.4)';
              } else {
                e.currentTarget.style.boxShadow = '0 4px 15px 0 rgba(30, 64, 175, 0.4)';
              }
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );

  // Use React Portal to render modal at document body level for proper centering
  // This ensures modal is always centered regardless of parent container positioning
  return typeof document !== 'undefined' 
    ? createPortal(modalContent, document.body)
    : null;
};

