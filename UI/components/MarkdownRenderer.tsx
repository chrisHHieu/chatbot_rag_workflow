import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'highlight.js/styles/github-dark.css';
import 'katex/dist/katex.min.css';

interface MarkdownRendererProps {
  text: string;
  isStreaming?: boolean;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ text, isStreaming = false }) => {
  // Render markdown immediately - no throttling for real-time streaming
  // react-markdown is optimized to handle frequent updates efficiently
  
  // Debug: Log if text contains concatenated Vietnamese (no spaces between words)
  // This helps identify if the issue is in the text prop itself
  if (process.env.NODE_ENV === 'development' && text.length > 20) {
    const vietnameseWords = text.match(/[\u0100-\u1EF9]+/g);
    if (vietnameseWords && vietnameseWords.some(word => word.length > 15)) {
      console.warn('⚠️ Potential concatenated Vietnamese text detected:', {
        length: text.length,
        sample: text.substring(0, 100),
        longWords: vietnameseWords.filter(w => w.length > 15).slice(0, 3)
      });
    }
  }
  
  return (
    <div className="prose prose-sm max-w-none text-slate-800 leading-relaxed break-words" style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeHighlight, rehypeKatex]}
        components={{
        // Custom styling for elements
        h1: (props) => (
          <h1 className="text-2xl font-bold mt-4 mb-2 text-slate-900 break-words" {...props} />
        ),
        h2: (props) => (
          <h2 className="text-xl font-bold mt-4 mb-2 text-slate-900 break-words" {...props} />
        ),
        h3: (props) => (
          <h3 className="text-lg font-bold mt-3 mb-2 text-slate-900 break-words" {...props} />
        ),
        p: (props) => (
          <p className="my-2 leading-relaxed text-slate-800 break-words" {...props} />
        ),
        strong: (props) => (
          <strong className="font-semibold text-slate-900" {...props} />
        ),
        em: (props) => (
          <em className="italic" {...props} />
        ),
        ul: (props) => (
          <ul className="list-disc list-outside my-2 space-y-1 text-slate-800 break-words ml-6" {...props} />
        ),
        ol: (props) => (
          <ol className="list-decimal list-outside my-2 space-y-1 text-slate-800 break-words ml-6" {...props} />
        ),
        li: (props) => (
          <li className="ml-0 pl-2 break-words" {...props} />
        ),
        code: (props: any) => {
          const { inline, className, children, ...rest } = props;
          return inline ? (
            <code className="bg-slate-200 text-slate-800 px-1.5 py-0.5 rounded text-sm" style={{ fontFamily: '"IBM Plex Mono", monospace' }} {...rest}>
              {children}
            </code>
          ) : (
            <code className="block bg-slate-800 text-slate-100 p-3 rounded-lg my-2 overflow-x-auto text-sm" style={{ fontFamily: '"IBM Plex Mono", monospace' }} {...rest}>
              {children}
            </code>
          );
        },
        pre: (props) => (
          <pre className="bg-slate-800 text-slate-100 p-3 rounded-lg my-2 overflow-x-auto" {...props} />
        ),
        a: (props) => (
          <a className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
        ),
        blockquote: (props) => (
          <blockquote className="border-l-4 border-slate-300 pl-4 my-2 italic text-slate-700" {...props} />
        ),
        table: (props) => (
          <table className="min-w-full divide-y divide-slate-300 my-2" {...props} />
        ),
        th: (props) => (
          <th className="bg-slate-100 border border-slate-300 px-3 py-2 text-left font-semibold" {...props} />
        ),
        td: (props) => (
          <td className="border border-slate-300 px-3 py-2 break-words" {...props} />
        ),
      }}
      >
        {text}
      </ReactMarkdown>
      <style>{`
        /* KaTeX Math Styling - Inline math */
        .katex {
          font-size: 1.05em;
          color: var(--color-textPrimary);
        }
        
        /* KaTeX Math Block - Display math */
        .katex-display {
          margin: 1.5em 0;
          padding: 1em;
          background-color: rgba(248, 250, 252, 0.8);
          border-radius: 8px;
          border-left: 3px solid var(--color-primary);
          overflow-x: auto;
          overflow-y: hidden;
        }
        
        .katex-display > .katex {
          text-align: left;
          max-width: 100%;
        }
        
        /* Ensure math doesn't break layout */
        .katex,
        .katex-display {
          word-break: normal;
          overflow-wrap: normal;
        }
        
        /* Math in paragraphs */
        p .katex {
          margin: 0 2px;
        }
        
        /* Dark mode support (if needed in future) */
        @media (prefers-color-scheme: dark) {
          .katex {
            color: #e2e8f0;
          }
          .katex-display {
            background-color: rgba(30, 41, 59, 0.5);
          }
        }
      `}</style>
    </div>
  );
};
