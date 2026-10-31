"""
Main entry point for the Hybrid RAG System with LangGraph.

This script demonstrates the complete workflow:
1. Load and process documents
2. Create hybrid retriever (FAISS + BM25)
3. Build LangGraph workflow with summarization
4. Stream responses with persistent memory
"""

import asyncio
import sys
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
            ignored_tools = ["summarize"]  # the summariser is internal, do not print it
            
            async for msg, metadata in graph.astream(
                inputs,
                config=config,
                stream_mode="messages",
            ):
                node_name = metadata.get("langgraph_node")
                
                # Any node that is not an answer node is shown as a status line
                if node_name not in valid_nodes and node_name not in ignored_tools:
                    tool_messages = {
                        "retrieve": "🤖 Searching the documents...",
                    }
                    msg_tool = tool_messages.get(node_name, "🤖 Composing an answer...")
                    print(f"\n{msg_tool}\n", flush=True)
                    continue
                
                # Answer nodes print tokens as they arrive
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
    """Ask one question about one document from the command line."""
    # Usage: python main.py [path.pdf] ["your question"]
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample.pdf")
    question = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "Summarise the main obligations this document places on an employee."
    )
    thread_id = "cli_demo_thread"
    
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        print('Usage: python main.py [path.pdf] ["your question"]')
        return
    
    asyncio.run(stream_response(str(pdf_path), question, thread_id))


if __name__ == "__main__":
    main()

