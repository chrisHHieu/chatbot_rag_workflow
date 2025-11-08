# llmops_rag - Enterprise RAG System with LangGraph

Hệ thống RAG (Retrieval-Augmented Generation) enterprise-grade sử dụng **Hybrid Search** (FAISS + BM25) và **LangGraph** với persistent memory, được thiết kế để xử lý và trả lời câu hỏi từ tài liệu doanh nghiệp.

## 🎯 Features

### Core Capabilities
- ✅ **Hybrid Search**: Kết hợp semantic search (FAISS) và keyword search (BM25) để tìm kiếm chính xác
- ✅ **Multi-Document Support**: Hỗ trợ PDF, DOCX, TXT với session-based management
- ✅ **Persistent Memory**: Lưu trữ lịch sử hội thoại trong PostgreSQL với conversation summarization
- ✅ **Streaming Responses**: Real-time token-by-token streaming qua Server-Sent Events (SSE)
- ✅ **Citation Support**: Tự động trích dẫn nguồn (file name và page number) trong câu trả lời
- ✅ **Session Management**: Quản lý nhiều session độc lập, mỗi session có vector index riêng
- ✅ **Modern Web UI**: React + TypeScript interface với drag-and-drop, document preview, và markdown rendering

### Advanced Features
- 🔄 **Conversation Summarization**: Tự động tóm tắt cuộc hội thoại dài để duy trì context
- 📊 **Message Trimming**: Tự động cắt bớt messages cũ khi vượt token limit
- 🎨 **Progressive Markdown Rendering**: Render markdown real-time trong quá trình streaming
- 🗑️ **File Management**: Xóa file từ session, tự động cleanup khi session trống
- 🔍 **Smart Retrieval**: LLM tự quyết định khi nào cần retrieve thông tin từ documents

## 📁 Project Structure

```
llmops_rag/
├── main.py                          # CLI entry point (single PDF demo)
├── requirements.txt                  # Python dependencies
├── multi_doc_chat/                   # Main package
│   ├── api/                         # FastAPI application
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── schemas.py               # Pydantic request/response models
│   │   └── routes/                  # API endpoints
│   │       ├── chat.py              # Chat endpoints (streaming & non-streaming)
│   │       ├── files.py             # File upload/ingest/delete
│   │       ├── sessions.py          # Session management
│   │       ├── config.py             # Configuration endpoint
│   │       └── health.py             # Health checks
│   ├── config/
│   │   └── config.yaml              # Centralized configuration
│   ├── exception/
│   │   └── custom_exception.py     # Custom exception classes
│   ├── logger/
│   │   └── custom_logger.py        # Structured logging (structlog)
│   ├── model/
│   │   └── models.py                # Pydantic State model for LangGraph
│   ├── prompts/
│   │   └── prompt_library.py       # System & answer prompts
│   ├── src/
│   │   ├── document_ingestion/
│   │   │   └── data_ingestion.py   # Document loading, chunking, hybrid retriever
│   │   ├── document_chat/
│   │   │   ├── graph_nodes.py       # LangGraph nodes (generate_query_or_respond, generate_answer)
│   │   │   └── graph_builder.py    # Graph workflow builder
│   │   └── session_runner.py        # CLI session runner
│   └── utils/
│       ├── api_key_manager.py       # API key management (.env, JSON)
│       ├── checkpointer.py          # Postgres checkpoint setup
│       ├── config_loader.py         # YAML config loader
│       ├── document_ops.py          # Document loading utilities
│       ├── file_io.py               # File I/O & filename mapping
│       └── model_loader.py          # LLM & embedding loaders
├── UI/                              # React + TypeScript frontend
│   ├── App.tsx                      # Main React component
│   ├── components/                   # React components
│   │   ├── ChatMessage.tsx          # Chat message bubbles
│   │   ├── ChatInput.tsx            # Message input with modern features
│   │   ├── FileViewer.tsx           # Sidebar with file list & preview
│   │   ├── DocxViewer.tsx           # DOCX renderer (mammoth.js)
│   │   ├── MarkdownRenderer.tsx     # Markdown renderer (react-markdown)
│   │   └── icons.tsx                # SVG icons
│   ├── services/
│   │   └── apiService.ts            # API client
│   ├── types.ts                     # TypeScript interfaces
│   ├── index.html                   # HTML entry point
│   └── package.json                 # Frontend dependencies
├── tests/                           # Test suite
│   ├── unit/                        # Unit tests
│   └── integration/                 # Integration tests
├── data/                            # Uploaded documents (session-based)
└── faiss_index/                     # FAISS vector indices (session-based)
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for UI)
- **PostgreSQL** (for persistent memory)
- **OpenAI API Key**

### 1. Installation

#### Backend Setup

```bash
# Clone repository
cd llmops_rag

