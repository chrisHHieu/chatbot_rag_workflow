from pathlib import Path
from typing import List, Optional
import shutil
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from multi_doc_chat.api.schemas import (
    SessionStatus, 
    SampleQuestionsResponse, 
    DeleteSessionResponse,
    ConversationHistoryResponse,
    ChatMessage
)
from multi_doc_chat.utils.file_io import load_filename_mapping
from multi_doc_chat.src.document_ingestion.data_ingestion import load_session_retriever
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.checkpointer import CheckpointerManager
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, MessagesState, START
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.api.dependencies import get_model_loader, get_config


router = APIRouter(prefix="/sessions", tags=["sessions"])


# ✅ Helper functions to save/load sample questions
def save_sample_questions(session_id: str, questions: List[str]) -> None:
    """Save sample questions to file for persistence."""
    try:
        index_dir = Path("faiss_index") / session_id
        index_dir.mkdir(parents=True, exist_ok=True)
        questions_file = index_dir / "sample_questions.json"
        questions_file.write_text(
            json.dumps({"questions": questions}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        log.info("Sample questions saved", session_id=session_id, count=len(questions))
    except Exception as e:
        log.warning("Failed to save sample questions", session_id=session_id, error=str(e))


def load_sample_questions(session_id: str) -> Optional[List[str]]:
    """Load sample questions from file."""
    try:
        index_dir = Path("faiss_index") / session_id
        questions_file = index_dir / "sample_questions.json"
        if questions_file.exists():
            data = json.loads(questions_file.read_text(encoding="utf-8"))
            questions = data.get("questions", [])
            if questions:
                log.info("Sample questions loaded from file", session_id=session_id, count=len(questions))
                return questions
    except Exception as e:
        log.warning("Failed to load sample questions from file", session_id=session_id, error=str(e))
    return None


def generate_sample_questions_from_retriever(
    retriever: BaseRetriever,
    session_id: Optional[str] = None,
    model_loader: Optional[ModelLoader] = None,
    config: Optional[dict] = None
) -> List[str]:
    """
    Generate sample questions from a retriever.
    
    Args:
        retriever: The retriever to use for getting documents
        session_id: Optional session_id for logging
    
    Returns:
        List of sample questions (4-6 questions)
    """
    try:
        # Get representative documents by querying with generic terms
        sample_queries = [
            "tổng quan nội dung",
            "chủ đề chính",
            "thông tin quan trọng",
        ]
        
        all_docs = []
        seen_content = set()
        
        # Collect diverse document chunks
        for query in sample_queries:
            try:
                docs = retriever.invoke(query)
                for doc in docs:
                    content_hash = hash(doc.page_content[:100])  # Simple deduplication
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        all_docs.append(doc)
                        if len(all_docs) >= 10:  # Limit to 10 chunks
                            break
                if len(all_docs) >= 10:
                    break
            except Exception as e:
                log.debug("Failed to retrieve documents for query", query=query, error=str(e))
                continue
        
        if not all_docs:
            # Fallback: return generic questions if no documents found
            log.warning("No documents found for question generation", session_id=session_id)
            return [
                "Tóm tắt nội dung chính của tài liệu",
                "Có những chủ đề nào được đề cập?",
                "Thông tin quan trọng nhất là gì?",
                "Có quy trình nào được mô tả không?"
            ]
        
        # Prepare document content for LLM
        doc_summaries = []
        for i, doc in enumerate(all_docs[:8]):  # Use first 8 chunks
            metadata = doc.metadata or {}
            file_name = metadata.get("file_name", "Document")
            # Truncate long content
            content_preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            doc_summaries.append(f"Tài liệu {i+1} ({file_name}):\n{content_preview}")
        
        documents_text = "\n\n".join(doc_summaries)
        
        # Load LLM for question generation
        # ✅ Use provided model_loader or create new one
        if model_loader is None:
            model_loader = ModelLoader(config=config)
        llm = model_loader.load_response_model()
        
        # Create prompt for generating questions
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """Bạn là một trợ lý AI chuyên tạo các câu hỏi mẫu dựa trên nội dung tài liệu.
Nhiệm vụ của bạn là phân tích nội dung tài liệu và tạo ra 4-6 câu hỏi mẫu thực tế, cụ thể và hữu ích mà người dùng có thể hỏi về tài liệu này.

Yêu cầu:
- Câu hỏi phải dựa trên nội dung THỰC TẾ trong tài liệu
- Câu hỏi phải cụ thể, không chung chung
- Câu hỏi nên đa dạng về loại (tổng quan, chi tiết, so sánh, hướng dẫn)
- Câu hỏi bằng tiếng Việt
- Mỗi câu hỏi trên một dòng
- Chỉ trả về danh sách câu hỏi, không có số thứ tự, không có giải thích"""),
            ("user", """Dựa trên nội dung tài liệu sau, hãy tạo 4-6 câu hỏi mẫu cụ thể và thực tế:

{documents}

Chỉ trả về danh sách câu hỏi, mỗi câu hỏi một dòng, không đánh số thứ tự.""")
        ])
        
        # Generate questions
        chain = prompt_template | llm
        response = chain.invoke({"documents": documents_text})
        
        # Parse response - extract questions (one per line)
        questions_text = response.content.strip()
        questions = [
            q.strip() 
            for q in questions_text.split('\n') 
            if q.strip() and not q.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '-', '*'))
        ]
        
        # Clean up questions (remove numbering if any)
        cleaned_questions = []
        for q in questions:
            # Remove leading numbers/dashes
            q = q.lstrip('0123456789.-* ').strip()
            if q and len(q) > 10:  # Minimum length check
                cleaned_questions.append(q)
        
        # Ensure we have at least 4 questions
        if len(cleaned_questions) < 4:
            # Add fallback questions
            fallbacks = [
                "Tóm tắt nội dung chính của tài liệu",
                "Có những chủ đề nào được đề cập?",
                "Thông tin quan trọng nhất là gì?",
                "Có quy trình nào được mô tả không?"
            ]
            cleaned_questions.extend(fallbacks[:4 - len(cleaned_questions)])
        
        # Limit to 6 questions max
        final_questions = cleaned_questions[:6]
        
        # ✅ Save questions to file for persistence
        if session_id and final_questions:
            save_sample_questions(session_id, final_questions)
        
        log.info("Sample questions generated", count=len(final_questions), session_id=session_id)
        return final_questions
        
    except Exception as e:
        log.error("Failed to generate sample questions", error=str(e), session_id=session_id)
        # Return fallback questions on error
        fallback_questions = [
            "Tóm tắt nội dung chính của tài liệu",
            "Có những chủ đề nào được đề cập?",
            "Thông tin quan trọng nhất là gì?",
            "Có quy trình nào được mô tả không?"
        ]
        # ✅ Save fallback questions too (so they persist)
        if session_id:
            save_sample_questions(session_id, fallback_questions)
        return fallback_questions


