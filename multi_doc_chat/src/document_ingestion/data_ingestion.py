from pathlib import Path
from typing import List, Optional, Iterable, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.tools.retriever import create_retriever_tool
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.tools import StructuredTool
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import RAGException
import sys
import json
import uuid
from datetime import datetime
import hashlib
from pydantic import BaseModel, Field

# Utilities for multi-file ingestion
from multi_doc_chat.utils.file_io import save_uploaded_files, load_filename_mapping
from multi_doc_chat.utils.document_ops import load_documents


class DocumentIngestor:
    """Handles document loading, chunking, and hybrid retriever creation."""
    
    def __init__(self, model_loader: Optional[ModelLoader] = None, config: Optional[dict] = None):
        """
        Initialize DocumentIngestor.
        
        Args:
            model_loader: Optional shared ModelLoader instance
            config: Optional config dict
        """
        self.model_loader = model_loader or ModelLoader(config=config)
        self.config = config or load_config()
        log.info("DocumentIngestor initialized")
    
    def load_documents(self, pdf_path: str) -> List[Document]:
        """Load documents from PDF file."""
        try:
            log.info("Loading documents", pdf_path=pdf_path)
            loader = PyPDFLoader(file_path=pdf_path)
            docs = loader.load()
            log.info("Documents loaded", count=len(docs))
            return docs
        except Exception as e:
            log.error("Failed loading documents", error=str(e))
            raise RAGException("Error loading documents", e)
    
    def split_documents(self, docs: List[Document]) -> List[Document]:
        """Split documents into chunks."""
        try:
            splitter_config = self.config["text_splitter"]
            chunk_size = splitter_config.get("chunk_size", 1000)
            chunk_overlap = splitter_config.get("chunk_overlap", 150)  # ✅ Updated to match config.yaml
            add_start_index = splitter_config.get("add_start_index", True)
            use_tiktoken = splitter_config.get("use_tiktoken", True)  # Default True for production
            
            # Get length function (tiktoken for accurate token counting or len for characters)
            from multi_doc_chat.utils.text_splitter import get_length_function
            length_function = get_length_function(use_tiktoken=use_tiktoken)
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                add_start_index=add_start_index,
                length_function=length_function,  # ✅ Use tiktoken for accurate token counting
            )
            
            doc_splits = text_splitter.split_documents(docs)
            log.info("Documents split", 
                    chunks=len(doc_splits), 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap,
                    length_function="tiktoken" if use_tiktoken else "len")
            return doc_splits
        except Exception as e:
            log.error("Failed splitting documents", error=str(e))
            raise RAGException("Error splitting documents", e)
    
    def create_hybrid_retriever(self, doc_splits: List[Document]):
        """Create hybrid retriever (FAISS vector + BM25 keyword)."""
        try:
            hybrid_config = self.config["hybrid_retriever"]
            vector_weight = hybrid_config.get("vector_weight", 0.7)
            bm25_weight = hybrid_config.get("bm25_weight", 0.3)
            vector_k = hybrid_config.get("vector_k", 14)  # ✅ Updated to match config.yaml
            bm25_k = hybrid_config.get("bm25_k", 6)  # ✅ Updated to match config.yaml
            search_type = hybrid_config.get("search_type", "mmr")
            fetch_k = hybrid_config.get("fetch_k", 20)  # ✅ Updated to match config.yaml
            lambda_mult = hybrid_config.get("lambda_mult", 0.5)
            
            log.info("Creating vector store...")
            embeddings = self.model_loader.load_embeddings()
            
            # 1. Vector Store Retriever (Semantic Search)
            vectorstore = FAISS.from_documents(
                documents=doc_splits,
                embedding=embeddings
            )
            
            search_kwargs = {"k": vector_k}
            if search_type == "mmr":
                search_kwargs["fetch_k"] = fetch_k
                search_kwargs["lambda_mult"] = lambda_mult
            
            vector_retriever = vectorstore.as_retriever(
                search_type=search_type,
                search_kwargs=search_kwargs
            )
            
            # 2. BM25 Retriever (Keyword Search)
            log.info("Creating BM25 retriever...")
            bm25_retriever = BM25Retriever.from_documents(doc_splits)
            bm25_retriever.k = bm25_k
            
            # 3. Ensemble Retriever (Hybrid = Vector + BM25)
            log.info("Creating hybrid ensemble retriever...")
            hybrid_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=[vector_weight, bm25_weight],
            )
            
            log.info("Hybrid retriever created", 
                    vector_weight=vector_weight, 
                    bm25_weight=bm25_weight)
            
            return hybrid_retriever
            
        except Exception as e:
            log.error("Failed creating hybrid retriever", error=str(e))
            raise RAGException("Failed to create hybrid retriever", e)
    

    def create_retriever_tool(self, hybrid_retriever, tool_name: str = "retrieve_data", 
                            description: str = "Search and return information about enterprise data from files"):
        """Create retriever tool that includes file name and page number for citation."""
        
        # Định nghĩa schema cho input
        class RetrieverInput(BaseModel):
            query: str = Field(description="The search query to retrieve relevant documents")
        
        def retrieve_and_format(query: str) -> str:
            """Retrieve documents and format with citation metadata."""
            try:
                # Retrieve documents from hybrid retriever
                docs: List[Document] = hybrid_retriever.invoke(query)
                
                if not docs:
                    log.warning("No documents retrieved", query=query)
                    return "No relevant documents found."
                
                # Load filename mapping from first document's session_id (if available)
                filename_mapping: Dict[str, str] = {}
                first_doc_metadata = docs[0].metadata or {}
                session_id = first_doc_metadata.get("session_id")
                
                if session_id:
                    # Load filename mapping from data/<session_id>/filename_mapping.json
                    data_dir = Path("data") / session_id
                    if data_dir.exists():
                        filename_mapping = load_filename_mapping(data_dir)
                        log.debug("Filename mapping loaded", session_id=session_id, mapping_count=len(filename_mapping))
                
                def format_document_with_metadata(doc: Document) -> str:
                    """Format a single document with comprehensive metadata for citation (Option 2)."""
                    from datetime import datetime
                    
                    metadata = doc.metadata or {}
                    saved_file_name = metadata.get("file_name", "Unknown Document")
                    
                    # Get original filename from mapping, fallback to saved_name
                    original_file_name = filename_mapping.get(saved_file_name, saved_file_name)
                    
                    # Build rich citation with multiple metadata fields
                    citation_parts = [f"Source: {original_file_name}"]
                    
                    # 1. Document Type (from file extension)
                    file_ext = metadata.get("file_ext", "")
                    if file_ext:
                        ext_upper = file_ext.upper().lstrip(".")
                        doc_type_map = {
                            "PDF": "PDF Document",
                            "DOCX": "Word Document", 
                            "DOC": "Word Document",
                            "TXT": "Text File",
                            "MD": "Markdown File"
                        }
                        doc_type = doc_type_map.get(ext_upper, f"{ext_upper} File")
                        citation_parts.append(f"Type: {doc_type}")
                    
                    # 2. Page Number
                    page_number = metadata.get("page_number", metadata.get("page", "?"))
                    if page_number != "?":
                        citation_parts.append(f"Page: {page_number}")
                    else:
                        citation_parts.append("Page: Unknown")
                    
                    # 3. Upload Date and Time (exact timestamp)
                    uploaded_at = metadata.get("uploaded_at")
                    if uploaded_at:
                        try:
                            # Parse ISO format (may have timezone or be naive)
                            upload_str = uploaded_at.replace('Z', '+00:00') if uploaded_at.endswith('Z') else uploaded_at
                            upload_date = datetime.fromisoformat(upload_str)
                            
                            # Ensure timezone-aware (convert to Vietnam timezone if needed)
                            from datetime import timezone, timedelta
                            vietnam_tz = timezone(timedelta(hours=7))
                            if upload_date.tzinfo is None:
                                # If naive, assume it's already in Vietnam timezone
                                upload_date = upload_date.replace(tzinfo=vietnam_tz)
                            else:
                                # Convert to Vietnam timezone
                                upload_date = upload_date.astimezone(vietnam_tz)
                            
                            # Format: "15 January 2025, 14:30:45"
                            date_time_str = upload_date.strftime("%d %B %Y, %H:%M:%S")
                            citation_parts.append(f"Uploaded: {date_time_str}")
                        except Exception as e:
                            log.debug("Failed to parse upload date", error=str(e), uploaded_at=uploaded_at)
                    
                    # 4. Chunk Position (Beginning/Middle/End based on chunk_index)
                    chunk_index = metadata.get("chunk_index", 0)
                    total_chunks = metadata.get("total_chunks")
                    
                    if total_chunks and total_chunks > 1:
                        position_ratio = chunk_index / total_chunks
                        if position_ratio < 0.1:
                            citation_parts.append("Section: Introduction")
                        elif position_ratio < 0.3:
                            citation_parts.append("Section: Early Content")
                        elif position_ratio < 0.7:
                            citation_parts.append("Section: Main Content")
                        elif position_ratio < 0.9:
                            citation_parts.append("Section: Later Content")
                        else:
                            citation_parts.append("Section: Conclusion")
                    elif chunk_index == 0:
                        citation_parts.append("Section: Beginning")
                    elif chunk_index > 10:
                        citation_parts.append("Section: Details")
                    
                    # 5. Document Version/Year (extract from filename if pattern matches)
                    # Pattern: "Policy_2025.pdf" or "Report_2024_Final.pdf"
                    import re
                    year_match = re.search(r'\b(20\d{2})\b', original_file_name)
                    if year_match:
                        year = year_match.group(1)
                        citation_parts.append(f"Version: {year}")
                    
                    # Format final citation
                    source_citation = f"[{', '.join(citation_parts)}]"
                    return f"{source_citation}\n{doc.page_content}"
                
                # Format each document with metadata
                formatted_docs = [format_document_with_metadata(doc) for doc in docs]
                
                # Join with double newline for readability
                result = "\n\n".join(formatted_docs)
                log.info("Documents retrieved and formatted", count=len(docs), query_length=len(query))
                return result
            except Exception as e:
                log.error("Error in retrieve_and_format", error=str(e), query=query)
                raise RAGException("Failed to retrieve and format documents", e)
        
        try:
            return StructuredTool(
                name=tool_name,
                description=description,
                func=retrieve_and_format,
                args_schema=RetrieverInput,  # ← THÊM DÒNG NÀY
            )
        except Exception as e:
            log.error("Failed creating retriever tool", error=str(e))
            raise RAGException("Failed to create retriever tool", e)