# Install Python dependencies
pip install -r requirements.txt
```

#### Frontend Setup

```bash
cd UI
npm install
```

### 2. Configuration

#### Environment Variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Database (PostgreSQL)
POSTGRES_URI=postgresql://user:password@localhost:5432/llmops_rag
# Or use DB_URI (backward compatible)
# DB_URI=postgresql://user:password@localhost:5432/llmops_rag

# Optional: LangSmith (for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=llmops_rag
```

#### Configuration File

Edit `multi_doc_chat/config/config.yaml` to customize:

- **Embedding model**: Default `text-embedding-3-large`
- **LLM models**: Response model (`gpt-4.1-mini`) and grader model (`gpt-4o-mini`)
- **Hybrid retriever weights**: Vector (0.7) + BM25 (0.3)
- **Text splitting**: Chunk size (800), overlap (150)
- **Summarization**: Token limits and thresholds
- **Message trimming**: Strategy and limits

### 3. Database Setup

Create PostgreSQL database:

```sql
CREATE DATABASE llmops_rag;
```

The system will automatically create required tables on first run.

### 4. Run the Application

#### Start Backend API

```bash
# From project root
python -m multi_doc_chat.api.main
# Or
uvicorn multi_doc_chat.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at `http://localhost:8000`

#### Start Frontend

```bash
cd UI
npm run dev
```

Frontend will be available at `http://localhost:3000` (or Vite's default port)

## 📖 Usage

### CLI Usage

#### Single PDF Demo (`main.py`)

```bash
python main.py
```

Edit `main.py` to customize:
- `pdf_path`: Path to PDF file
- `question`: User question
- `thread_id`: Conversation thread ID

#### Session Runner (`session_runner.py`)

**Create new session with files:**
```bash
python -m multi_doc_chat.src.session_runner new "Your question here" file1.pdf file2.docx --k 5
```

**Resume existing session:**
```bash
python -m multi_doc_chat.src.session_runner resume session_20251107_145458_d0fcb19d "Follow-up question"
```

### API Usage

#### Upload Files (Create Session)

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx"
```

Response:
```json
{
  "session_id": "session_20251107_145458_d0fcb19d",
  "indexed": true,
  "message": "Indexing complete"
}
```

#### Add Files to Existing Session

```bash
curl -X POST "http://localhost:8000/ingest?session_id=session_20251107_145458_d0fcb19d" \
  -F "files=@document3.pdf"
```

#### Streaming Chat

```bash
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_20251107_145458_d0fcb19d",
    "message": "What is the company policy on leave?"
  }'
```

Response format (SSE):
```
data: {"type": "status", "content": "🔍 Đang tìm kiếm thông tin..."}

data: {"type": "token", "content": "According"}

data: {"type": "token", "content": " to"}

...

data: {"type": "done"}
```

#### Non-Streaming Chat

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_20251107_145458_d0fcb19d",
    "message": "What is the company policy on leave?"
  }'
```

#### List Session Files

```bash
curl "http://localhost:8000/sessions/session_20251107_145458_d0fcb19d/files"
```

#### Delete File from Session

```bash
curl -X DELETE "http://localhost:8000/sessions/session_20251107_145458_d0fcb19d/files/document.pdf"
```

#### Delete Session

```bash
curl -X DELETE "http://localhost:8000/sessions/session_20251107_145458_d0fcb19d"
```

### Web UI Usage

1. **Upload Documents**: Click upload button or drag-and-drop files
2. **View Documents**: Click on file in sidebar to preview
3. **Chat**: Type question in input field, press Enter to send
4. **Streaming**: Watch real-time token-by-token response
5. **Delete Files**: Hover over file and click delete icon
6. **Session Persistence**: Session ID stored in localStorage

## 🏗️ Architecture

### Document Ingestion Flow

```
Upload Files
    ↓
Save to data/<session_id>/
    ↓
Load Documents (PDF/DOCX/TXT)
    ↓
Split into Chunks (RecursiveCharacterTextSplitter)
    ↓
Enrich Metadata (file_name, page_number, session_id, etc.)
    ↓
Create FAISS Index (with embeddings)
    ↓
Create BM25 Index (keyword search)
    ↓
Combine → Hybrid Retriever
```

### LangGraph Workflow

```
START
  ↓
Summarize (conversation summary)
  ↓
generate_query_or_respond
  ├─→ [Needs retrieval] → retrieve → generate_answer → END
  └─→ [Direct answer] → END
```

### Retrieval Process

1. **User Question** → `generate_query_or_respond` node
2. **LLM Decision**: Tool call (retrieve) or direct answer
3. **If retrieve**: 
   - Hybrid search (FAISS + BM25)
   - Format documents with citations: `[Source: file_name, Page: page_number]`
   - Return to `generate_answer` node
4. **Generate Answer**: LLM synthesizes response with citations

