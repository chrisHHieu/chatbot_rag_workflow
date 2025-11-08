"""
Utility functions for working with session files and FAISS indices.
"""
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from langchain_core.documents import Document

from multi_doc_chat.utils.file_io import load_filename_mapping
from multi_doc_chat.src.document_ingestion.data_ingestion import FaissManager
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.logger import GLOBAL_LOGGER as log


def get_session_files_info_with_preview(
    session_id: str, 
    max_preview_length: int = 2000
) -> str:
    """
    Lấy danh sách files + preview cho mỗi file.
    
    Cách làm:
    1. Load FAISS vector store từ faiss_index/<session_id>
    2. Lấy TẤT CẢ documents từ vector store (không query)
    3. Group documents theo file_name trong metadata
    4. Với mỗi file, lấy chunk có chunk_index = 0 (chunk đầu tiên)
    5. Lấy preview từ chunk đó
    
    Args:
        session_id: Session ID
        max_preview_length: Maximum characters for content preview per file
    
    Returns:
        Formatted string with file information and content preview for SYSTEM_PROMPT
    """
    data_dir = Path("data") / session_id
    faiss_dir = Path("faiss_index") / session_id
    
    if not data_dir.exists() or not faiss_dir.exists():
        return "No documents have been uploaded to this session yet."
    
    # Load filename mapping
    filename_mapping = load_filename_mapping(data_dir)
    
    # Load FAISS vector store
    try:
        model_loader = ModelLoader()
        fm = FaissManager(faiss_dir, model_loader)
        
        # Check if index exists
        if not (faiss_dir / "index.faiss").exists():
            return "No documents have been indexed yet."
        
        # Load existing index
        vs = fm.load_or_create()
        
        # ✅ Lấy TẤT CẢ documents từ vector store (không query)
        all_docs = list(vs.docstore._dict.values())
        
        if not all_docs:
            return "No documents found in index."
        
        # ✅ Group documents theo file_name trong metadata
        docs_by_file: Dict[str, List[Document]] = {}
        for doc in all_docs:
            metadata = doc.metadata or {}
            file_name = metadata.get("file_name")  # saved_name (sanitized)
            
            if file_name:
                if file_name not in docs_by_file:
                    docs_by_file[file_name] = []
                docs_by_file[file_name].append(doc)
        
        log.info("Documents grouped by file", 
                total_docs=len(all_docs),
                files_count=len(docs_by_file),
                session_id=session_id)
        
    except Exception as e:
        log.error("Failed to load FAISS index", error=str(e), session_id=session_id)
        return "Failed to load document index."
    
    # Get all files from data directory
    files_info = []
    for file_path in data_dir.iterdir():
        if file_path.is_file() and file_path.name != "filename_mapping.json":
            saved_name = file_path.name  # saved_name trong FAISS
            original_name = filename_mapping.get(saved_name, saved_name)
            
            # Get file stats
            stat = file_path.stat()
            file_size = stat.st_size
            upload_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone(timedelta(hours=7)))
            
            # ✅ Lấy preview từ chunks của file này
            content_preview = ""
            if saved_name in docs_by_file:
                chunks = docs_by_file[saved_name]
                
                # ✅ Tìm chunk có chunk_index = 0 (chunk đầu tiên)
                first_chunk = None
                for chunk in chunks:
                    chunk_index = chunk.metadata.get("chunk_index", -1)
                    if chunk_index == 0:
                        first_chunk = chunk
                        break
                
                # Nếu không có chunk_index = 0, lấy chunk đầu tiên trong list
                if not first_chunk and chunks:
                    # Sort by chunk_index để lấy chunk đầu tiên
                    chunks_sorted = sorted(chunks, key=lambda c: c.metadata.get("chunk_index", 0))
                    first_chunk = chunks_sorted[0]
                
                # Lấy preview từ first_chunk
                if first_chunk:
                    content_preview = first_chunk.page_content[:max_preview_length].strip()
                    if len(first_chunk.page_content) > max_preview_length:
                        content_preview += "..."
            else:
                log.warning("File not found in FAISS index", 
                          saved_name=saved_name, 
                          session_id=session_id)
            
            # Format file info
            file_ext = file_path.suffix.upper().lstrip(".")
            files_info.append({
                "name": original_name,
                "saved_name": saved_name,  # For debugging
                "type": file_ext if file_ext else "Unknown",
                "size": file_size,
                "uploaded": upload_time.strftime("%d %B %Y, %H:%M:%S"),
                "preview": content_preview
            })
    
    if not files_info:
        return "No documents have been uploaded to this session yet."
    
    # Sort by upload time (newest first)
    files_info.sort(key=lambda x: x["uploaded"], reverse=True)
    
    # Format for LLM
    formatted_lines = ["📄 AVAILABLE DOCUMENTS IN THIS SESSION:"]
    formatted_lines.append("")
    
    for i, file_info in enumerate(files_info, 1):
        size_mb = file_info["size"] / (1024 * 1024)
        formatted_lines.append(
            f"{i}. **{file_info['name']}** ({file_info['type']} file, {size_mb:.2f} MB) - Uploaded: {file_info['uploaded']}"
        )
        
        # Add content preview if available
        if file_info["preview"]:
            # Clean up preview (remove extra whitespace, newlines)
            preview = " ".join(file_info["preview"].split())
            formatted_lines.append(f"   Preview: {preview}")
        
        formatted_lines.append("")  # Empty line between files
    
    formatted_lines.append("CONTEXT FOR RETRIEVAL:")
    formatted_lines.append("- When users ask about 'the document I just uploaded', 'the file', or 'my documents', they are referring to these files.")
    formatted_lines.append("- If users mention 'recently uploaded' or 'just uploaded' (or 'vừa upload'), prioritize the MOST RECENTLY UPLOADED files in the list.")
    formatted_lines.append("- Use the content previews above to understand what each file is about, which helps you construct better retrieval queries.")
    formatted_lines.append("- When users ask 'what's in the document?' or 'nội dung tài liệu có gì', retrieve information based on the preview context.")
    formatted_lines.append("- Files are listed in order of upload time (newest first).")
    
    return "\n".join(formatted_lines)