@router.get("/{session_id}/status", response_model=SessionStatus)
def session_status(session_id: str):
    data_dir = Path("data") / session_id
    index_dir = Path("faiss_index") / session_id
    exists = index_dir.exists()

    ingested_meta_path = index_dir / "ingested_meta.json"
    docs_count = None
    if ingested_meta_path.exists():
        try:
            import json
            meta = json.loads(ingested_meta_path.read_text(encoding="utf-8"))
            docs_count = len((meta or {}).get("rows", {}))
        except Exception:
            docs_count = None

    return SessionStatus(
        exists=exists,
        data_path=str(data_dir),
        index_path=str(index_dir),
        docs_count=docs_count,
    )


@router.get("/{session_id}/files")
def list_session_files(session_id: str):
    """List actual files in the session data directory.
    
    Returns both saved_name (for URL/delete operations) and original_name (for display).
    """
    data_dir = Path("data") / session_id
    if not data_dir.exists():
        return {"files": []}
    
    # Load filename mapping (saved_name -> original_name)
    filename_mapping = load_filename_mapping(data_dir)
    
    files = []
    for f in data_dir.iterdir():
        if f.is_file() and f.name != "filename_mapping.json":  # Skip mapping file itself
            saved_name = f.name
            original_name = filename_mapping.get(saved_name, saved_name)  # Fallback to saved_name if no mapping
            
            files.append({
                "name": saved_name,  # Use for URL/delete operations
                "original_name": original_name,  # Use for display in UI
                "size": f.stat().st_size,
                "path": str(f),
            })
    
    return {"files": files}


