# llmops_rag UI

React + TypeScript UI for the llmops_rag enterprise RAG system with LangGraph.

## Features

- 📤 **Multi-file upload** with session management
- 💬 **Streaming chat** with real-time token-by-token updates
- 📄 **Document preview** (PDF, DOCX, TXT) from server
- 🔄 **Session persistence** (localStorage)
- 🎨 **Modern UI** with Tailwind CSS

## Prerequisites

- Node.js 18+
- FastAPI backend running (see parent README.md)

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create `.env.local` (optional, defaults to `http://localhost:8000`):
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open http://localhost:3000

## Build for Production

```bash
npm run build
```

The built files will be in `dist/` directory.

## API Integration

The UI connects to the FastAPI backend at `VITE_API_BASE_URL`:

- `POST /upload` - Upload files and create session
- `POST /ingest` - Add more files to existing session
- `POST /chat` - Non-streaming chat
- `POST /chat/stream` - Streaming chat (SSE)
- `GET /sessions/{session_id}/status` - Get session status
- `GET /data/{session_id}/{filename}` - Serve uploaded files for preview
