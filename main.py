"""
Main entry point for the Hybrid RAG System with LangGraph.

This script demonstrates the complete workflow:
1. Load and process documents
2. Create hybrid retriever (FAISS + BM25)
3. Build LangGraph workflow with summarization
4. Stream responses with persistent memory
"""

import asyncio
from pathlib import Path
from multi_doc_chat.src.document_ingestion.data_ingestion import DocumentIngestor
from multi_doc_chat.src.document_chat.graph_nodes import GraphNodes
from multi_doc_chat.src.document_chat.graph_builder import GraphBuilder
from multi_doc_chat.utils.checkpointer import CheckpointerManager
from multi_doc_chat.logger import GLOBAL_LOGGER as log


async def stream_response(pdf_path: str, question: str, thread_id: str = "default_thread"):
    """
    Main async function to process query through the RAG system.
    
    Args:
        pdf_path: Path to PDF file
        question: User question
        thread_id: Thread ID for conversation persistence
    """
    try:
        log.info("Starting RAG workflow", pdf_path=pdf_path, thread_id=thread_id)
        
        # 1. Document Ingestion
        ingestor = DocumentIngestor()
        docs = ingestor.load_documents(pdf_path)
        doc_splits = ingestor.split_documents(docs)
        log.info(f"📄 Loaded {len(doc_splits)} document chunks")
        
        # 2. Create Hybrid Retriever
        hybrid_retriever = ingestor.create_hybrid_retriever(doc_splits)
        retriever_tool = ingestor.create_retriever_tool(
            hybrid_retriever,
            tool_name="retrieve_data",
            description="Search and return information about enterprise data from files"
        )
        
        # 3. Build Graph Nodes
        graph_nodes = GraphNodes(retriever_tool)
        
        # 4. Build Graph Workflow
        graph_builder = GraphBuilder(retriever_tool, graph_nodes)
        workflow = graph_builder.build_graph()
        
        # 5. Setup Checkpointer and Compile Graph
        checkpointer_manager = CheckpointerManager()
        checkpointer = await checkpointer_manager.get_checkpointer()
        async with checkpointer as cp:
            graph = workflow.compile(checkpointer=cp)
            config = {"configurable": {"thread_id": thread_id}}
            
            # Prepare inputs
            inputs = {
                "messages": [
                    {
                        "role": "user",
                        "content": question,
                    }
                ]
            }
            
            # Stream response
            valid_nodes = ["generate_query_or_respond", "generate_answer"]
            ignored_tools = ["summarize"]  # không hiển thị summarizer
            
            async for msg, metadata in graph.astream(
                inputs,
                config=config,
                stream_mode="messages",
            ):
                node_name = metadata.get("langgraph_node")
                
                # 🔹 Nếu node là tool nhưng không bị ignore -> hiển thị trạng thái
                if node_name not in valid_nodes and node_name not in ignored_tools:
                    tool_messages = {
                        "retrieve": "🤖 Đang tìm kiếm thông tin...",
                    }
                    msg_tool = tool_messages.get(node_name, "🤖 Đang tổng hợp thông tin...")
                    print(f"\n{msg_tool}\n", flush=True)
                    continue
                
                # 🔹 Nếu là node sinh ra nội dung chat thì in bình thường
                if (
                    msg.content
                    and node_name in valid_nodes
                    and metadata.get("ls_model_type") == "chat"
                ):
                    print(msg.content, end="", flush=True)
        
        log.info("RAG workflow completed successfully")
        
    except Exception as e:
        log.error("RAG workflow failed", error=str(e))
        raise


def main():
    """Main function."""
    # Configuration
    pdf_path = "OOS_Nội quy lao động_2025_Final.pdf"
    question = "THỜI GIAN ĐI LÀM ở công ty OOS TỪ MẤY GIỜ ĐẾN MẤY GIỜ, CHI TIẾT NHẤT"
    thread_id = "some_thread_id_1"
    
    # Check if PDF exists
    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        print("Please ensure the PDF file exists in the current directory.")
        return
    
    # Run async workflow
    asyncio.run(stream_response(pdf_path, question, thread_id))


if __name__ == "__main__":
    main()

