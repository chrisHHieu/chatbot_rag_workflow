export interface Message {
  role: 'user' | 'model';
  content: string;
}

export interface UploadedFile {
  id: string;
  file: File;
  fileName: string; // Display name (original filename)
  savedFileName?: string; // Saved name (sanitized, for URL/delete operations)
  content: string;
  url: string | null;
  status: 'uploading' | 'ready' | 'error' | 'deleting';
  sessionId?: string; // Session ID from backend
  fileSize?: number; // File size in bytes (persisted from server)
}