// ✅ Smart API URL detection: relative URL for same-origin, absolute for different origins
const getApiBaseUrl = (): string => {
  // Priority 1: Explicit environment variable (kể cả empty string)
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  
  // Nếu có giá trị (kể cả empty string ''), dùng nó
  // Empty string = relative URL = tự động dùng cùng domain với frontend
  if (envUrl !== undefined) {
    return envUrl; // Empty string '' = relative URL (best for production)
  }
  
  // Priority 2: Development fallback (chỉ khi không có env variable)
  // Kiểm tra nếu đang chạy trên localhost
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    return 'http://localhost:8100';
  }
  
  // Priority 3: Production - dùng relative URL (same origin)
  // Browser sẽ tự động dùng window.location.origin
  return '';
};

const API_BASE_URL = getApiBaseUrl();

export interface UploadResponse {
  session_id: string;
  indexed: boolean;
  message?: string;
  questions?: string[];  // Sample questions generated from documents
}

export interface ChatResponse {
  answer: string;
}

export interface SessionStatus {
  exists: boolean;
  data_path: string;
  index_path: string;
  docs_count?: number;
}

export interface SessionFile {
  name: string;  // Saved name (for URL/delete operations)
  original_name?: string;  // Original name (for display in UI)
  size: number;
  path: string;
}

export async function uploadFiles(
  files: File[], 
  generateQuestions: boolean = true
): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));

  // ✅ Thêm param generate_questions vào URL
  const url = `${API_BASE_URL}/upload?generate_questions=${generateQuestions}`;
  
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

export async function ingestFiles(
  sessionId: string, 
  files: File[],
  generateQuestions: boolean = true
): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));

  // ✅ Thêm param generate_questions vào URL
  const url = `${API_BASE_URL}/ingest?session_id=${encodeURIComponent(sessionId)}&generate_questions=${generateQuestions}`;
  
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Ingest failed' }));
    throw new Error(error.detail || 'Ingest failed');
  }

  return response.json();
}

export async function chat(sessionId: string, message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Chat failed' }));
    throw new Error(error.detail || 'Chat failed');
  }

  return response.json();
}

export async function chatStream(
  sessionId: string,
  message: string,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Stream failed' }));
    throw new Error(error.detail || 'Stream failed');
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    // Decode immediately without waiting
    buffer += decoder.decode(value, { stream: true });
    
    // Process all complete events immediately (don't wait for more data)
    let eventEndIndex;
    while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
      // Extract complete event
      const eventText = buffer.slice(0, eventEndIndex);
      buffer = buffer.slice(eventEndIndex + 2); // Remove processed event + \n\n
      
      // Parse event immediately
      const lines = eventText.split('\n');
      let eventData = '';
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          eventData = line.slice(5).trim();
          break; // Found data, no need to check other lines
        }
      }
      
      // Process event immediately if we have data
      if (eventData) {
        try {
          const parsed = JSON.parse(eventData);
          
          if (parsed.type === 'status') {
            if (onStatus) {
              onStatus(parsed.content);
            }
          } else if (parsed.type === 'token') {
            // Call onChunk immediately - no delay
            // Debug: Log token content in development mode
            if (process.env.NODE_ENV === 'development' && parsed.content.length > 0) {
              const hasNewlines = parsed.content.includes('\n');
              const hasSpaces = parsed.content.includes(' ');
              if (!hasNewlines && !hasSpaces && parsed.content.length > 10) {
                console.warn('⚠️ Token without spaces/newlines:', {
                  content: JSON.stringify(parsed.content),
                  length: parsed.content.length,
                  hex: [...parsed.content].slice(0, 10).map(c => c.charCodeAt(0).toString(16))
                });
              }
            }
            onChunk(parsed.content);
          } else if (parsed.type === 'done') {
            // Stream completed
            return; // Exit immediately
          } else if (parsed.type === 'error') {
            throw new Error(parsed.content || 'Stream error');
          }
        } catch (e) {
          // If JSON parse fails, treat as plain text token
          if (eventData && !eventData.startsWith('{')) {
            onChunk(eventData);
          }
        }
      }
    }
  }
  
  // Process any remaining buffer
  if (buffer.trim()) {
    const lines = buffer.split('\n');
    for (const line of lines) {
      if (line.startsWith('data:')) {
        const eventData = line.slice(5).trim();
        if (eventData) {
          try {
            const parsed = JSON.parse(eventData);
            if (parsed.type === 'token') {
              onChunk(parsed.content);
            }
          } catch {
            onChunk(eventData);
          }
        }
      }
    }
  }
}

export async function getSessionStatus(sessionId: string): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/status`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Status check failed' }));
    throw new Error(error.detail || 'Status check failed');
  }

  return response.json();
}

export async function listSessionFiles(sessionId: string): Promise<{ files: SessionFile[] }> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/files`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'List files failed' }));
    throw new Error(error.detail || 'List files failed');
  }

  return response.json();
}

export function getFileUrl(sessionId: string, fileName: string): string {
  return `${API_BASE_URL}/data/${encodeURIComponent(sessionId)}/${encodeURIComponent(fileName)}`;
}

export interface DeleteFileResponse {
  deleted: boolean;
  deleted_chunks: number;
  file_name: string;
  session_id: string;
  session_deleted?: boolean;
}

export interface SampleQuestionsResponse {
  questions: string[];
}

export async function deleteFileFromSession(
  sessionId: string,
  fileName: string
): Promise<DeleteFileResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/files/${encodeURIComponent(fileName)}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete failed' }));
    throw new Error(error.detail || 'Delete failed');
  }

  return response.json();
}

export async function getSampleQuestions(sessionId: string): Promise<SampleQuestionsResponse> {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/sample-questions`);
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get sample questions' }));
    throw new Error(error.detail || 'Failed to get sample questions');
  }
  
  return response.json();
}

export interface DeleteSessionResponse {
  success: boolean;
  message: string;
  deleted_paths: string[];
}

export async function deleteSession(sessionId: string): Promise<DeleteSessionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete session failed' }));
    throw new Error(error.detail || 'Delete session failed');
  }

  return response.json();
}

export async function deleteAllSessionFiles(sessionId: string): Promise<DeleteSessionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/files`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete all files failed' }));
    throw new Error(error.detail || 'Delete all files failed');
  }

  return response.json();
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ConversationHistoryResponse {
  session_id: string;
  messages: ChatMessage[];
  total_messages: number;
}

export async function getConversationHistory(sessionId: string): Promise<ConversationHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/history`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get conversation history' }));
    throw new Error(error.detail || 'Failed to get conversation history');
  }

  return response.json();
}