# ============================
# Session-based ingestion (optional)
# ============================

def generate_session_id() -> str:
    """Generate a unique session ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"session_{timestamp}_{unique_id}"


class ChatIngestor:
    """
    Sessionized ingestion manager for multi-file uploads.

    Unlike the single-file DocumentIngestor above, this class handles:
    - saving uploaded files into data/<session_id>
    - building/augmenting FAISS index in faiss_index/<session_id>
    - returning a retriever with configurable search_type (e.g., mmr)
    """

    def __init__(
        self,
        temp_base: str = "data",
        faiss_base: str = "faiss_index",
        use_session_dirs: bool = True,
        session_id: Optional[str] = None,
        model_loader: Optional[ModelLoader] = None,
        config: Optional[dict] = None,
    ):
        """
        Initialize ChatIngestor.
        
        Args:
            temp_base: Base directory for temporary files
            faiss_base: Base directory for FAISS indexes
            use_session_dirs: Whether to use session directories
            session_id: Optional session ID
            model_loader: Optional shared ModelLoader instance
            config: Optional config dict
        """
        try:
            self.model_loader = model_loader or ModelLoader(config=config)
            self.config = config or load_config()

            self.use_session = use_session_dirs
            self.session_id = session_id or generate_session_id()

            self.temp_base = Path(temp_base); self.temp_base.mkdir(parents=True, exist_ok=True)
            self.faiss_base = Path(faiss_base); self.faiss_base.mkdir(parents=True, exist_ok=True)

            self.temp_dir = self._resolve_dir(self.temp_base)
            self.faiss_dir = self._resolve_dir(self.faiss_base)

            log.info(
                "ChatIngestor initialized",
                session_id=self.session_id,
                temp_dir=str(self.temp_dir),
                faiss_dir=str(self.faiss_dir),
                sessionized=self.use_session,
            )
        except Exception as e:
            log.error("Failed to initialize ChatIngestor", error=str(e))
            raise RAGException("Initialization error in ChatIngestor", e)

    def _resolve_dir(self, base: Path):
        if self.use_session:
            d = base / self.session_id
            d.mkdir(parents=True, exist_ok=True)
            return d
        return base

    def _split(self, docs: List[Document], *, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None, add_start_index: Optional[bool] = None) -> List[Document]:
        # Load from config if not provided
        splitter_config = self.config.get("text_splitter", {})
        chunk_size = chunk_size if chunk_size is not None else splitter_config.get("chunk_size", 1000)  # ✅ Updated to match config.yaml
        chunk_overlap = chunk_overlap if chunk_overlap is not None else splitter_config.get("chunk_overlap", 150)
        add_start_index = add_start_index if add_start_index is not None else splitter_config.get("add_start_index", True)
        use_tiktoken = splitter_config.get("use_tiktoken", True)  # Default True for production
        
        # Get length function (tiktoken for accurate token counting or len for characters)
        from multi_doc_chat.utils.text_splitter import get_length_function
        length_function = get_length_function(use_tiktoken=use_tiktoken)
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap,
            add_start_index=add_start_index,
            length_function=length_function,  # ✅ Use tiktoken for accurate token counting
        )
        chunks = splitter.split_documents(docs)
        log.info("Documents split", 
                chunks=len(chunks), 
                chunk_size=chunk_size, 
                overlap=chunk_overlap,
                length_function="tiktoken" if use_tiktoken else "len")
        return chunks

    def build_retriever(
        self,
        uploaded_files: Iterable,
        *,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        k: Optional[int] = None,
        search_type: Optional[str] = None,
        fetch_k: Optional[int] = None,
        lambda_mult: Optional[float] = None,
    ):
        """Save files, (create|load) FAISS, add new docs idempotently, and return retriever."""
        try:
            # Load from config if not provided
            hybrid_config = self.config.get("hybrid_retriever", {})
            k = k or hybrid_config.get("vector_k", 14)  # ✅ Updated to match config.yaml
            search_type = search_type or hybrid_config.get("search_type", "mmr")
            fetch_k = fetch_k or hybrid_config.get("fetch_k", 20)  # ✅ Updated to match config.yaml
            lambda_mult = lambda_mult if lambda_mult is not None else hybrid_config.get("lambda_mult", 0.5)
            
            paths = save_uploaded_files(uploaded_files, self.temp_dir)
            log.info("Uploaded files saved", count=len(paths), temp_dir=str(self.temp_dir))
            docs = load_documents(paths)
            if not docs:
                raise ValueError("No valid documents loaded")

            log.info("Documents loaded", count=len(docs))
            chunks = self._split(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            # ============================
            # Enrich metadata for production-grade tracing
            # ============================
            # Store upload time in Vietnam timezone (UTC+7) with ISO format
            from datetime import timezone, timedelta
            vietnam_tz = timezone(timedelta(hours=7))
            uploaded_at = datetime.now(vietnam_tz).isoformat()
            # Compute stable file-level meta
            file_meta: Dict[str, Any] = {}
            for p in paths:
                try:
                    data = p.read_bytes()
                except Exception:
                    data = b""
                file_meta[str(p)] = {
                    "file_hash": hashlib.sha256(data).hexdigest(),
                    "doc_id": uuid.uuid4().hex[:8],
                    "file_name": p.name,
                    "file_ext": p.suffix.lower(),
                    "source_path": str(p),
                    "source_type": p.suffix.lower().lstrip("."),
                }
            
            # Calculate total chunks per file for accurate position calculation
            chunks_per_file: Dict[str, int] = {}
            for c in chunks:
                md = c.metadata or {}
                src = md.get("source") or md.get("file_path")
                file_key = str(src)
                chunks_per_file[file_key] = chunks_per_file.get(file_key, 0) + 1

            for idx, c in enumerate(chunks):
                md = c.metadata or {}
                src = md.get("source") or md.get("file_path")
                fm = file_meta.get(str(src), {})
                start = md.get("start_index")
                end = (start + len(c.page_content)) if isinstance(start, int) else None
                text_hash = hashlib.sha256(c.page_content.encode("utf-8")).hexdigest()
                page = md.get("page") or md.get("page_number") or 0
                chunk_index = md.get("chunk_index", idx)
                
                # Get total chunks for this specific file
                file_key = str(src)
                total_chunks_for_file = chunks_per_file.get(file_key, len(chunks))

                md.update({
                    "session_id": self.session_id,
                    "doc_id": fm.get("doc_id"),
                    "source_path": fm.get("source_path", src),
                    "file_name": fm.get("file_name"),
                    "file_ext": fm.get("file_ext"),
                    "file_hash": fm.get("file_hash"),
                    "source_type": fm.get("source_type", "unknown"),
                    "uploaded_at": uploaded_at,
                    "page_number": page,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks_for_file,  # ✅ Total chunks for this specific file (for accurate position calculation)
                    "start_index": start,
                    "end_index": end,
                    "text_hash": text_hash,
                    "ingest_version": "split:rcts-1000-200;embed:openai:text-embedding-3-large",
                })
                md["row_id"] = f"{self.session_id}:{md.get('doc_id')}:{page}:{chunk_index}"
                c.metadata = md
            # ============================

            fm = FaissManager(self.faiss_dir, self.model_loader)
            log.info("FAISS manager ready", index_dir=str(self.faiss_dir))

            texts = [c.page_content for c in chunks]
            metas = [c.metadata for c in chunks]

            try:
                vs = fm.load_or_create(texts=texts, metadatas=metas)
            except Exception:
                vs = fm.load_or_create(texts=texts, metadatas=metas)

            added = fm.add_documents(chunks)
            log.info("FAISS index updated", added=added, index=str(self.faiss_dir))

            # Configure search parameters
            search_kwargs: Dict[str, Any] = {"k": k}
            if search_type == "mmr":
                search_kwargs["fetch_k"] = fetch_k
                search_kwargs["lambda_mult"] = lambda_mult
                log.info("Using MMR search", k=k, fetch_k=fetch_k, lambda_mult=lambda_mult)

            log.info("Retriever created", search_type=search_type, search_kwargs=search_kwargs)
            return vs.as_retriever(search_type=search_type, search_kwargs=search_kwargs)

        except Exception as e:
            log.error("Failed to build retriever", error=str(e))
            raise RAGException("Failed to build retriever", e)


class FaissManager:
    """Minimal FAISS manager for session-scoped index with idempotent adds."""

    def __init__(self, index_dir: Path, model_loader: Optional[ModelLoader] = None):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.meta_path = self.index_dir / "ingested_meta.json"
        self._meta: Dict[str, Any] = {"rows": {}}

        if self.meta_path.exists():
            try:
                self._meta = json.loads(self.meta_path.read_text(encoding="utf-8")) or {"rows": {}}
            except Exception:
                self._meta = {"rows": {}}

        self.model_loader = model_loader or ModelLoader()
        self.emb = self.model_loader.load_embeddings()
        self.vs: Optional[FAISS] = None

    def _exists(self) -> bool:
        return (self.index_dir / "index.faiss").exists() and (self.index_dir / "index.pkl").exists()

    @staticmethod
    def _fingerprint(text: str, md: Dict[str, Any]) -> str:
        # Prefer stable row_id if present
        rid = md.get("row_id")
        if rid:
            return str(rid)
        # Next prefer file_hash + chunk_index for stability across runs
        fh = md.get("file_hash")
        ci = md.get("chunk_index")
        if fh is not None and ci is not None:
            return f"{fh}:{ci}"
        # Fallback: use source path if available
        src = md.get("source") or md.get("file_path")
        if src is not None:
            return f"{src}"
        # Final fallback: content hash
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _save_meta(self):
        self.meta_path.write_text(json.dumps(self._meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_documents(self, docs: List[Document]) -> int:
        if self.vs is None:
            raise RuntimeError("Call load_or_create() before add_documents().")

        new_docs: List[Document] = []
        for d in docs:
            key = self._fingerprint(d.page_content, d.metadata or {})
            if key in self._meta["rows"]:
                continue
            self._meta["rows"][key] = True
            new_docs.append(d)

        if new_docs:
            self.vs.add_documents(new_docs)
            self.vs.save_local(str(self.index_dir))
            self._save_meta()
        return len(new_docs)

    def load_or_create(self, texts: Optional[List[str]] = None, metadatas: Optional[List[dict]] = None):
        if self._exists():
            self.vs = FAISS.load_local(
                str(self.index_dir),
                embeddings=self.emb,
                allow_dangerous_deserialization=True,
            )
            return self.vs

        if not texts:
            raise RAGException("No existing FAISS index and no data to create one", sys)
        self.vs = FAISS.from_texts(texts=texts, embedding=self.emb, metadatas=metadatas or [])
        self.vs.save_local(str(self.index_dir))
        return self.vs

    def delete_by_file_hash(self, file_hash: str) -> tuple[int, bool]:
        """Delete all documents with matching file_hash by rebuilding index.
        
        Args:
            file_hash: SHA256 hash of the file to delete
        
        Returns:
            Tuple of (number of documents deleted, is_index_empty)
        """
        if self.vs is None:
            raise RuntimeError("Call load_or_create() before delete_by_file_hash().")
        
        # Get all documents from index
        all_docs = list(self.vs.docstore._dict.values())
        
        # Filter: keep documents that DON'T have matching file_hash
        docs_to_keep = [
            doc for doc in all_docs 
            if (doc.metadata or {}).get("file_hash") != file_hash
        ]
        
        # Count deleted
        deleted_count = len(all_docs) - len(docs_to_keep)
        is_index_empty = len(docs_to_keep) == 0
        
        if deleted_count > 0:
            # Rebuild index with remaining documents
            if docs_to_keep:
                texts = [doc.page_content for doc in docs_to_keep]
                metas = [doc.metadata for doc in docs_to_keep]
                
                self.vs = FAISS.from_texts(
                    texts=texts, 
                    embedding=self.emb, 
                    metadatas=metas
                )
                self.vs.save_local(str(self.index_dir))
            else:
                # No documents left, delete index files
                index_files = [
                    self.index_dir / "index.faiss",
                    self.index_dir / "index.pkl",
                    self.meta_path,
                ]
                for f in index_files:
                    if f.exists():
                        f.unlink()
                self.vs = None
                self._meta = {"rows": {}}
            
            # Update metadata tracking
            if docs_to_keep:
                self._meta["rows"] = {
                    self._fingerprint(doc.page_content, doc.metadata or {}): True
                    for doc in docs_to_keep
                }
                self._save_meta()
            
            log.info("Documents deleted by file_hash", 
                    file_hash=file_hash, 
                    deleted=deleted_count,
                    remaining=len(docs_to_keep),
                    is_index_empty=is_index_empty)
        
        return deleted_count, is_index_empty

    def delete_by_file_name(self, file_name: str) -> tuple[int, bool]:
        """Delete all documents with matching file_name by rebuilding index.
        
        Args:
            file_name: Name of the file to delete
        
        Returns:
            Tuple of (number of documents deleted, is_index_empty)
        """
        if self.vs is None:
            raise RuntimeError("Call load_or_create() before delete_by_file_name().")
        
        # Get all documents from index
        all_docs = list(self.vs.docstore._dict.values())
        
        # Filter: keep documents that DON'T have matching file_name
        docs_to_keep = [
            doc for doc in all_docs 
            if (doc.metadata or {}).get("file_name") != file_name
        ]
        
        # Count deleted
        deleted_count = len(all_docs) - len(docs_to_keep)
        is_index_empty = len(docs_to_keep) == 0
        
        if deleted_count > 0:
            # Rebuild index with remaining documents
            if docs_to_keep:
                texts = [doc.page_content for doc in docs_to_keep]
                metas = [doc.metadata for doc in docs_to_keep]
                
                self.vs = FAISS.from_texts(
                    texts=texts, 
                    embedding=self.emb, 
                    metadatas=metas
                )
                self.vs.save_local(str(self.index_dir))
            else:
                # No documents left, delete index files
                index_files = [
                    self.index_dir / "index.faiss",
                    self.index_dir / "index.pkl",
                    self.meta_path,
                ]
                for f in index_files:
                    if f.exists():
                        f.unlink()
                self.vs = None
                self._meta = {"rows": {}}
            
            # Update metadata tracking
            if docs_to_keep:
                self._meta["rows"] = {
                    self._fingerprint(doc.page_content, doc.metadata or {}): True
                    for doc in docs_to_keep
                }
                self._save_meta()
            
            log.info("Documents deleted by file_name", 
                    file_name=file_name, 
                    deleted=deleted_count,
                    remaining=len(docs_to_keep),
                    is_index_empty=is_index_empty)
        
        return deleted_count, is_index_empty


# ============================
# Helper: load retriever from existing session index
# ============================

def load_session_retriever(
    session_id: str,
    *,
    k: Optional[int] = None,
    search_type: Optional[str] = None,
    fetch_k: Optional[int] = None,
    lambda_mult: Optional[float] = None,
):
    """Load a retriever from faiss_index/<session_id> using current embedding model.

    This is used for resuming conversation over an existing session (single-thread per session).
    """
    try:
        # Load from config if not provided
        config = load_config()
        hybrid_config = config.get("hybrid_retriever", {})
        k = k or hybrid_config.get("vector_k", 14)  # ✅ Updated to match config.yaml
        search_type = search_type or hybrid_config.get("search_type", "mmr")
        fetch_k = fetch_k or hybrid_config.get("fetch_k", 20)  # ✅ Updated to match config.yaml
        lambda_mult = lambda_mult if lambda_mult is not None else hybrid_config.get("lambda_mult", 0.5)
        
        index_path = Path("faiss_index") / session_id
        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index for session not found: {index_path}")

        embeddings = ModelLoader().load_embeddings()
        vs = FAISS.load_local(
            str(index_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )

        search_kwargs: Dict[str, Any] = {"k": k}
        if search_type == "mmr":
            search_kwargs["fetch_k"] = fetch_k
            search_kwargs["lambda_mult"] = lambda_mult

        log.info("Session retriever loaded", index_path=str(index_path), search_type=search_type, search_kwargs=search_kwargs)
        return vs.as_retriever(search_type=search_type, search_kwargs=search_kwargs)
    except Exception as e:
        log.error("Failed to load session retriever", error=str(e), session_id=session_id)
        raise RAGException("Failed to load session retriever", e)

