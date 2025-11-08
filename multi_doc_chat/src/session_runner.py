import asyncio
import argparse
from pathlib import Path
from typing import Iterable, Dict, List

from multi_doc_chat.src.document_ingestion.data_ingestion import (
    ChatIngestor,
    load_session_retriever,
    DocumentIngestor,
)
from multi_doc_chat.src.document_chat.graph_nodes import GraphNodes
from multi_doc_chat.src.document_chat.graph_builder import GraphBuilder
from multi_doc_chat.utils.checkpointer import CheckpointerManager
from multi_doc_chat.logger import GLOBAL_LOGGER as log


async def _stream_graph_response(retriever, question: str, thread_id: str, *, use_checkpointer: bool = True):
    """Compile LangGraph with the given retriever and stream response for a single turn."""
    try:
        log.info("Session graph run start", thread_id=thread_id)
        # Create tool from retriever using existing ingestor API
        ingestor = DocumentIngestor()
        retriever_tool = ingestor.create_retriever_tool(
            retriever,
            tool_name="retrieve_data",
            description="Search and return information about enterprise data from files",
        )

        graph_nodes = GraphNodes(retriever_tool)
        graph_builder = GraphBuilder(retriever_tool, graph_nodes)
        workflow = graph_builder.build_graph()

        if use_checkpointer:
            checkpointer_manager = CheckpointerManager()
            checkpointer = await checkpointer_manager.get_checkpointer()

            async with checkpointer as cp:
                log.info("Compiling workflow with checkpointer", thread_id=thread_id)
                graph = workflow.compile(checkpointer=cp)
                config: Dict[str, Dict[str, str]] = {"configurable": {"thread_id": thread_id}}

                inputs = {
                    "messages": [
                        {
                            "role": "user",
                            "content": question,
                        }
                    ]
                }

                valid_nodes = ["generate_query_or_respond", "generate_answer"]
                ignored_tools = ["summarize"]

                async for msg, metadata in graph.astream(
                    inputs,
                    config=config,
                    stream_mode="messages",
                ):
                    node_name = metadata.get("langgraph_node")

                    if node_name not in valid_nodes and node_name not in ignored_tools:
                        tool_messages = {
                            "retrieve": "\n🤖 Đang tìm kiếm thông tin...\n",
                        }
                        print(tool_messages.get(node_name, "\n🤖 Đang tổng hợp thông tin...\n"), flush=True)
                        continue

                    if (
                        getattr(msg, "content", None)
                        and node_name in valid_nodes
                        and metadata.get("ls_model_type") == "chat"
                    ):
                        print(msg.content, end="", flush=True)
        else:
            # Compile without checkpointer (no persistent memory), for offline tests
            log.info("Compiling workflow without checkpointer (test mode)", thread_id=thread_id)
            graph = workflow.compile()
            config = {}
            inputs = {
                "messages": [
                    {
                        "role": "user",
                        "content": question,
                    }
                ]
            }
            valid_nodes = ["generate_query_or_respond", "generate_answer"]
            ignored_tools = ["summarize"]
            async for msg, metadata in graph.astream(
                inputs,
                config=config,
                stream_mode="messages",
            ):
                node_name = metadata.get("langgraph_node")
                if node_name not in valid_nodes and node_name not in ignored_tools:
                    tool_messages = {"retrieve": "\n🤖 Đang tìm kiếm thông tin...\n"}
                    print(tool_messages.get(node_name, "\n🤖 Đang tổng hợp thông tin...\n"), flush=True)
                    continue
                if (
                    getattr(msg, "content", None)
                    and node_name in valid_nodes
                    and metadata.get("ls_model_type") == "chat"
                ):
                    print(msg.content, end="", flush=True)

        log.info("Session graph run completed", thread_id=thread_id)
    except Exception as e:
        log.error("Session graph run failed", error=str(e), thread_id=thread_id)
        raise


async def run_chat_with_new_upload(
    uploaded_files: Iterable,
    question: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    k: int = 5,
    search_type: str = "mmr",
    fetch_k: int = 20,
    lambda_mult: float = 0.5,
    use_checkpointer: bool = True,
):
    """Case A: Create a new session from uploaded files, then run graph.

    Uses a single conversation per session: thread_id == session_id.
    """
    ci = ChatIngestor(use_session_dirs=True)
    session_id = ci.session_id

    retriever = ci.build_retriever(
        uploaded_files,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        k=k,
        search_type=search_type,
        fetch_k=fetch_k,
        lambda_mult=lambda_mult,
    )

    await _stream_graph_response(retriever, question, thread_id=session_id, use_checkpointer=use_checkpointer)
    return session_id


async def run_chat_resume_session(
    session_id: str,
    question: str,
    *,
    k: int = 5,
    search_type: str = "mmr",
    fetch_k: int = 20,
    lambda_mult: float = 0.5,
    use_checkpointer: bool = True,
):
    """Case B: Resume chat for an existing session, loading retriever from FAISS.

    Uses a single conversation per session: thread_id == session_id.
    """
    log.info("Resume session requested", session_id=session_id)
    retriever = load_session_retriever(
        session_id=session_id,
        k=k,
        search_type=search_type,
        fetch_k=fetch_k,
        lambda_mult=lambda_mult,
    )

    await _stream_graph_response(retriever, question, thread_id=session_id, use_checkpointer=use_checkpointer)

def _build_local_file_adapters(paths: List[str]):
    class LocalFileAdapter:
        def __init__(self, file_path: str):
            p = Path(file_path)
            self.filename = p.name
            self._bytes = p.read_bytes()
        def read(self):
            return self._bytes
    return [LocalFileAdapter(p) for p in paths]


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run LangGraph chat (new session from uploads or resume by session_id)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create new session from uploaded files and chat")
    p_new.add_argument("question", type=str, help="User question to ask")
    p_new.add_argument("files", nargs="+", help="One or more file paths (.pdf/.docx/.txt)")
    p_new.add_argument("--k", type=int, default=5)
    p_new.add_argument("--chunk-size", type=int, default=1000)
    p_new.add_argument("--chunk-overlap", type=int, default=200)
    p_new.add_argument("--search-type", type=str, default="mmr", choices=["mmr", "similarity", "similarity_score_threshold"])
    p_new.add_argument("--fetch-k", type=int, default=20)
    p_new.add_argument("--lambda-mult", type=float, default=0.5)

    p_resume = sub.add_parser("resume", help="Resume chat using existing session_id")
    p_resume.add_argument("session_id", type=str, help="Existing session id")
    p_resume.add_argument("question", type=str, help="User question to ask")
    p_resume.add_argument("--k", type=int, default=5)
    p_resume.add_argument("--search-type", type=str, default="mmr", choices=["mmr", "similarity", "similarity_score_threshold"])
    p_resume.add_argument("--fetch-k", type=int, default=20)
    p_resume.add_argument("--lambda-mult", type=float, default=0.5)

    return parser.parse_args()


def main():
    args = _parse_args()
    if args.command == "new":
        files = _build_local_file_adapters(args.files)
        session_id = asyncio.run(
            run_chat_with_new_upload(
                files,
                args.question,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                k=args.k,
                search_type=args.search_type,
                fetch_k=args.fetch_k,
                lambda_mult=args.lambda_mult,
            )
        )
        print(f"\n\nCreated session_id: {session_id}")
    elif args.command == "resume":
        asyncio.run(
            run_chat_resume_session(
                session_id=args.session_id,
                question=args.question,
                k=args.k,
                search_type=args.search_type,
                fetch_k=args.fetch_k,
                lambda_mult=args.lambda_mult,
            )
        )


if __name__ == "__main__":
    main()


