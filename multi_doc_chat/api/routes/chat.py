from typing import Dict, Any
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse

from multi_doc_chat.src.document_ingestion.data_ingestion import (
    load_session_retriever,
    DocumentIngestor,
)
from multi_doc_chat.src.document_chat.graph_nodes import GraphNodes
from multi_doc_chat.src.document_chat.graph_builder import GraphBuilder
from multi_doc_chat.utils.checkpointer import CheckpointerManager
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.api.schemas import ChatRequest, ChatResponse
from multi_doc_chat.api.dependencies import get_model_loader, get_config


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    model_loader: ModelLoader = Depends(get_model_loader),
    config: dict = Depends(get_config)
):
    session_id = payload.session_id
    message = payload.message.strip()
    if not session_id or not message:
        raise HTTPException(status_code=400, detail="session_id and message are required")

    try:
        retriever = load_session_retriever(session_id=session_id)
        # ✅ Pass shared model_loader and config
        ingestor = DocumentIngestor(model_loader=model_loader, config=config)
        retriever_tool = ingestor.create_retriever_tool(
            retriever,
            tool_name="retrieve_data",
            description="Search and return information about enterprise data from files",
        )

        # ✅ Pass shared model_loader and config to avoid creating new instances
        graph_nodes = GraphNodes(
            retriever_tool, 
            session_id=session_id,
            model_loader=model_loader,
            config=config
        )
        graph_builder = GraphBuilder(
            retriever_tool, 
            graph_nodes,
            model_loader=model_loader,
            config=config
        )
        workflow = graph_builder.build_graph()

        cm = CheckpointerManager()
        checkpointer = await cm.get_checkpointer()

        async def event_generator():
            try:
                async with checkpointer as cp:
                    graph = workflow.compile(checkpointer=cp)
                    config = {"configurable": {"thread_id": session_id}}
                    inputs = {"messages": [{"role": "user", "content": message}]}
                    valid_nodes = ["generate_query_or_respond", "generate_answer"]
                    ignored_tools = ["summarize"]

                    async for msg, metadata in graph.astream(inputs, config=config, stream_mode="messages"):
                        node_name = metadata.get("langgraph_node")
                        
                        # Send status for tool nodes
                        if node_name not in valid_nodes and node_name not in ignored_tools:
                            tool_messages = {
                                "retrieve": "🔍 Đang tìm kiếm thông tin...",
                            }
                            status_msg = tool_messages.get(node_name, "⚙️ Đang xử lý...")
                            # JSON format with type field
                            yield f"data: {json.dumps({'type': 'status', 'content': status_msg}, ensure_ascii=False)}\n\n"
                            continue
                        
                        # Stream tokens directly from LLM - msg.content is already a token/chunk
                        if (
                            msg.content
                            and node_name in valid_nodes
                            and metadata.get("ls_model_type") == "chat"
                        ):
                            # JSON format for tokens with ensure_ascii=False for Vietnamese
                            yield f"data: {json.dumps({'type': 'token', 'content': msg.content}, ensure_ascii=False)}\n\n"
                    
                    # Send done event
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                            
            except Exception as e:
                # JSON format for errors
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        # Generic error handler
        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    model_loader: ModelLoader = Depends(get_model_loader),
    config: dict = Depends(get_config)
):
    """Non-stream chat: collect final assistant content and return."""
    session_id = payload.session_id
    message = payload.message.strip()
    if not session_id or not message:
        raise HTTPException(status_code=400, detail="session_id and message are required")

    try:
        retriever = load_session_retriever(session_id=session_id)
        # ✅ Pass shared model_loader and config
        ingestor = DocumentIngestor(model_loader=model_loader, config=config)
        retriever_tool = ingestor.create_retriever_tool(
            retriever,
            tool_name="retrieve_data",
            description="Search and return information about enterprise data from files",
        )

        # ✅ Pass shared model_loader and config to avoid creating new instances
        graph_nodes = GraphNodes(
            retriever_tool, 
            session_id=session_id,
            model_loader=model_loader,
            config=config
        )
        graph_builder = GraphBuilder(
            retriever_tool, 
            graph_nodes,
            model_loader=model_loader,
            config=config
        )
        workflow = graph_builder.build_graph()

        cm = CheckpointerManager()
        checkpointer = await cm.get_checkpointer()

        final_text_parts = []

        async with checkpointer as cp:
            graph = workflow.compile(checkpointer=cp)
            config = {"configurable": {"thread_id": session_id}}
            inputs = {"messages": [{"role": "user", "content": message}]}
            valid_nodes = ["generate_query_or_respond", "generate_answer"]
            ignored_tools = ["summarize"]

            async for msg, metadata in graph.astream(inputs, config=config, stream_mode="messages"):
                node_name = metadata.get("langgraph_node")
                if getattr(msg, "content", None) and node_name in valid_nodes and metadata.get("ls_model_type") == "chat":
                    final_text_parts.append(str(msg.content))

        answer = "".join(final_text_parts)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