@router.get("/{session_id}/sample-questions", response_model=SampleQuestionsResponse)
async def get_sample_questions(session_id: str):
    """
    Get sample questions for a session.
    
    This endpoint:
    1. First tries to load saved questions from file (if exists)
    2. If not found, generates new questions based on document content
    3. Returns 4-6 sample questions
    """
    try:
        # ✅ Try to load from file first (persisted questions)
        saved_questions = load_sample_questions(session_id)
        if saved_questions:
            return SampleQuestionsResponse(questions=saved_questions)
        
        # ✅ If not found, generate new ones
        index_dir = Path("faiss_index") / session_id
        if not index_dir.exists():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Load retriever and generate
        retriever = load_session_retriever(session_id=session_id)
        questions = generate_sample_questions_from_retriever(retriever, session_id=session_id)
        
        return SampleQuestionsResponse(questions=questions)
        
    except HTTPException:
        raise
    except Exception as e:
        # Return generic questions on error
        generic_questions = [
            "Tóm tắt nội dung chính của tài liệu",
            "Có những chủ đề nào được đề cập?",
            "Thông tin quan trọng nhất là gì?",
            "Có quy trình nào được mô tả không?"
        ]
        # ✅ Save generic questions for persistence
        try:
            save_sample_questions(session_id, generic_questions)
        except:
            pass  # Ignore save errors
        return SampleQuestionsResponse(questions=generic_questions)


