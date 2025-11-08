import asyncio
from pathlib import Path
from typing import List

import pytest
from langchain_core.embeddings import Embeddings

from multi_doc_chat.src.session_runner import run_chat_with_new_upload, run_chat_resume_session


class DummyEmbeddings(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[float(len(t))] for t in texts]
    def embed_query(self, text: str) -> List[float]:
        return [float(len(text))]


@pytest.mark.skip(reason="Requires OpenAI and Postgres unless monkeypatched. Enable when env is set.")
def test_end_to_end_requires_env():
    assert True


def test_new_and_resume_with_monkeypatch(monkeypatch, tmp_path: Path):
    # Monkeypatch ModelLoader used internally to return DummyEmbeddings
    import multi_doc_chat.src.document_ingestion.data_ingestion as di
    class DummyModelLoader:
        def load_embeddings(self):
            return DummyEmbeddings()
    monkeypatch.setattr(di, "ModelLoader", DummyModelLoader)

    # Monkeypatch CheckpointerManager to bypass Postgres (use a no-op async context manager)
    import types
    from multi_doc_chat.utils import checkpointer as cp_mod

    class DummyAsyncContext:
        async def __aenter__(self):
            class Dummy:
                pass
            return Dummy()
        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def dummy_get_checkpointer(self):
        return DummyAsyncContext()

    monkeypatch.setattr(cp_mod.CheckpointerManager, "get_checkpointer", dummy_get_checkpointer)

    # Prepare upload
    src = tmp_path / "doc.txt"
    src.write_text("quick brown fox", encoding="utf-8")

    class LocalFile:
        def __init__(self, p: Path):
            self.filename = p.name
            self._bytes = p.read_bytes()
        def read(self):
            return self._bytes

    files = [LocalFile(src)]

    # Run new session (should stream; we don't assert output text here)
    session_id = asyncio.run(run_chat_with_new_upload(files, "What is in the doc?", chunk_size=50, chunk_overlap=0, k=2, use_checkpointer=False))
    assert isinstance(session_id, str) and session_id

    # Resume
    asyncio.run(run_chat_resume_session(session_id, "Repeat the question", k=2, use_checkpointer=False))


