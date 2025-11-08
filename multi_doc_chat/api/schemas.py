from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class UploadResponse(BaseModel):
    session_id: str
    indexed: bool = True
    message: Optional[str] = None
    questions: Optional[List[str]] = None  # Sample questions generated from documents


class IngestResponse(BaseModel):
    session_id: str
    indexed: bool = True
    message: Optional[str] = None
    questions: Optional[List[str]] = None  # Sample questions generated from documents


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str = Field(min_length=1)


class SessionStatus(BaseModel):
    exists: bool
    data_path: str
    index_path: str
    docs_count: Optional[int] = None


class HealthDb(BaseModel):
    ok: bool
    error: Optional[str] = None


class ConfigSummary(BaseModel):
    embedding_model: Dict[str, Any]
    hybrid_retriever: Dict[str, Any]
    text_splitter: Dict[str, Any]
    llm: Dict[str, Any]
    summarization: Dict[str, Any]
    message_trimming: Dict[str, Any]


class SampleQuestionsResponse(BaseModel):
    questions: List[str] = Field(description="List of sample questions based on document content")


class DeleteSessionResponse(BaseModel):
    success: bool
    message: str
    deleted_paths: List[str] = Field(default_factory=list, description="List of deleted paths")


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list, description="List of conversation messages")
    total_messages: int = 0