@router.get("/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(session_id: str):
    """
    Get conversation history from checkpointer for a session.
    
    This endpoint:
    1. Loads the checkpointer
    2. Retrieves conversation state using session_id as thread_id
    3. Filters messages to return only HumanMessage and AIMessage with content
    4. Returns formatted messages (role, content)
    
    Note: This endpoint does NOT require FAISS index or retriever.
    It only reads from checkpointer, so it works even when session has no files.
    
    Returns:
        ConversationHistoryResponse with list of messages
    """
    # ✅ Normalize session_id (remove leading/trailing whitespace)
    session_id = session_id.strip()
    
    try:
        # ✅ Đơn giản hóa: Chỉ cần checkpointer với MessagesState, KHÔNG cần retriever
        # ✅ KHÔNG gọi load_session_retriever - chỉ đọc từ checkpointer
        log.info("Loading conversation history from checkpointer (no retriever needed)", 
                session_id=session_id)
        
        try:
            # Tạo graph đơn giản với MessagesState để truy cập checkpointer
            async def dummy_node(state: MessagesState):
                return state
            
            builder = StateGraph(MessagesState)
            builder.add_node("dummy", dummy_node)
            builder.add_edge(START, "dummy")
            
            # Get checkpointer and compile graph
            cm = CheckpointerManager()
            checkpointer = await cm.get_checkpointer()
            async with checkpointer as cp:
                graph = builder.compile(checkpointer=cp)
                
                # Get state using session_id as thread_id
                config = {"configurable": {"thread_id": session_id}}
                state = await graph.aget_state(config)
                
                # Get messages from state
                if state is None:
                    log.info("No state found in checkpointer", session_id=session_id)
                    return ConversationHistoryResponse(
                        session_id=session_id,
                        messages=[],
                        total_messages=0
                    )
                
                # Extract messages from state.values
                messages = []
                if hasattr(state, 'values') and state.values is not None:
                    if isinstance(state.values, dict):
                        messages = state.values.get("messages", [])
                
                # Filter messages: only HumanMessage and AIMessage with content
                # Remove ToolMessage and empty AIMessage (only tool_calls)
                filtered_messages: List[ChatMessage] = []
                
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        content = msg.content
                        if content and isinstance(content, str) and content.strip():
                            filtered_messages.append(ChatMessage(
                                role="user",
                                content=content
                            ))
                    elif isinstance(msg, AIMessage):
                        content = msg.content
                        if content and isinstance(content, str) and content.strip():
                            filtered_messages.append(ChatMessage(
                                role="assistant",
                                content=content
                            ))
                
                log.info("Retrieved conversation history", 
                        session_id=session_id, 
                        total_messages=len(messages),
                        filtered_messages=len(filtered_messages))
                
                return ConversationHistoryResponse(
                    session_id=session_id,
                    messages=filtered_messages,
                    total_messages=len(filtered_messages)
                )
                
        except Exception as e:
            # Checkpointer may not be configured or thread doesn't exist
            # ✅ IMPORTANT: This should NOT involve load_session_retriever
            log.warning("Failed to load conversation history from checkpointer", 
                       session_id=session_id, 
                       error=str(e),
                       error_type=type(e).__name__)
            return ConversationHistoryResponse(
                session_id=session_id,
                messages=[],
                total_messages=0
            )
            
    except Exception as e:
        # ✅ Catch any unexpected errors (should not include load_session_retriever)
        log.error("Unexpected error loading conversation history", 
                 session_id=session_id, 
                 error=str(e),
                 error_type=type(e).__name__)
        # Return empty history on error
        return ConversationHistoryResponse(
            session_id=session_id,
            messages=[],
            total_messages=0
        )


@router.delete("/{session_id}/files", response_model=DeleteSessionResponse)
async def delete_all_session_files(session_id: str):
    """
    Delete all files from a session (data and FAISS index) but keep the session.
    
    This endpoint:
    1. Deletes the data directory: `data/<session_id>/`
    2. Deletes the FAISS index directory: `faiss_index/<session_id>/`
    3. Does NOT delete checkpointer data (conversation history is preserved)
    4. Does NOT delete the session itself
    
    This is useful when users want to clear all documents but keep the conversation history.
    
    Returns:
        DeleteSessionResponse with success status and deleted paths
    """
    deleted_paths = []
    errors = []
    
    try:
        # 1. Delete data directory
        data_dir = Path("data") / session_id
        if data_dir.exists():
            try:
                shutil.rmtree(data_dir)
                deleted_paths.append(str(data_dir))
                log.info("Deleted data directory", session_id=session_id, path=str(data_dir))
            except Exception as e:
                error_msg = f"Failed to delete data directory: {str(e)}"
                errors.append(error_msg)
                log.error(error_msg, session_id=session_id, path=str(data_dir))
        
        # 2. Delete FAISS index directory
        index_dir = Path("faiss_index") / session_id
        if index_dir.exists():
            try:
                shutil.rmtree(index_dir)
                deleted_paths.append(str(index_dir))
                log.info("Deleted FAISS index directory", session_id=session_id, path=str(index_dir))
            except Exception as e:
                error_msg = f"Failed to delete FAISS index directory: {str(e)}"
                errors.append(error_msg)
                log.error(error_msg, session_id=session_id, path=str(index_dir))
        
        # Note: We intentionally do NOT delete checkpointer data (conversation history)
        # The session remains active, just without documents
        
        # Determine response
        if errors:
            # Some deletions failed
            message = f"File deletion completed with errors: {'; '.join(errors)}"
            log.warning("File deletion completed with errors", 
                       session_id=session_id, 
                       errors=errors,
                       deleted_paths=deleted_paths)
            return DeleteSessionResponse(
                success=False,
                message=message,
                deleted_paths=deleted_paths
            )
        elif deleted_paths:
            # All deletions successful
            message = f"All files deleted from session {session_id} (session and conversation history preserved)"
            log.info("All files deleted from session", 
                    session_id=session_id, 
                    deleted_paths=deleted_paths)
            return DeleteSessionResponse(
                success=True,
                message=message,
                deleted_paths=deleted_paths
            )
        else:
            # No files to delete (session exists but has no files)
            message = f"Session {session_id} has no files to delete"
            log.info("No files to delete", session_id=session_id)
            return DeleteSessionResponse(
                success=True,
                message=message,
                deleted_paths=deleted_paths
            )
            
    except Exception as e:
        error_msg = f"Unexpected error during file deletion: {str(e)}"
        log.error(error_msg, session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=error_msg)


@router.delete("/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str):
    """
    Delete a session and all its associated data.
    
    This endpoint:
    1. Deletes the data directory: `data/<session_id>/`
    2. Deletes the FAISS index directory: `faiss_index/<session_id>/`
    3. Deletes checkpointer data (conversation history) from PostgreSQL
    
    Returns:
        DeleteSessionResponse with success status and deleted paths
    """
    deleted_paths = []
    errors = []
    checkpointer_deleted = False
    
    try:
        # 1. Delete data directory
        data_dir = Path("data") / session_id
        if data_dir.exists():
            try:
                shutil.rmtree(data_dir)
                deleted_paths.append(str(data_dir))
                log.info("Deleted data directory", session_id=session_id, path=str(data_dir))
            except Exception as e:
                error_msg = f"Failed to delete data directory: {str(e)}"
                errors.append(error_msg)
                log.error(error_msg, session_id=session_id, path=str(data_dir))
        
        # 2. Delete FAISS index directory
        index_dir = Path("faiss_index") / session_id
        if index_dir.exists():
            try:
                shutil.rmtree(index_dir)
                deleted_paths.append(str(index_dir))
                log.info("Deleted FAISS index directory", session_id=session_id, path=str(index_dir))
            except Exception as e:
                error_msg = f"Failed to delete FAISS index directory: {str(e)}"
                errors.append(error_msg)
                log.error(error_msg, session_id=session_id, path=str(index_dir))
        
        # 3. Delete checkpointer data (conversation history) from PostgreSQL
        try:
            cm = CheckpointerManager()
            checkpointer = await cm.get_checkpointer()
            async with checkpointer as cp:
                # session_id được dùng như thread_id trong checkpointer
                await cp.adelete_thread(session_id)
                checkpointer_deleted = True
                deleted_paths.append(f"checkpointer:thread_{session_id}")
                log.info("Deleted checkpointer thread", session_id=session_id)
        except Exception as e:
            # Checkpointer deletion is optional - log warning but don't fail the request
            # This handles cases where checkpointer is not configured or thread doesn't exist
            error_msg = f"Failed to delete checkpointer thread (non-critical): {str(e)}"
            log.warning(error_msg, session_id=session_id, error=str(e))
            # Don't add to errors list - this is non-critical
        
        # Determine response
        if errors:
            # Some deletions failed
            message = f"Session deletion completed with errors: {'; '.join(errors)}"
            if checkpointer_deleted:
                message += " (Checkpointer deleted)"
            log.warning("Session deletion completed with errors", 
                       session_id=session_id, 
                       errors=errors,
                       deleted_paths=deleted_paths,
                       checkpointer_deleted=checkpointer_deleted)
            return DeleteSessionResponse(
                success=False,
                message=message,
                deleted_paths=deleted_paths
            )
        elif deleted_paths:
            # All deletions successful
            message = f"Session {session_id} deleted successfully"
            if checkpointer_deleted:
                message += " (including conversation history)"
            log.info("Session deleted successfully", 
                    session_id=session_id, 
                    deleted_paths=deleted_paths,
                    checkpointer_deleted=checkpointer_deleted)
            return DeleteSessionResponse(
                success=True,
                message=message,
                deleted_paths=deleted_paths
            )
        else:
            # Session not found (no paths to delete)
            message = f"Session {session_id} not found (no data to delete)"
            log.info("Session not found for deletion", session_id=session_id)
            return DeleteSessionResponse(
                success=True,
                message=message,
                deleted_paths=deleted_paths
            )
            
    except Exception as e:
        error_msg = f"Unexpected error during session deletion: {str(e)}"
        log.error(error_msg, session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=error_msg)


