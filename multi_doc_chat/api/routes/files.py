from typing import List
from pathlib import Path
import shutil

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from multi_doc_chat.api.schemas import UploadResponse, IngestResponse

from multi_doc_chat.src.document_ingestion.data_ingestion import ChatIngestor, FaissManager
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.api.routes.sessions import generate_sample_questions_from_retriever
from multi_doc_chat.api.dependencies import get_model_loader, get_config


router = APIRouter(tags=["files"])


class FastAPIFileAdapter:
    def __init__(self, uf: UploadFile):
        self._uf = uf
        self.filename = uf.filename or "file"
    
    def read(self):
        self._uf.file.seek(0)
        return self._uf.file.read()


def validate_file_limits(
    files: List[UploadFile], 
    session_id: str = None
) -> None:
    """
    Validate file size limits based on config.
    
    Raises HTTPException if validation fails.
    """
    config = load_config()
    limits = config.get("file_limits", {})
    
    max_file_size_mb = limits.get("max_file_size_mb", 20)
    max_session_size_mb = limits.get("max_session_size_mb", 100)
    max_files_per_session = limits.get("max_files_per_session", 15)
    
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    max_session_size_bytes = max_session_size_mb * 1024 * 1024
    
    # Calculate file sizes and reset file pointers
    file_sizes = []
    for file in files:
        # Try to get file size - FastAPI UploadFile may have size attribute
        # If not, read from file stream
        file_size = 0
        try:
            # Check if file has size attribute (some UploadFile implementations)
            if hasattr(file, 'size') and file.size is not None:
                file_size = file.size
            else:
                # Read file size from stream
                # Save current position
                current_pos = file.file.tell()
                file.file.seek(0, 2)  # Seek to end
                file_size = file.file.tell()
                file.file.seek(current_pos)  # Reset to original position (not necessarily 0)
        except (AttributeError, OSError, ValueError) as e:
            log.error("Failed to get file size for validation", filename=file.filename, error=str(e))
            raise HTTPException(
                status_code=400,
                detail=f"Không thể đọc kích thước file '{file.filename}'. Vui lòng thử lại."
            )
        file_sizes.append((file, file_size))
    
    # Check individual file sizes
    for file, file_size in file_sizes:
        if file_size > max_file_size_bytes:
            file_size_mb = file_size / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' quá lớn ({file_size_mb:.2f} MB). "
                       f"Kích thước tối đa cho phép: {max_file_size_mb} MB. "
                       f"Vui lòng chia nhỏ file hoặc nén file."
            )
    
    # Check total number of files (for new session)
    if session_id is None and len(files) > max_files_per_session:
        raise HTTPException(
            status_code=400,
            detail=f"Số lượng file vượt quá giới hạn. "
                   f"Tối đa {max_files_per_session} files mỗi session. "
                   f"Bạn đã chọn {len(files)} files."
        )
    
    # Check total session size (if session_id provided)
    if session_id:
        try:
            # Get existing files in session
            data_dir = Path("data") / session_id
            existing_size = 0
            existing_count = 0
            
            if data_dir.exists():
                for f in data_dir.iterdir():
                    if f.is_file() and f.name != "filename_mapping.json":
                        existing_size += f.stat().st_size
                        existing_count += 1
            
            # Calculate total size after adding new files
            new_files_size = sum(size for _, size in file_sizes)
            total_size = existing_size + new_files_size
            total_files = existing_count + len(files)
            
            # Check total session size
            if total_size > max_session_size_bytes:
                total_size_mb = total_size / (1024 * 1024)
                raise HTTPException(
                    status_code=413,
                    detail=f"Tổng kích thước session vượt quá giới hạn ({total_size_mb:.2f} MB / {max_session_size_mb} MB). "
                           f"Vui lòng xóa một số file cũ hoặc tạo session mới."
                )
            
            # Check total number of files
            if total_files > max_files_per_session:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số lượng file trong session vượt quá giới hạn ({total_files} / {max_files_per_session}). "
                           f"Vui lòng xóa một số file cũ hoặc tạo session mới."
                )
        except HTTPException:
            raise
        except Exception as e:
            log.warning("Failed to check session size limits", error=str(e), session_id=session_id)
            # Don't fail upload if we can't check - just log warning