### Persistent Memory

- **PostgreSQL Checkpoint**: Stores conversation state
- **Conversation Summary**: Automatically summarizes long conversations
- **Message Trimming**: Removes old messages when token limit exceeded
- **Thread ID**: Each session has unique thread_id for conversation continuity

## ⚙️ Configuration

### `config.yaml` Structure

```yaml
embedding_model:
  provider: "openai"
  model_name: "text-embedding-3-large"

hybrid_retriever:
  vector_weight: 0.7      # Semantic search weight
  bm25_weight: 0.3        # Keyword search weight
  vector_k: 5             # Top k from vector search
  bm25_k: 5               # Top k from BM25 search
  search_type: "mmr"      # MMR for diversity
  fetch_k: 15             # Documents to fetch before MMR
  lambda_mult: 0.5        # Diversity parameter

text_splitter:
  chunk_size: 800
  chunk_overlap: 150
  add_start_index: true

llm:
  response:
    provider: "openai"
    model_name: "gpt-4.1-mini"
    temperature: 0.3
  grader:
    provider: "openai"
    model_name: "gpt-4o-mini"
    temperature: 0

summarization:
  max_tokens: 2048
  temperature: 0.1
  max_tokens_total: 100000
  max_tokens_before_summary: 80000
  max_summary_tokens: 1000

message_trimming:
  strategy: "last"
  max_tokens: 6000
  start_on: "human"
  end_on: ["human", "tool"]
  include_system: true
```

## 🔧 Key Components

### DocumentIngestor

- `load_documents()`: Load PDF/DOCX/TXT files
- `split_documents()`: Chunk documents with overlap
- `create_hybrid_retriever()`: Combine FAISS + BM25
- `create_retriever_tool()`: Create LangChain StructuredTool with citation formatting

### ChatIngestor

- Session-based multi-file ingestion
- Idempotent document addition (no duplicates)
- FAISS index management per session
- Filename mapping (sanitized ↔ original)

### FaissManager

- Load or create FAISS index
- Add documents idempotently
- Delete by file_name or file_hash
- Rebuild index when documents deleted

### GraphNodes

- `generate_query_or_respond()`: Decision node (retrieve or answer)
- `generate_answer()`: Answer generation with citations

### GraphBuilder

- Builds LangGraph workflow
- Integrates summarization node
- Configures conditional edges

## 📚 Dependencies

### Backend

- `langchain==1.0.3` - LangChain core
- `langchain-openai==1.0.2` - OpenAI integrations
- `langchain-community==0.4.1` - Community integrations
- `langgraph==1.0.2` - LangGraph workflow orchestration
- `langgraph-checkpoint-postgres==3.0.0` - PostgreSQL checkpoint
- `langmem==0.0.30` - Conversation summarization
- `faiss-cpu==1.12.0` - Vector similarity search
- `rank-bm25==0.2.2` - BM25 keyword search
- `langchain-classic==1.0.0` - Hybrid retriever
- `pymupdf==1.26.5` - PDF processing
- `psycopg-binary==3.2.12` - PostgreSQL driver
- `fastapi` - Web framework (not in requirements.txt, should be added)

### Frontend

- `react==^19.2.0` - React framework
- `react-dom==^19.2.0` - React DOM
- `react-markdown==^10.1.0` - Markdown rendering
- `remark-gfm==^4.0.1` - GitHub Flavored Markdown
- `rehype-highlight==^7.0.2` - Syntax highlighting
- `highlight.js==^11.11.1` - Highlight.js library
- `mammoth==^1.11.0` - DOCX to HTML conversion
- `vite==^6.2.0` - Build tool
- `typescript==~5.8.2` - TypeScript

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```

## 📝 API Documentation

Once the backend is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🎨 UI Features

- **Modern Design**: Tailwind CSS with custom color palette
- **Drag & Drop**: Upload files by dragging into sidebar
- **Document Preview**: View PDF, DOCX, and TXT files in sidebar
- **Streaming Chat**: Real-time token-by-token updates
- **Markdown Support**: Rich formatting with tables, lists, code blocks
- **Citation Display**: Source file and page number in responses
- **Session Management**: Visual session indicator
- **Responsive**: Works on desktop and tablet

## 🔍 Troubleshooting

### Database Connection Issues

Ensure PostgreSQL is running and `POSTGRES_URI` is correct:
```bash
psql -U postgres -c "SELECT 1"
```

### OpenAI API Key

Verify API key is set:
```bash
echo $OPENAI_API_KEY
```

### FAISS Index Not Found

If session index is missing, re-upload files to recreate the session.

### Frontend Not Connecting

Check `VITE_API_BASE_URL` in `UI/.env.local` matches backend URL.

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Contact

[Add contact information here]

---

**Built with ❤️ using LangGraph, LangChain, and React**
