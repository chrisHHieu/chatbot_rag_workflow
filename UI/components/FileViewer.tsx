import React from 'react';
import { UploadedFile } from '../types';
import { UploadIcon, PdfIcon, FileTextIcon, OOSBrandIcon, DocumentSearchIcon, CloseIcon } from './icons';
import { DocxViewer } from './DocxViewer';
import { ConfirmModal } from './ConfirmModal';

interface SidebarProps {
  uploadedFiles: UploadedFile[];
  selectedFile: UploadedFile | null;
  onFileSelect: (file: UploadedFile) => void;
  onUploadClick: () => void;
  onRemoveFile: (fileId: string) => void;
  onFilesDropped?: (files: FileList) => void;
  sessionId?: string | null;
  onDeleteAllFiles?: () => void;
}

const FileItemLoader: React.FC<{ progressText?: string }> = ({ progressText }) => (
    <div className="flex items-center gap-2">
        <div className="relative w-5 h-5">
            {/* Outer ring */}
            <div className="absolute inset-0 border-2 border-slate-200 rounded-full"></div>
            {/* Spinning ring */}
            <div className="absolute inset-0 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
        {progressText && (
            <span className="text-xs animate-pulse" style={{ 
              color: 'var(--color-textSecondary)',
              fontWeight: '400'
            }}>{progressText}</span>
        )}
    </div>
);