@router.post("/upload", response_model=UploadResponse)
async def upload(
    files: List[UploadFile] = File(...),
    generate_questions: bool = Query(True, description="Whether to generate sample questions"),
    model_loader: ModelLoader = Depends(get_model_loader),
    config: dict = Depends(get_config)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # ✅ Validate file size limits
    validate_file_limits(files)

    # ✅ Pass shared model_loader and config
    ci = ChatIngestor(
        use_session_dirs=True,
        model_loader=model_loader,
        config=config
    )
    session_id = ci.session_id
    adapters = [FastAPIFileAdapter(f) for f in files]
    
    # Build retriever and get it back (it returns the retriever)
    retriever = ci.build_retriever(adapters)
    
    # Generate sample questions if requested
    questions = None
    if generate_questions:
        try:
            log.info("Generating sample questions for new session", session_id=session_id)
            questions = generate_sample_questions_from_retriever(
                retriever, 
                session_id=session_id,
                model_loader=model_loader,
                config=config
            )
        except Exception as e:
            log.warning("Failed to generate sample questions during upload", error=str(e), session_id=session_id)
            # Continue without questions - upload is still successful
    
    return UploadResponse(
        session_id=session_id, 
        indexed=True, 
        message="Indexing complete",
        questions=questions
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    session_id: str, 
    files: List[UploadFile] = File(...),
    generate_questions: bool = Query(True, description="Whether to generate sample questions"),
    model_loader: ModelLoader = Depends(get_model_loader),
    config: dict = Depends(get_config)
):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # ✅ Validate file size limits (including session limits)
    validate_file_limits(files, session_id=session_id)

    # ✅ Pass shared model_loader and config
    ci = ChatIngestor(
        use_session_dirs=True, 
        session_id=session_id,
        model_loader=model_loader,
        config=config
    )
    adapters = [FastAPIFileAdapter(f) for f in files]
    
    # Build retriever and get it back (it returns the retriever)
    retriever = ci.build_retriever(adapters)
    
    # Generate sample questions if requested
    questions = None
    if generate_questions:
        try:
            log.info("Generating sample questions for existing session", session_id=session_id)
            questions = generate_sample_questions_from_retriever(
                retriever, 
                session_id=session_id,
                model_loader=model_loader,
                config=config
            )
        except Exception as e:
            log.warning("Failed to generate sample questions during ingest", error=str(e), session_id=session_id)
            # Continue without questions - ingest is still successful
    
    return IngestResponse(
        session_id=session_id, 
        indexed=True, 
        message="Index updated",
        questions=questions
    )


@router.delete("/sessions/{session_id}/files/{file_name}")
async def delete_file_from_session(
    session_id: str, 
    file_name: str,
    model_loader: ModelLoader = Depends(get_model_loader)  # ✅ Add dependency injection
):
    """Delete a specific file from session's FAISS index.
    
    This will:
    1. Remove all document chunks with matching file_name from FAISS index
    2. Delete the physical file from data directory
    3. Rebuild the FAISS index with remaining documents
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not file_name:
        raise HTTPException(status_code=400, detail="file_name is required")
    
    try:
        index_dir = Path("faiss_index") / session_id
        if not index_dir.exists():
            raise HTTPException(status_code=404, detail="Session index not found")
        
        # Load existing FAISS index
        fm = FaissManager(index_dir, model_loader)  # ✅ Dùng dependency injection
        fm.load_or_create()  # Load existing index
        
        # Delete documents by file_name
        deleted_count, is_index_empty = fm.delete_by_file_name(file_name)
        
        # Also delete physical file from data directory
        data_dir = Path("data") / session_id
        file_path = data_dir / file_name
        if file_path.exists():
            file_path.unlink()
            log.info("Physical file deleted", file_path=str(file_path))
        
        # If index is empty after deletion, delete entire session folders
        session_deleted = False
        if is_index_empty:
            # Delete data directory
            if data_dir.exists():
                shutil.rmtree(data_dir, ignore_errors=True)
                log.info("Session data directory deleted (empty)", session_id=session_id)
            
            # Delete index directory
            if index_dir.exists():
                shutil.rmtree(index_dir, ignore_errors=True)
                log.info("Session index directory deleted (empty)", session_id=session_id)
            
            session_deleted = True
        
        return {
            "deleted": deleted_count > 0,
            "deleted_chunks": deleted_count,
            "file_name": file_name,
            "session_id": session_id,
            "session_deleted": session_deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to delete file from session", error=str(e), 
                 session_id=session_id, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


