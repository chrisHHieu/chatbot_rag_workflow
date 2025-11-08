import React, { useState, useEffect } from 'react';
import mammoth from 'mammoth';

interface DocxViewerProps {
  url: string;
  fileName: string;
}

export const DocxViewer: React.FC<DocxViewerProps> = ({ url, fileName }) => {
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDocx = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Failed to load document');
        }
        
        const arrayBuffer = await response.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });
        
        setHtmlContent(result.value);
        
        // Log warnings if any
        if (result.messages.length > 0) {
          console.warn('DOCX conversion warnings:', result.messages);
        }
      } catch (err) {
        console.error('Error loading DOCX:', err);
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setIsLoading(false);
      }
    };

    loadDocx();
  }, [url]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
          <p className="text-sm text-slate-600">Loading document...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-sm text-red-800 font-semibold mb-2">Failed to load document</p>
          <p className="text-xs text-red-600">{error}</p>
        </div>
        <a 
          href={url} 
          download={fileName}
          className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download {fileName}
        </a>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div 
        className="prose prose-sm max-w-none p-6 
                   prose-headings:text-slate-800 prose-headings:font-semibold
                   prose-p:text-slate-700 prose-p:leading-relaxed
                   prose-strong:text-slate-900 prose-strong:font-semibold
                   prose-ul:text-slate-700 prose-ol:text-slate-700
                   prose-li:text-slate-700
                   prose-table:text-sm prose-table:border-collapse
                   prose-th:bg-slate-100 prose-th:border prose-th:border-slate-300 prose-th:p-2
                   prose-td:border prose-td:border-slate-300 prose-td:p-2
                   prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
};

