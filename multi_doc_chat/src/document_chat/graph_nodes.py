from typing import Dict, Optional
from langchain_core.messages import SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from langmem.short_term import RunningSummary
from multi_doc_chat.model.models import State
from multi_doc_chat.prompts.prompt_library import SYSTEM_PROMPT, ANSWER_PROMPT
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from datetime import datetime, timezone, timedelta


def get_current_datetime() -> str:
    """Get current datetime in Vietnam timezone (UTC+7) format."""
    try:
        # Use Vietnam timezone (UTC+7)
        vietnam_tz = timezone(timedelta(hours=7))
        current_dt = datetime.now(vietnam_tz)
        # Format: "Monday, 15 January 2025, 14:30:45 (UTC+7)"
        current_datetime = current_dt.strftime("%A, %d %B %Y, %H:%M:%S") + " (UTC+7)"
        return current_datetime
    except Exception:
        # Fallback if timezone not available
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class GraphNodes:
    """LangGraph nodes for the RAG workflow."""
    
    def __init__(
        self, 
        retriever_tool, 
        session_id: Optional[str] = None,
        model_loader: Optional[ModelLoader] = None,
        config: Optional[dict] = None
    ):
        """
        Initialize GraphNodes.
        
        Args:
            retriever_tool: Retriever tool for document search
            session_id: Optional session ID for file info injection
            model_loader: Optional shared ModelLoader instance
            config: Optional config dict
        """
        self.model_loader = model_loader or ModelLoader(config=config)
        self.config = config or load_config()
        self.response_model = self.model_loader.load_response_model()
        self.retriever_tool = retriever_tool
        self.session_id = session_id  # ✅ Store session_id for file info
        
        # Bind tools to response model
        self.response_model_with_tools = self.response_model.bind_tools([retriever_tool])
        log.info("GraphNodes initialized", session_id=session_id)
    
    def generate_query_or_respond(self, state: State) -> Dict:
        """
        Node chính: Quyết định gọi retriever hoặc trả lời trực tiếp.
        Tự động inject conversation summary và file info vào context.
        Note: Không dùng trim_messages vì SummarizationNode đã quản lý token limit.
        """
        try:
            messages = state["messages"]
            
            # Get current datetime
            current_datetime = get_current_datetime()
            
            # ✅ Get file info for this session
            available_files_info = "No documents available."
            if self.session_id:
                try:
                    from multi_doc_chat.utils.file_utils import get_session_files_info_with_preview
                    available_files_info = get_session_files_info_with_preview(self.session_id)
                except Exception as e:
                    log.warning("Failed to get session files info", error=str(e), session_id=self.session_id)
            
            # Format SYSTEM_PROMPT with datetime and file info
            formatted_system_prompt = SYSTEM_PROMPT.format(
                current_datetime=current_datetime,
                available_files=available_files_info  # ✅ Inject file info
            )
            system_message = SystemMessage(content=formatted_system_prompt)
            
            # Thêm conversation summary để model hiểu ngữ cảnh
            context_summary = state.get("context", {}).get("running_summary")
            summary_content = ""
            if context_summary and context_summary.summary:
                summary_content = (
                    f"Previous conversation summary: {context_summary.summary}\n\n"
                    "Use this context to understand follow-up questions and references to previous topics."
                )
            
            # ✅ BỎ TRIM: SummarizationNode đã quản lý token limit (max_tokens_total: 100000)
            # Dùng toàn bộ messages - summarization sẽ tự động tóm tắt khi cần
            
            # PREPEND SYSTEM MESSAGE + SUMMARY (nếu có) VÀO MESSAGES
            enhanced_messages = [system_message]
            if summary_content:
                enhanced_messages.append({"role": "system", "content": summary_content})
            enhanced_messages.extend(messages)  # ✅ Dùng messages gốc, không trim
            
            # Model tự quyết định: gọi tool hoặc trả lời trực tiếp
            response = self.response_model_with_tools.invoke(enhanced_messages)
            # Log tool call vs direct answer decision
            try:
                tool_calls = getattr(response, "tool_calls", None)
                decision = "tool" if tool_calls else "direct_answer"
                log.info("Decision made", decision=decision)
            except Exception:
                pass
            return {"messages": [response]}
            
        except Exception as e:
            log.error("Error in generate_query_or_respond", error=str(e))
            raise
    
    def generate_answer(self, state: State) -> Dict:
        """
        Tạo câu trả lời từ retrieved context.
        LLM tự đánh giá context có đủ thông tin hay không.
        """
        try:
            # Lấy câu hỏi cuối cùng từ user
            user_messages = [m for m in state["messages"] if m.type == "human"]
            if not user_messages:
                return {"messages": [{"role": "assistant", "content": "Tôi cần một câu hỏi để trả lời."}]}
            
            question = user_messages[-1].content
            
            # Lấy context từ tool message cuối cùng
            tool_messages = [m for m in state["messages"] if m.type == "tool"]
            if not tool_messages:
                return {"messages": [{"role": "assistant", "content": "Xin lỗi, tôi không tìm thấy thông tin liên quan."}]}
            
            context = tool_messages[-1].content
            
            # Get current datetime
            current_datetime = get_current_datetime()
            
            # ✅ Get file info for answer generation too
            available_files_info = "No documents available."
            if self.session_id:
                try:
                    from multi_doc_chat.utils.file_utils import get_session_files_info_with_preview
                    available_files_info = get_session_files_info_with_preview(self.session_id)
                except Exception as e:
                    log.warning("Failed to get session files info in generate_answer", error=str(e), session_id=self.session_id)
            
            # Format SYSTEM_PROMPT with datetime and file info
            formatted_system_prompt = SYSTEM_PROMPT.format(
                current_datetime=current_datetime,
                available_files=available_files_info  # ✅ Inject file info
            )
            system_message = SystemMessage(content=formatted_system_prompt)
            
            # LLM tự đánh giá và trả lời
            # Note: current_datetime is now in SYSTEM_PROMPT, not ANSWER_PROMPT
            prompt = ANSWER_PROMPT.format(
                question=question, 
                context=context
            )
            
            # Include system message with temporal context for answer generation
            response = self.response_model.invoke([
                system_message,
                {"role": "user", "content": prompt}
            ])
            log.info("Answer generated")
            
            return {"messages": [response]}
            
        except Exception as e:
            log.error("Error in generate_answer", error=str(e))
            raise

