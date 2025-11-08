import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { flushSync } from 'react-dom';
import { Message, UploadedFile } from './types';
import * as apiService from './services/apiService';
import { Sidebar } from './components/FileViewer';
import { ChatMessage } from './components/ChatMessage';
import { MarkdownRenderer } from './components/MarkdownRenderer';
import { ChatTabs, ChatSession } from './components/ChatTabs';
import { SendIcon, OOSBrandIcon, DocumentSearchIcon, BuildingIcon } from './components/icons';

const SESSION_STORAGE_KEY = 'llmops_rag_session_id';
const SESSIONS_STORAGE_KEY = 'llmops_rag_sessions';

// ✅ File size limits (matches backend config.yaml)
const MAX_FILE_SIZE_MB = 20;
const MAX_SESSION_SIZE_MB = 100;
const MAX_FILES_PER_SESSION = 15;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const MAX_SESSION_SIZE_BYTES = MAX_SESSION_SIZE_MB * 1024 * 1024;

// ============================================
// 1. TÁCH CHATINPUT THÀNH COMPONENT RIÊNG
// ============================================
interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  sessionId: string | null;
  hasFiles: boolean;
}

const ChatInput = React.memo<ChatInputProps>(({ onSendMessage, isLoading, sessionId, hasFiles }) => {
  const [userInput, setUserInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const maxChars = 2000;

  const handleSend = useCallback(() => {
    if (userInput.trim()) {
      onSendMessage(userInput);
      setUserInput(''); // Clear sau khi gửi
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  }, [userInput, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [userInput]);

  // ✅ Disable khi không có sessionId hoặc không có files
  const isDisabled = !sessionId || !hasFiles;

  return (
    <div className="p-6 bg-gradient-to-t from-white/95 to-transparent backdrop-blur-sm">
      <div className="max-w-4xl mx-auto">
        <div className={`relative group transition-all duration-300 ${
          isFocused ? 'scale-[1.02]' : ''
        }`}>
          {/* Glow effect khi focus - Enhanced */}
          {isFocused && (
            <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 via-purple-500 to-pink-500 rounded-[2rem] opacity-25 blur-xl transition-opacity pulse-glow" />
          )}
          
          {/* Input container - Glassmorphism */}
          <div className={`relative modern-card rounded-[1.75rem] transition-all duration-300 ${
            isFocused 
              ? 'shadow-strong shadow-colored ring-2 ring-blue-500/50' 
              : 'shadow-medium hover:shadow-strong hover-lift'
          }`}>
            <textarea
              ref={textareaRef}
              value={userInput}
              onChange={(e) => {
                if (e.target.value.length <= maxChars) {
                  setUserInput(e.target.value);
                }
              }}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder={isDisabled ? "Vui lòng tải tài liệu lên để bắt đầu trò chuyện" : "Đặt câu hỏi về tài liệu của bạn..."}
              className="w-full bg-transparent border-none rounded-[1.75rem] py-4 pl-6 pr-24 resize-none focus:outline-none transition-all duration-200 text-base leading-relaxed"
              style={{
                color: 'var(--color-textPrimary)',
                fontWeight: '400',
                '--placeholder-color': 'var(--color-textTertiary)',
                minHeight: '56px',
                maxHeight: '200px',
              } as React.CSSProperties & { '--placeholder-color'?: string }}
              rows={1}
              disabled={isLoading || isDisabled}
            />
            
            {/* Character counter (hiển thị khi có text) */}
            {userInput.length > 0 && (
              <div className="absolute bottom-2 left-6 text-xs transition-opacity" style={{ 
                color: userInput.length > maxChars * 0.8 ? '#f59e0b' : 'var(--color-textTertiary)',
                fontWeight: '400'
              }}>
                {userInput.length} / {maxChars}
              </div>
            )}
            
            {/* Send button với animation đẹp */}
            <button
              onClick={handleSend}
              disabled={isLoading || !userInput.trim() || isDisabled}
              className={`absolute right-3 top-1/2 -translate-y-1/2 p-3 rounded-full transition-all duration-300 transform ${
                userInput.trim() && !isDisabled && !isLoading
                  ? 'btn-gradient-blue text-white shadow-colored hover:shadow-colored-hover hover:scale-110 active:scale-95'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
              aria-label="Send message"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <SendIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          
          {/* Hint text */}
          <div className="mt-3 px-1 flex items-center justify-between text-xs" style={{ color: 'var(--color-textTertiary)' }}>
            <span className="flex items-center gap-1" style={{ fontWeight: '400' }}>
              <kbd className="px-2 py-0.5 bg-slate-100 rounded border border-slate-300 font-mono text-[10px]" style={{ 
                color: 'var(--color-textSecondary)',
                fontWeight: '500'
              }}>Enter</kbd>
              <span>để gửi</span>
              <span className="mx-1">•</span>
              <kbd className="px-2 py-0.5 bg-slate-100 rounded border border-slate-300 font-mono text-[10px]" style={{ 
                color: 'var(--color-textSecondary)',
                fontWeight: '500'
              }}>Shift + Enter</kbd>
              <span>để xuống dòng</span>
            </span>
            {sessionId && (
              <span className="flex items-center gap-1" style={{ fontWeight: '400' }}>
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                <span>Connected</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

// ============================================
// 2. WELCOME SCREEN VỚI REACT.MEMO
// ============================================
interface WelcomeScreenProps {
  sessionId: string | null;
  onSendMessage: (message: string) => void;
  sampleQuestions: string[];
  isLoadingQuestions: boolean;
}

const WelcomeScreen = React.memo<WelcomeScreenProps>(({ 
  sessionId, 
  onSendMessage,
  sampleQuestions,
  isLoadingQuestions 
}) => (
  <div className="flex flex-col items-center justify-center h-full text-center p-8 animate-fadeIn">
    <div className="mb-6" style={{ width: '280px', height: '146px' }}>
      <OOSBrandIcon style={{ width: '100%', height: '100%' }} />
    </div>
    <h1 className="text-4xl font-bold mb-2" style={{ 
      color: 'var(--color-text)',
      fontWeight: '700',
      letterSpacing: '-0.02em',
      lineHeight: '1.2'
    }}>Humax Assistant</h1>
    <p className="mt-2 max-w-md text-lg mb-6" style={{ 
      color: 'var(--color-textSecondary)',
      fontWeight: '400',
      lineHeight: '1.6',
      letterSpacing: '-0.01em'
    }}>Biến kho tài liệu doanh nghiệp thành nguồn tri thức sống, sẵn sàng cung cấp câu trả lời tức thì cho mọi nhu cầu thông tin</p>
    {sessionId && (
      <>
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg mb-6" style={{ 
          backgroundColor: 'var(--color-surfaceHover)', 
          border: '1px solid var(--color-border)'
        }}>
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          <span className="text-sm" style={{ 
            color: 'var(--color-textSecondary)',
            fontWeight: '500'
          }}>Session Active</span>
        </div>
        
        {/* Sample Questions Component */}
        {isLoadingQuestions ? (
          <div className="mt-4 w-full max-w-3xl">
            <div className="flex items-center justify-center gap-2">
              <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-sm" style={{ color: 'var(--color-textSecondary)' }}>
                Đang tạo câu hỏi mẫu...
              </span>
            </div>
          </div>
        ) : sampleQuestions.length > 0 ? (
          <div className="mt-6 w-full max-w-4xl animate-fadeIn">
            <h3 className="text-base font-semibold mb-4 text-center" style={{ 
              color: 'var(--color-text)',
              fontWeight: '600',
              letterSpacing: '-0.01em'
            }}>
              💡 Các câu hỏi gợi ý từ tài liệu
            </h3>
            
            {/* Horizontal scrollable questions - Better visibility */}
            <div className="overflow-x-auto pb-2 scrollbar-visible" style={{
              scrollbarWidth: 'thin',
              scrollbarColor: '#cbd5e1 #f1f5f9'
            }}>
              <div className="flex gap-3" style={{ minWidth: 'max-content', paddingBottom: '4px' }}>
                {sampleQuestions.slice(0, 6).map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => onSendMessage(question)}
                    className="flex-shrink-0 px-5 py-3 rounded-xl text-sm transition-all duration-200 glass-card hover:shadow-medium hover-lift group"
                    style={{
                      color: 'var(--color-textPrimary)',
                      minWidth: '280px',
                      maxWidth: '320px',
                      whiteSpace: 'normal',
                      textAlign: 'left',
                      lineHeight: '1.5'
                    }}
                  >
                    <span className="group-hover:text-blue-600 transition-colors block">
                      {question}
                    </span>
                  </button>
                ))}
              </div>
            </div>
            
            {/* Show count if more than displayed */}
            {sampleQuestions.length > 6 && (
              <p className="text-xs text-center mt-3" style={{ 
                color: 'var(--color-textTertiary)',
                fontStyle: 'italic'
              }}>
                Hiển thị 6/{sampleQuestions.length} câu hỏi gợi ý
              </p>
            )}
          </div>
        ) : null}
      </>
    )}
  </div>
));

// ============================================
// 3. CHAT HEADER - REMOVED (Replaced by ChatTabs)
// ============================================

// ============================================
// 4. STREAMING MESSAGE COMPONENT
// ============================================
interface StreamingMessageProps {
  streamingContent: string;
  statusMessage: string;
}

const StreamingMessage = React.memo<StreamingMessageProps>(({ streamingContent, statusMessage }) => (
  <div className="flex items-start gap-4">
    <div className="flex-shrink-0 rounded-full flex items-center justify-center shadow-lg overflow-hidden" style={{ width: '48px', height: '48px', background: 'var(--color-surface)', border: '2px solid var(--color-border)', padding: '0' }}>
      <OOSBrandIcon style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
    <div className="bg-slate-100 rounded-lg p-4 max-w-3xl shadow-sm">
      {statusMessage && !streamingContent && (
        <p className="text-sm text-slate-600 mb-2">{statusMessage}</p>
      )}
      {streamingContent && (
        <div className="text-slate-800">
          <MarkdownRenderer text={streamingContent} isStreaming={true} />
                                  <span className="inline-block w-1 h-4 ml-0.5 animate-pulse" style={{ backgroundColor: 'var(--color-primary)' }}></span>
        </div>
      )}
    </div>
  </div>
));

// ============================================
// MAIN APP COMPONENT
// ============================================
const App: React.FC = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<UploadedFile | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem(SESSION_STORAGE_KEY);
  });
  
  // ✅ Chat Sessions Management
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const stored = localStorage.getItem(SESSIONS_STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return [];
      }
    }
    // Nếu có sessionId cũ, tạo session từ đó
    const oldSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (oldSessionId) {
      return [{
        id: oldSessionId,
        title: 'Chat ' + oldSessionId.substring(0, 8),
        createdAt: Date.now(),
      }];
    }
    return [];
  });
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isChatStarted, setIsChatStarted] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [sampleQuestions, setSampleQuestions] = useState<string[]>([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [isScrolling, setIsScrolling] = useState(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isLoading, streamingContent]);

  // Handle scroll detection for auto-hide scrollbar
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      setIsScrolling(true);
      container.classList.add('scrolling');
      
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
      
      scrollTimeoutRef.current = setTimeout(() => {
        setIsScrolling(false);
        container.classList.remove('scrolling');
      }, 1000);
    };

    container.addEventListener('scroll', handleScroll);
    return () => {
      container.removeEventListener('scroll', handleScroll);
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  // ✅ Save sessions to localStorage whenever sessions change
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
    } else {
      localStorage.removeItem(SESSIONS_STORAGE_KEY);
    }
  }, [sessions]);

  // ✅ Load session files function
  const loadSessionFiles = useCallback(async (targetSessionId?: string) => {
    const targetId = targetSessionId || sessionId;
    if (!targetId) return;
    try {
      const status = await apiService.getSessionStatus(targetId);
      if (status.exists) {
        const serverFiles = await apiService.listSessionFiles(targetId);
        
        // ✅ Nếu không có files, clear UI (chat input sẽ disable)
        if (serverFiles.files.length === 0) {
          setUploadedFiles([]);
          setSelectedFile(null);
          return;
        }
        
        const loadedFiles: UploadedFile[] = serverFiles.files.map((sf, idx) => {
          const ext = sf.name.split('.').pop()?.toLowerCase() || '';
          const mimeType = ext === 'pdf' ? 'application/pdf' : 
                          ext === 'docx' ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' :
                          'text/plain';
          const displayName = sf.original_name || sf.name;
          return {
            id: `${sf.name}-${idx}`,
            file: new File([], displayName, { type: mimeType }),
            fileName: displayName,
            savedFileName: sf.name,
            content: mimeType === 'application/pdf' ? '[PDF Document]' : '[Document Content]',
            url: apiService.getFileUrl(targetId, sf.name),
            status: 'ready' as const,
            sessionId: targetId,
            fileSize: sf.size || 0, // ✅ Persist file size from server
          };
        });
        setUploadedFiles(loadedFiles);
        if (loadedFiles.length > 0) {
          setSelectedFile(loadedFiles[0]);
        }
      } else {
        // Session không tồn tại hoặc không có files
        setUploadedFiles([]);
        setSelectedFile(null);
      }
    } catch (e) {
      console.error('Failed to load session files:', e);
      // Nếu lỗi, clear files để disable chat input
      setUploadedFiles([]);
      setSelectedFile(null);
    }
  }, [sessionId]);

  // ✅ Load conversation history from checkpointer
  const loadConversationHistory = useCallback(async (targetSessionId: string): Promise<boolean> => {
    try {
      const history = await apiService.getConversationHistory(targetSessionId);
      if (history.messages && history.messages.length > 0) {
        // Convert API messages to UI Message format
        const uiMessages: Message[] = history.messages.map(msg => ({
          role: msg.role === 'user' ? 'user' : 'model',
          content: msg.content
        }));
        setMessages(uiMessages);
        setIsChatStarted(true); // Mark as started since we have history
        console.log(`Loaded conversation history for session ${targetSessionId}:`, uiMessages.length, 'messages');
        return true; // ✅ Chat has started
      } else {
        // No history, start fresh
        setMessages([]);
        setIsChatStarted(false);
        return false; // ✅ No chat history
      }
    } catch (error) {
      // If history loading fails, start fresh (non-critical)
      console.warn('Failed to load conversation history:', error);
      setMessages([]);
      setIsChatStarted(false);
      return false; // ✅ No chat history on error
    }
  }, []);

  // ✅ Add function to load sample questions
  const loadSampleQuestions = useCallback(async (targetSessionId: string) => {
    try {
      setIsLoadingQuestions(true);
      const response = await apiService.getSampleQuestions(targetSessionId);
      if (response.questions && response.questions.length > 0) {
        setSampleQuestions(response.questions);
      } else {
        setSampleQuestions([]);
      }
    } catch (error) {
      // Non-critical error - just log and continue
      console.warn('Failed to load sample questions:', error);
      setSampleQuestions([]);
    } finally {
      setIsLoadingQuestions(false);
    }
  }, []);

  useEffect(() => {
    if (sessionId) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
      loadSessionFiles(sessionId);
      
      // ✅ Load conversation history first, then load sample questions if no chat
      loadConversationHistory(sessionId).then((hasChatHistory) => {
        // ✅ Only load sample questions if no chat history
        if (!hasChatHistory) {
          // Check if files exist before loading questions
          apiService.getSessionStatus(sessionId).then((status) => {
            if (status.exists) {
              loadSampleQuestions(sessionId);
            }
          }).catch(() => {
            // Ignore error
          });
        } else {
          // Clear sample questions if chat has started
          setSampleQuestions([]);
        }
      });
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, [sessionId, loadSessionFiles, loadConversationHistory, loadSampleQuestions]);

  // ✅ Handle New Chat
  const handleNewChat = useCallback(() => {
    // Clear current session
    setSessionId(null);
    setMessages([]);
    setUploadedFiles([]);
    setSelectedFile(null);
    setIsChatStarted(false);
    setSampleQuestions([]);
    setError(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }, []);

  // ✅ Handle Session Select
  const handleSessionSelect = useCallback(async (sessionIdToSelect: string | null) => {
    if (sessionIdToSelect === null) {
      handleNewChat();
      return;
    }
    
    // Load session
    setSessionId(sessionIdToSelect);
    localStorage.setItem(SESSION_STORAGE_KEY, sessionIdToSelect);
    
    // Load files for this session
    await loadSessionFiles(sessionIdToSelect);
    
    // ✅ Load conversation history from checkpointer
    const hasChatHistory = await loadConversationHistory(sessionIdToSelect);
    
    // ✅ Load sample questions if no chat history
    if (!hasChatHistory) {
      try {
        const status = await apiService.getSessionStatus(sessionIdToSelect);
        if (status.exists) {
          await loadSampleQuestions(sessionIdToSelect);
        } else {
          setSampleQuestions([]);
        }
      } catch (error) {
        console.warn('Failed to check session status for sample questions:', error);
        setSampleQuestions([]);
      }
    } else {
      // Clear sample questions if chat has started
      setSampleQuestions([]);
    }
    
    setError(null);
  }, [handleNewChat, loadSessionFiles, loadConversationHistory, loadSampleQuestions]);

  // ✅ Handle Close Session
  const handleCloseSession = useCallback(async (sessionIdToClose: string) => {
    try {
      // ✅ Call backend API to delete session data (data folder + faiss_index folder)
      await apiService.deleteSession(sessionIdToClose);
      
      // Remove from UI
      const updatedSessions = sessions.filter(s => s.id !== sessionIdToClose);
      setSessions(updatedSessions);
      
      // ✅ Nếu xóa hết session, về welcome screen và clear tất cả
      if (updatedSessions.length === 0) {
        setSessionId(null);
        setMessages([]);
        setUploadedFiles([]);
        setSelectedFile(null);
        setIsChatStarted(false);
        setSampleQuestions([]);
        setError(null);
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }
      
      // If closing active session, switch to another session
      if (sessionIdToClose === sessionId) {
        if (updatedSessions.length > 0) {
          // Switch to first remaining session
          handleSessionSelect(updatedSessions[0].id);
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete session';
      setError(`Failed to delete session: ${errorMessage}`);
      console.error('Error deleting session:', error);
      
      // Still remove from UI even if backend deletion fails
      const updatedSessions = sessions.filter(s => s.id !== sessionIdToClose);
      setSessions(updatedSessions);
      
      // ✅ Nếu xóa hết session, về welcome screen
      if (updatedSessions.length === 0) {
        setSessionId(null);
        setMessages([]);
        setUploadedFiles([]);
        setSelectedFile(null);
    setIsChatStarted(false);
        setSampleQuestions([]);
        setError(null);
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }
      
      // If closing active session, switch to another session
      if (sessionIdToClose === sessionId) {
        if (updatedSessions.length > 0) {
          handleSessionSelect(updatedSessions[0].id);
        }
      }
    }
  }, [sessionId, sessions, handleSessionSelect]);

  // ============================================
  // OPTIMIZED CALLBACKS WITH USECALLBACK
  // ============================================
  const handleRemoveFile = useCallback(async (fileId: string) => {
    const fileToRemove = uploadedFiles.find(f => f.id === fileId);
    if (!fileToRemove) return;

    if (!sessionId) {
    setUploadedFiles(prevFiles => {
      const updatedFiles = prevFiles.filter(f => f.id !== fileId);
      if (selectedFile?.id === fileId) {
        setSelectedFile(updatedFiles.length > 0 ? updatedFiles[0] : null);
      }
      return updatedFiles;
    });
      return;
    }

    const isSelectedFile = selectedFile?.id === fileId;
    const remainingFiles = uploadedFiles.filter(f => f.id !== fileId);
    
    setUploadedFiles(prevFiles =>
      prevFiles.map(f => f.id === fileId ? { ...f, status: 'deleting' as const } : f)
    );
    
    if (isSelectedFile) {
      setSelectedFile(remainingFiles.length > 0 ? remainingFiles[0] : null);
    }

    setError(null);
    try {
      const fileNameToDelete = fileToRemove.savedFileName || fileToRemove.fileName;
      const result = await apiService.deleteFileFromSession(sessionId, fileNameToDelete);
    
      setUploadedFiles(prevFiles => {
        const updatedFiles = prevFiles.filter(f => f.id !== fileId);
        if (isSelectedFile && updatedFiles.length === 0) {
          setSelectedFile(null);
        } else if (isSelectedFile && updatedFiles.length > 0 && !updatedFiles.some(f => f.id === selectedFile?.id)) {
          setSelectedFile(updatedFiles[0]);
        }
        return updatedFiles;
      });

      if (result.session_deleted) {
        setSessionId(null);
        setMessages([]);
        setIsChatStarted(false);
        console.log(`Session deleted: All files removed from session ${sessionId}`);
      }

      if (result.deleted) {
        console.log(`File deleted: ${result.file_name} (${result.deleted_chunks} chunks removed)`);
      }
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Delete failed';
      setError(`Failed to delete file: ${errorMessage}`);
      setUploadedFiles(prevFiles =>
        prevFiles.map(f => f.id === fileId ? { ...f, status: 'ready' as const } : f)
      );
      if (isSelectedFile && fileToRemove) {
        setSelectedFile({ ...fileToRemove, status: 'ready' as const });
      }
    }
  }, [uploadedFiles, selectedFile, sessionId]);

  // ✅ Handle Delete All Files
  const handleDeleteAllFiles = useCallback(async () => {
    if (!sessionId) {
      setError('No session active');
      return;
    }

    try {
      // Call API to delete all files
      await apiService.deleteAllSessionFiles(sessionId);
      
      // ✅ Clear files from UI - chat input sẽ tự động disable
      setUploadedFiles([]);
      setSelectedFile(null);
      
      console.log(`All files deleted from session ${sessionId} (session preserved)`);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Delete all files failed';
      setError(`Failed to delete all files: ${errorMessage}`);
      console.error('Error deleting all files:', e);
    }
  }, [sessionId]);

  const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setError(null);

    // ✅ Validate file sizes BEFORE processing
    const fileArray = Array.from(files);
    
    // Check individual file sizes
    for (const file of fileArray) {
      if (file.size > MAX_FILE_SIZE_BYTES) {
        const fileSizeMB = file.size / (1024 * 1024);
        setError(
          `File '${file.name}' quá lớn (${fileSizeMB.toFixed(2)} MB). ` +
          `Kích thước tối đa cho phép: ${MAX_FILE_SIZE_MB} MB. ` +
          `Vui lòng chia nhỏ file hoặc nén file.`
        );
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }
    }
    
    // Check total number of files (for new session)
    if (!sessionId && fileArray.length > MAX_FILES_PER_SESSION) {
      setError(
        `Số lượng file vượt quá giới hạn. ` +
        `Tối đa ${MAX_FILES_PER_SESSION} files mỗi session. ` +
        `Bạn đã chọn ${fileArray.length} files.`
      );
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    
    // Check total session size (if session exists)
    if (sessionId) {
      try {
        // Calculate existing files size
        const existingSize = uploadedFiles.reduce((sum, f) => sum + (f.fileSize || f.file.size || 0), 0);
        const newFilesSize = fileArray.reduce((sum, f) => sum + f.size, 0);
        const totalSize = existingSize + newFilesSize;
        const totalFiles = uploadedFiles.length + fileArray.length;
        
        if (totalSize > MAX_SESSION_SIZE_BYTES) {
          const totalSizeMB = totalSize / (1024 * 1024);
          setError(
            `Tổng kích thước session vượt quá giới hạn (${totalSizeMB.toFixed(2)} MB / ${MAX_SESSION_SIZE_MB} MB). ` +
            `Vui lòng xóa một số file cũ hoặc tạo session mới.`
          );
          if (fileInputRef.current) fileInputRef.current.value = '';
          return;
        }
        
        if (totalFiles > MAX_FILES_PER_SESSION) {
          setError(
            `Số lượng file trong session vượt quá giới hạn (${totalFiles} / ${MAX_FILES_PER_SESSION}). ` +
            `Vui lòng xóa một số file cũ hoặc tạo session mới.`
          );
          if (fileInputRef.current) fileInputRef.current.value = '';
          return;
        }
      } catch (error) {
        console.warn('Failed to validate session size limits:', error);
        // Continue with upload if validation fails (backend will also check)
      }
    }

    const newFiles: UploadedFile[] = fileArray
      .filter(file => !uploadedFiles.some(f => f.file.name === file.name && (f.fileSize || f.file.size) === file.size))
      .map((file, idx) => ({
        id: `${file.name}-${Date.now()}-${idx}`,
        file: file,
        fileName: file.name,
        content: '',
        url: null,
        status: 'uploading' as const,
        fileSize: file.size, // ✅ Save file size from original file
      }));

    if (newFiles.length === 0) {
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setUploadedFiles(prev => [...prev, ...newFiles]);

    try {
      let currentSessionId = sessionId;
      let questions: string[] | undefined = undefined;
      
      // ✅ Xác định có nên generate questions không (chỉ khi chưa chat)
      const shouldGenerateQuestions = !isChatStarted;
      
      // ✅ Set loading state ngay khi bắt đầu upload (nếu chưa chat)
      if (shouldGenerateQuestions && !sessionId) {
        setIsLoadingQuestions(true);
      }
      
      if (currentSessionId) {
        // ✅ Ingest files vào session cũ - gửi param generate_questions
        const ingestResult = await apiService.ingestFiles(
          currentSessionId, 
          Array.from(files),
          shouldGenerateQuestions  // ✅ Chỉ generate khi chưa chat
        );
        questions = ingestResult.questions;  // ✅ Nhận questions từ response (nếu có)
        
        // ✅ Update session title if needed
        setSessions(prev => {
          const existing = prev.find(s => s.id === currentSessionId);
          if (existing && uploadedFiles.length === 0) {
            // First file in session, update title
            return prev.map(s => 
              s.id === currentSessionId 
                ? { 
                    ...s, 
                    title: files[0]?.name || s.title,
                    createdAt: Date.now()
                  }
                : s
            );
          }
          return prev;
        });
        
        const serverFiles = await apiService.listSessionFiles(currentSessionId);
        
        const updatedFiles = newFiles.map((nf, idx) => {
          const matchedFile = serverFiles.files.find(
            sf => Math.abs(sf.size - (nf.fileSize || nf.file.size)) < 1000
          ) || serverFiles.files[serverFiles.files.length - newFiles.length + idx];
          
          const serverFileName = matchedFile?.name || files[idx].name;
          const originalFileName = matchedFile?.original_name || files[idx].name;
          const fileUrl = apiService.getFileUrl(currentSessionId, serverFileName);
          return {
            ...nf,
            fileName: originalFileName,
            savedFileName: serverFileName,
            url: fileUrl,
            status: 'ready' as const,
            sessionId: currentSessionId,
            content: nf.file.type === 'application/pdf' ? '[PDF Document]' : '[Document Content]',
            fileSize: matchedFile?.size || nf.fileSize || nf.file.size, // ✅ Persist file size from server
          };
        });

        setUploadedFiles(prev => {
          const filtered = prev.filter(f => !newFiles.some(nf => nf.id === f.id));
          return [...filtered, ...updatedFiles];
        });

        if (updatedFiles.length > 0) {
          setSelectedFile(updatedFiles[0]);
        }
      } else {
        // ✅ Upload files mới - tạo session mới - gửi param generate_questions
        const uploadResult = await apiService.uploadFiles(
          Array.from(files),
          shouldGenerateQuestions  // ✅ Chỉ generate khi chưa chat
        );
        currentSessionId = uploadResult.session_id;
        questions = uploadResult.questions;  // ✅ Nhận questions từ response (nếu có)
        setSessionId(currentSessionId);
      
        // ✅ Add/Update session in sessions list
        setSessions(prev => {
          // Check if session already exists
          const existing = prev.find(s => s.id === currentSessionId);
          if (existing) {
            // Update existing session
            return prev.map(s => 
              s.id === currentSessionId 
                ? { 
                    ...s, 
                    title: files[0]?.name || `Chat ${currentSessionId.substring(0, 8)}`,
                    createdAt: Date.now()
                  }
                : s
            );
          } else {
            // Add new session
            const newSession: ChatSession = {
              id: currentSessionId,
              title: files[0]?.name || `Chat ${currentSessionId.substring(0, 8)}`,
              createdAt: Date.now(),
            };
            return [...prev, newSession];
          }
        });

        const serverFiles = await apiService.listSessionFiles(currentSessionId);
        
      const updatedFiles = newFiles.map((nf, idx) => {
        const matchedFile = serverFiles.files.find(
          sf => Math.abs(sf.size - (nf.fileSize || nf.file.size)) < 1000
        ) || serverFiles.files[idx];
        
        const serverFileName = matchedFile?.name || files[idx].name;
          const originalFileName = matchedFile?.original_name || files[idx].name;
          const fileUrl = apiService.getFileUrl(currentSessionId, serverFileName);
        return {
          ...nf,
            fileName: originalFileName,
            savedFileName: serverFileName,
          url: fileUrl,
          status: 'ready' as const,
            sessionId: currentSessionId,
          content: nf.file.type === 'application/pdf' ? '[PDF Document]' : '[Document Content]',
          fileSize: matchedFile?.size || nf.fileSize || nf.file.size, // ✅ Persist file size from server
        };
      });

      setUploadedFiles(prev => {
        const filtered = prev.filter(f => !newFiles.some(nf => nf.id === f.id));
        return [...filtered, ...updatedFiles];
      });

      if (updatedFiles.length > 0) {
        setSelectedFile(updatedFiles[0]);
        }
      }
      
      // ✅ Set questions từ response (CHỈ KHI chưa chat)
      // Backend đã tự động generate questions, không cần gọi API riêng nữa
      if (currentSessionId && !isChatStarted) {
        if (questions && questions.length > 0) {
          setSampleQuestions(questions);
        } else {
          setSampleQuestions([]);
        }
        setIsLoadingQuestions(false);
      } else {
        // Nếu đã chat rồi, clear loading state
        setIsLoadingQuestions(false);
      }
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Upload failed';
      setError(`Upload failed: ${errorMessage}`);
      setUploadedFiles(prev => prev.map(f => 
        newFiles.some(nf => nf.id === f.id) ? { ...f, status: 'error' as const } : f
      ));
      // Clear loading state on error
      setIsLoadingQuestions(false);
    }
    
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [uploadedFiles, sessionId, isChatStarted]);
  
  const handleFileSelect = useCallback((file: UploadedFile) => {
    if (selectedFile?.id !== file.id && file.status === 'ready') {
      setSelectedFile(file);
    }
  }, [selectedFile]);

  const handleSendMessage = useCallback(async (prompt: string, useStreaming: boolean = true) => {
    if (!prompt?.trim() || isLoading) return;
    if (!sessionId) {
      setError('Please upload documents first to create a session.');
      return;
    }

    if (!isChatStarted) setIsChatStarted(true);

    const newMessages: Message[] = [...messages, { role: 'user', content: prompt }];
    setMessages(newMessages);
    setIsLoading(true);
    setError(null);
    setStreamingContent('');

    try {
      if (useStreaming) {
        let fullAnswer = '';
        await apiService.chatStream(
          sessionId, 
          prompt, 
          (chunk) => {
          fullAnswer += chunk;
            
            if (fullAnswer === chunk) {
              flushSync(() => {
                setStatusMessage('');
          setStreamingContent(fullAnswer);
        });
            } else {
              setStreamingContent(fullAnswer);
            }
          },
          (status) => {
            setStatusMessage(status);
          }
        );
        setMessages([...newMessages, { role: 'model', content: fullAnswer }]);
        setStreamingContent('');
        setStatusMessage('');
      } else {
        const response = await apiService.chat(sessionId, prompt);
        setMessages([...newMessages, { role: 'model', content: response.answer }]);
      }
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'An unknown error occurred.';
      setError(`Failed to get response: ${errorMessage}`);
      setMessages([...newMessages, { role: 'model', content: "Sorry, I couldn't process that. Please try again." }]);
    } finally {
      setIsLoading(false);
      setStreamingContent('');
      setStatusMessage('');
    }
  }, [isLoading, sessionId, messages, isChatStarted]);
  
  const triggerFileInput = useCallback(() => fileInputRef.current?.click(), []);

  // ============================================
  // RENDER
  // ============================================
  return (
    <div className="h-screen flex">
      <div className="w-full h-full modern-card flex overflow-hidden" style={{ backgroundColor: 'rgba(255, 255, 255, 0.95)' }}>
            <Sidebar 
                uploadedFiles={uploadedFiles}
                selectedFile={selectedFile}
                onFileSelect={handleFileSelect}
                onUploadClick={triggerFileInput}
                onRemoveFile={handleRemoveFile}
                onDeleteAllFiles={handleDeleteAllFiles}
          onFilesDropped={async (files) => {
            // Convert FileList to array and trigger upload
            const fileArray = Array.from(files);
            if (fileArray.length === 0) return;
            
            // ✅ Validate file sizes for drag & drop (same as file input)
            setError(null);
            
            // Check individual file sizes
            for (const file of fileArray) {
              if (file.size > MAX_FILE_SIZE_BYTES) {
                const fileSizeMB = file.size / (1024 * 1024);
                setError(
                  `File '${file.name}' quá lớn (${fileSizeMB.toFixed(2)} MB). ` +
                  `Kích thước tối đa cho phép: ${MAX_FILE_SIZE_MB} MB. ` +
                  `Vui lòng chia nhỏ file hoặc nén file.`
                );
                return;
              }
            }
            
            // Check total number of files (for new session)
            if (!sessionId && fileArray.length > MAX_FILES_PER_SESSION) {
              setError(
                `Số lượng file vượt quá giới hạn. ` +
                `Tối đa ${MAX_FILES_PER_SESSION} files mỗi session. ` +
                `Bạn đã chọn ${fileArray.length} files.`
              );
              return;
            }
            
            // Check total session size (if session exists)
            if (sessionId) {
              try {
                const existingSize = uploadedFiles.reduce((sum, f) => sum + (f.fileSize || f.file.size || 0), 0);
                const newFilesSize = fileArray.reduce((sum, f) => sum + f.size, 0);
                const totalSize = existingSize + newFilesSize;
                const totalFiles = uploadedFiles.length + fileArray.length;
                
                if (totalSize > MAX_SESSION_SIZE_BYTES) {
                  const totalSizeMB = totalSize / (1024 * 1024);
                  setError(
                    `Tổng kích thước session vượt quá giới hạn (${totalSizeMB.toFixed(2)} MB / ${MAX_SESSION_SIZE_MB} MB). ` +
                    `Vui lòng xóa một số file cũ hoặc tạo session mới.`
                  );
                  return;
                }
                
                if (totalFiles > MAX_FILES_PER_SESSION) {
                  setError(
                    `Số lượng file trong session vượt quá giới hạn (${totalFiles} / ${MAX_FILES_PER_SESSION}). ` +
                    `Vui lòng xóa một số file cũ hoặc tạo session mới.`
                  );
                  return;
                }
              } catch (error) {
                console.warn('Failed to validate session size limits for drag & drop:', error);
              }
            }
            
            // Create a synthetic event to reuse handleFileChange logic
            const syntheticEvent = {
              target: { files: files }
            } as React.ChangeEvent<HTMLInputElement>;
            
            await handleFileChange(syntheticEvent);
          }}
                sessionId={sessionId}
            />
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="hidden"
                accept=".txt,.md,.json,.csv,.pdf,.docx"
                multiple
            />
            <div className="flex-1 flex flex-col bg-transparent overflow-hidden">
          {/* ✅ ChatTabs Component */}
          <ChatTabs
            sessions={sessions}
            activeSessionId={sessionId}
            onSessionSelect={handleSessionSelect}
            onNewChat={handleNewChat}
            onCloseSession={handleCloseSession}
          />
          <div ref={chatContainerRef} className="flex-grow p-6 space-y-6 overflow-y-auto scrollbar-auto-hide">
            {!isChatStarted ? (
              <WelcomeScreen 
                sessionId={sessionId} 
                onSendMessage={handleSendMessage}
                sampleQuestions={sampleQuestions}
                isLoadingQuestions={isLoadingQuestions}
              />
            ) : (
                      <>
                        {messages.map((msg, index) => (
                          <ChatMessage key={index} message={msg} />
                        ))}
                {(streamingContent || (isLoading && statusMessage)) && (
                  <StreamingMessage 
                    streamingContent={streamingContent}
                    statusMessage={statusMessage}
                  />
                        )}
                      </>
                    )}
            {isLoading && !streamingContent && !statusMessage && (
                        <div className="flex items-start gap-4 animate-slide-in-bottom">
                <div className="flex-shrink-0 rounded-full flex items-center justify-center shadow-lg overflow-hidden" style={{ width: '48px', height: '48px', background: 'var(--color-surface)', border: '2px solid var(--color-border)', padding: '0' }}>
                  <OOSBrandIcon style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            </div>
                            <div className="bg-slate-100 rounded-lg p-4 max-w-xl">
                                <div className="flex items-center justify-center gap-1.5">
                                    <span className="h-2 w-2 rounded-full animate-bounce [animation-delay:-0.3s]" style={{ backgroundColor: 'var(--color-primary)' }}></span>
                                    <span className="h-2 w-2 rounded-full animate-bounce [animation-delay:-0.15s]" style={{ backgroundColor: 'var(--color-primary)' }}></span>
                                    <span className="h-2 w-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--color-primary)' }}></span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
                {error && (
                    <div className="p-3 bg-red-100 text-red-800 border-t border-red-200 text-sm font-medium animate-fadeIn">
                        <strong>Error:</strong> {error}
                    </div>
                )}
          <ChatInput 
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            sessionId={sessionId}
            hasFiles={uploadedFiles.length > 0}
          />
            </div>
      </div>
    </div>
  );
};

export default App;