export const Sidebar = React.memo<SidebarProps>(({ uploadedFiles, selectedFile, onFileSelect, onUploadClick, onRemoveFile, onFilesDropped, sessionId, onDeleteAllFiles }) => {
  const [isDragOver, setIsDragOver] = React.useState(false);
  const [dragCounter, setDragCounter] = React.useState(0);
  const [showDeleteAllModal, setShowDeleteAllModal] = React.useState(false);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragCounter(prev => prev + 1);
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragCounter(prev => {
      const newCounter = prev - 1;
      if (newCounter === 0) {
        setIsDragOver(false);
      }
      return newCounter;
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes('Files')) {
      e.dataTransfer.dropEffect = 'copy';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    setDragCounter(0);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0 && onFilesDropped) {
      onFilesDropped(e.dataTransfer.files);
    }
  };

  return (
    <div 
      className="w-2/5 flex flex-col border-r p-4 relative modern-card" 
      style={{ backgroundColor: 'rgba(255, 255, 255, 0.9)', borderColor: 'var(--color-borderGlass)' }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
        {/* Header - OPTIMIZED LAYOUT */}
        <div className="flex justify-between items-center mb-4 px-2 py-3 flex-shrink-0">
            <div className="flex items-center gap-3">
            {/* Logo với kích thước cố định, không bị méo - tỷ lệ 1.91:1 */}
            <div className="flex-shrink-0" style={{ width: '76px', height: '40px' }}>
              <OOSBrandIcon style={{ width: '100%', height: '100%' }} />
              </div>
            
            {/* Text content với vertical alignment tốt hơn */}
            <div className="flex flex-col justify-center">
              <h1 
                className="text-base font-bold leading-tight" 
                style={{ 
                  color: 'var(--color-text)',
                  letterSpacing: '-0.01em'
                }}
              >
                Trợ lý AI Dữ liệu Doanh nghiệp từ OOS Software
              </h1>
              <p 
                className="text-xs leading-tight mt-0.5" 
                style={{ 
                  color: 'var(--color-textSecondary)',
                  fontWeight: '400'
                }}
              >
                Quản lý và truy cập tài liệu doanh nghiệp của bạn tại đây
              </p>
            </div>
          </div>
          
          {/* Upload button với animation - LỚN HƠN */}
            <div className="flex gap-2">
            <button 
              onClick={onUploadClick} 
              className="p-3.5 rounded-lg transition-all duration-300 hover:scale-110 active:scale-95 relative overflow-hidden group" 
              style={{ 
                color: 'var(--color-textSecondary)',
                backgroundColor: 'transparent',
                minWidth: '44px',
                minHeight: '44px'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-surfaceHover)';
                e.currentTarget.style.color = 'var(--color-primary)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = 'var(--color-textSecondary)';
                e.currentTarget.style.boxShadow = 'none';
              }}
              title="Upload Document"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/20 to-blue-500/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700"></div>
              <UploadIcon className="w-6 h-6 relative z-10" />
                 </button>
            </div>
        </div>
        
        {/* Session ID Section - Enhanced with clear separation */}
        {sessionId && (
          <>
            <div className="flex-shrink-0 mb-3 px-2">
              <div className="px-3 py-2 rounded-lg text-xs flex items-center gap-2 break-all" 
                style={{ 
                  backgroundColor: 'rgba(239, 246, 255, 0.6)',
                  color: 'var(--color-textSecondary)',
                  border: '1px solid rgba(59, 130, 246, 0.2)',
                  fontWeight: '500',
                  wordBreak: 'break-all',
                  overflowWrap: 'break-word'
                }} 
                title={sessionId}
              >
                <span className="inline-block w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse flex-shrink-0"></span>
                <span className="text-xs font-semibold" style={{ 
                  color: 'var(--color-sectionHeader)',
                  fontWeight: '600'
                }}>Session:</span>
                <span style={{ fontWeight: '500', fontFamily: 'monospace' }}>
                  {sessionId}
                </span>
              </div>
            </div>
            {/* Small divider after Session ID */}
            <div className="flex-shrink-0 mb-3">
              <div style={{
                height: '1px',
                backgroundColor: 'var(--color-border)',
                margin: '0 12px'
              }}></div>
            </div>
          </>
        )}

        {/* Drag & Drop Overlay */}
        {isDragOver && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-blue-500/10 backdrop-blur-sm animate-dragOver" style={{ border: '2px dashed var(--color-primary)', borderRadius: '12px', margin: '8px' }}>
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center animate-uploadPulse">
                  <UploadIcon className="w-8 h-8" style={{ color: 'var(--color-primary)' }} />
                </div>
              </div>
              <h3 className="text-lg font-bold mb-2" style={{ 
                color: 'var(--color-primary)',
                fontWeight: '700',
                letterSpacing: '-0.01em'
              }}>Thả tài liệu vào đây</h3>
              <p className="text-sm" style={{ 
                color: 'var(--color-textSecondary)',
                fontWeight: '400'
              }}>Kéo và thả file để tải lên</p>
            </div>
          </div>
        )}

        {/* SECTION 1: Uploaded Files List - 30% of available space (flex: 3) */}
        <div className="flex flex-col mb-4" style={{ flex: '3', minHeight: '0' }}>
          {/* Section Header with background */}
          <div className="px-3 py-2.5 mb-3 rounded-lg" style={{
            backgroundColor: 'rgba(248, 250, 252, 0.8)',
            border: '1px solid var(--color-border)',
            borderBottom: '2px solid var(--color-primary)'
          }}>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold flex items-center gap-2" style={{ 
                color: 'var(--color-sectionHeader)',
                fontWeight: '600',
                letterSpacing: '-0.01em'
              }}>
                <span>📁 Danh sách tài liệu đã tải lên</span>
                {uploadedFiles.length > 0 && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-600 font-medium animate-scaleUp">
                    {uploadedFiles.length}
                  </span>
                )}
              </h2>
              {uploadedFiles.length > 0 && onDeleteAllFiles && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowDeleteAllModal(true);
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
                  style={{
                    color: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    fontWeight: '500'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                    e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                    e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                  }}
                  title="Xóa tất cả tài liệu (giữ lại session)"
                >
                  Xóa tất cả
                </button>
              )}
            </div>
          </div>
          
          {/* Files List Container - Flex grow to fill available space in 30% section */}
          <div className="flex-grow overflow-y-auto space-y-1.5 pr-2 scrollbar-auto-hide" style={{
            paddingLeft: '4px',
            paddingRight: '8px',
            minHeight: '60px' // Minimum height for empty state
          }}>
                {uploadedFiles.length > 0 ? (
                    uploadedFiles.map((upFile, index) => (
                        <div
                            key={upFile.id}
                            onClick={() => upFile.status === 'ready' && onFileSelect(upFile)}
                            className={`group flex items-center gap-3 p-2.5 rounded-lg transition-all duration-300 ease-in-out animate-fileItemSlideIn ${
                                upFile.status === 'uploading' 
                                    ? 'opacity-80 cursor-wait' 
                                    : upFile.status === 'deleting'
                                    ? 'opacity-80 cursor-wait'
                                    : upFile.status === 'error'
                                    ? 'opacity-70 cursor-not-allowed'
                                    : 'cursor-pointer hover:shadow-md hover:scale-[1.02] active:scale-[0.98]'
                            } ${
                                selectedFile?.id === upFile.id && upFile.status === 'ready'
                                ? 'font-semibold shadow-inner ring-2 ring-blue-500/30' 
                                : ''
                            }`}
                            style={{
                              animationDelay: `${index * 0.05}s`,
                              backgroundColor: upFile.status === 'uploading' 
                                ? 'rgba(59, 130, 246, 0.1)' 
                                : upFile.status === 'deleting'
                                ? 'rgba(249, 115, 22, 0.1)'
                                : upFile.status === 'error'
                                ? 'rgba(239, 68, 68, 0.1)'
                                : selectedFile?.id === upFile.id && upFile.status === 'ready'
                                ? 'var(--color-surfaceHover)'
                                : 'transparent',
                              color: selectedFile?.id === upFile.id && upFile.status === 'ready'
                                ? 'var(--color-primary)'
                                : 'var(--color-text)',
                              '--hover-bg': 'var(--color-surfaceHover)'
                            } as React.CSSProperties & { '--hover-bg'?: string }}
                            onMouseEnter={(e) => {
                              if (upFile.status === 'ready' && selectedFile?.id !== upFile.id) {
                                e.currentTarget.style.backgroundColor = 'var(--color-surfaceHover)';
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (selectedFile?.id !== upFile.id) {
                                e.currentTarget.style.backgroundColor = 'transparent';
                              }
                            }}
                        >
                            {upFile.file.type === 'application/pdf' ? (
                              <PdfIcon className="w-5 h-5 flex-shrink-0" style={{ color: '#ef4444' }} />
                            ) : (
                              <FileTextIcon className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--color-primary)' }} />
                            )}
                            <div className="flex-grow truncate">
                                <p className="font-medium text-sm truncate" style={{ 
                                  color: selectedFile?.id === upFile.id && upFile.status === 'ready'
                                    ? 'var(--color-primary)'
                                    : 'var(--color-textPrimary)',
                                  fontWeight: selectedFile?.id === upFile.id && upFile.status === 'ready' ? '600' : '500'
                                }}>{upFile.fileName}</p>
                                <p className="text-xs" style={{ 
                                  color: 'var(--color-textTertiary)',
                                  fontWeight: '400'
                                }}>{ ((upFile.fileSize || upFile.file.size) / 1024).toFixed(2) } KB</p>
                            </div>
                             <div className="flex-shrink-0">
                                {upFile.status === 'uploading' ? (
                                    <FileItemLoader progressText="Đang xử lý..." />
                                ) : upFile.status === 'deleting' ? (
                                    <FileItemLoader progressText="Đang xóa..." />
                                ) : upFile.status === 'error' ? (
                                    <span className="text-xs text-red-500">Lỗi</span>
                                ) : (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onRemoveFile(upFile.id);
                                        }}
                                        className={`w-5 h-5 transition-opacity ${
                                            uploadedFiles.length === 1 
                                                ? 'opacity-100' 
                                                : 'opacity-60 group-hover:opacity-100'
                                        }`}
                                        style={{ color: 'var(--color-textSecondary)' }}
                                        onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                                        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-textSecondary)'}
                                        title="Remove file"
                                    >
                                        <CloseIcon />
                                    </button>
                                )}
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="text-center p-6 animate-fadeIn">
                        <div className="mb-3 flex justify-center">
                            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
                                <DocumentSearchIcon className="w-6 h-6" style={{ color: 'var(--color-textTertiary)' }} />
                            </div>
                        </div>
                        <p className="text-sm mb-2 font-semibold" style={{ 
                          color: 'var(--color-textPrimary)',
                          fontWeight: '600'
                        }}>Chưa có tài liệu</p>
                        <p className="text-xs" style={{ 
                          color: 'var(--color-textTertiary)',
                          fontWeight: '400'
                        }}>Kéo thả file hoặc nhấn nút upload để bắt đầu</p>
                    </div>
                )}
            </div>
        </div>

        {/* Visual Divider - Clear separation between sections */}
        <div className="flex-shrink-0 my-3">
          <div style={{
            height: '2px',
            background: 'linear-gradient(to right, transparent, var(--color-border), transparent)',
            margin: '0 8px'
          }}></div>
        </div>

        {/* SECTION 2: File Preview - 70% of available space (flex: 7) */}
        <div className="flex flex-col overflow-hidden" style={{ flex: '7', minHeight: '0' }}>
          {/* Section Header with background */}
          <div className="px-3 py-2.5 mb-3 rounded-lg flex-shrink-0" style={{
            backgroundColor: 'rgba(248, 250, 252, 0.8)',
            border: '1px solid var(--color-border)',
            borderBottom: '2px solid var(--color-accentGreen)'
          }}>
            <h2 className="text-sm font-semibold flex items-center gap-2" style={{ 
              color: 'var(--color-sectionHeader)',
              fontWeight: '600',
              letterSpacing: '-0.01em'
            }}>
              <span>👁️ Bản xem trước tài liệu</span>
              {selectedFile && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-600 font-medium animate-scaleUp ml-auto">
                  ✓ Đã chọn
                </span>
              )}
            </h2>
          </div>
            <div className="flex-grow overflow-auto rounded-lg transition-all duration-300 scrollbar-auto-hide" style={{ backgroundColor: 'var(--color-background)', borderColor: 'var(--color-border)', border: '1px solid var(--color-border)' }}>
              {selectedFile ? (
                  <>
                      {selectedFile.status === 'uploading' ? (
                          <div className="w-full h-full flex flex-col items-center justify-center text-center p-8">
                              <div className="relative w-16 h-16 mb-4">
                                  {/* Outer ring */}
                                  <div className="absolute inset-0 border-4 border-slate-200 rounded-full"></div>
                                  {/* Spinning ring */}
                                  <div className="absolute inset-0 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                              </div>
                              <h3 className="font-semibold mb-2" style={{ 
                                color: 'var(--color-textPrimary)',
                                fontWeight: '600'
                              }}>Đang xử lý tài liệu...</h3>
                              <p className="text-sm" style={{ 
                                color: 'var(--color-textSecondary)',
                                fontWeight: '400'
                              }}>Vui lòng đợi trong giây lát</p>
                          </div>
                      ) : selectedFile.status === 'deleting' ? (
                          <div className="w-full h-full flex flex-col items-center justify-center text-center p-8">
                              <div className="relative w-16 h-16 mb-4">
                                  {/* Outer ring */}
                                  <div className="absolute inset-0 border-4 border-slate-200 rounded-full"></div>
                                  {/* Spinning ring */}
                                  <div className="absolute inset-0 border-4 border-orange-600 border-t-transparent rounded-full animate-spin"></div>
                              </div>
                              <h3 className="font-semibold mb-2" style={{ 
                                color: 'var(--color-textPrimary)',
                                fontWeight: '600'
                              }}>Đang xóa tài liệu...</h3>
                              <p className="text-sm" style={{ 
                                color: 'var(--color-textSecondary)',
                                fontWeight: '400'
                              }}>Vui lòng đợi trong giây lát</p>
                          </div>
                      ) : selectedFile.status === 'error' ? (
                          <div className="w-full h-full flex flex-col items-center justify-center text-center p-8">
                              <div className="w-16 h-16 mb-4 rounded-full bg-red-100 flex items-center justify-center">
                                  <span className="text-2xl">⚠️</span>
                              </div>
                              <h3 className="font-semibold mb-2" style={{ 
                                color: '#dc2626',
                                fontWeight: '600'
                              }}>Lỗi khi xử lý</h3>
                              <p className="text-sm" style={{ 
                                color: '#ef4444',
                                fontWeight: '400'
                              }}>Không thể tải tài liệu này</p>
                          </div>
                      ) : selectedFile.file.type === 'application/pdf' && selectedFile.url ? (
                          <iframe src={selectedFile.url} className="w-full h-full border-none min-h-[400px]" title={selectedFile.file.name} />
                      ) : selectedFile.file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' && selectedFile.url ? (
                          <DocxViewer url={selectedFile.url} fileName={selectedFile.fileName} />
                      ) : selectedFile.url ? (
                          <iframe src={selectedFile.url} className="w-full h-full border-none min-h-[400px]" title={selectedFile.file.name} />
                      ) : (
                          <pre className="text-sm whitespace-pre-wrap break-words font-sans p-4">{selectedFile.content || '[Document content]'}</pre>
                      )}
                  </>
              ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-center p-6 animate-fadeIn">
                      <div className="mb-4 animate-pulse">
                          <DocumentSearchIcon className="w-20 h-20" style={{ color: 'var(--color-textTertiary)' }} />
                      </div>
                      <h3 className="font-semibold mb-2" style={{ 
                        color: 'var(--color-textPrimary)',
                        fontWeight: '600'
                      }}>Hãy chọn một tài liệu</h3>
                      <p className="text-sm max-w-xs" style={{ 
                        color: 'var(--color-textSecondary)',
                        fontWeight: '400',
                        lineHeight: '1.5'
                      }}>Nội dung của tài liệu sẽ được hiển thị tại đây để bạn xem và đánh giá.</p>
                  </div>
              )}
            </div>
        </div>

        {/* Delete All Confirmation Modal */}
        <ConfirmModal
          isOpen={showDeleteAllModal}
          onClose={() => setShowDeleteAllModal(false)}
          onConfirm={() => {
            if (onDeleteAllFiles) {
              onDeleteAllFiles();
            }
          }}
          title="Xóa tất cả tài liệu?"
          message="Bạn có chắc chắn muốn xóa tất cả tài liệu? Hành động này không thể hoàn tác."
          confirmText="Xóa tất cả"
          cancelText="Hủy"
          confirmButtonStyle="danger"
        />
    </div>
  );
}, (prevProps, nextProps) => {
  // Chỉ re-render khi props thực sự thay đổi
  return (
    prevProps.uploadedFiles.length === nextProps.uploadedFiles.length &&
    prevProps.uploadedFiles.every((f, i) => 
      f.id === nextProps.uploadedFiles[i]?.id && 
      f.status === nextProps.uploadedFiles[i]?.status &&
      f.fileName === nextProps.uploadedFiles[i]?.fileName
    ) &&
    prevProps.selectedFile?.id === nextProps.selectedFile?.id &&
    prevProps.selectedFile?.status === nextProps.selectedFile?.status &&
    prevProps.sessionId === nextProps.sessionId
  );
});