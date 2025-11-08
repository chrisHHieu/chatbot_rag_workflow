from pathlib import Path
from typing import List
from langchain_core.embeddings import Embeddings
from multi_doc_chat.src.document_ingestion.data_ingestion import ChatIngestor, FaissManager


class DummyEmbeddings(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[float(len(t))] for t in texts]
    def embed_query(self, text: str) -> List[float]:
        return [float(len(text))]


def test_faiss_manager_load_create_and_add(monkeypatch, tmp_path: Path):
    # Monkeypatch ModelLoader within FaissManager to return DummyEmbeddings
    import multi_doc_chat.src.document_ingestion.data_ingestion as di

    class DummyModelLoader:
        def load_embeddings(self):
            return DummyEmbeddings()

    monkeypatch.setattr(di, "ModelLoader", DummyModelLoader)

    idx_dir = tmp_path / "faiss"
    fm = FaissManager(idx_dir)

    # Create new vs from texts
    vs = fm.load_or_create(texts=["hello", "world"], metadatas=[{}, {}])
    assert vs is not None

    # Add idempotent documents
    from langchain_core.documents import Document
    docs = [Document(page_content="hello", metadata={}), Document(page_content="new", metadata={})]
    added = fm.add_documents(docs)
    assert added >= 1


def test_chat_ingestor_build_retriever(monkeypatch, tmp_path: Path):
    # Monkeypatch ModelLoader in ChatIngestor path
    import multi_doc_chat.src.document_ingestion.data_ingestion as di

    class DummyModelLoader:
        def load_embeddings(self):
            return DummyEmbeddings()

    monkeypatch.setattr(di, "ModelLoader", DummyModelLoader)

    # Prepare a small text file as upload
    src = tmp_path / "doc.txt"
    src.write_text("small text for testing", encoding="utf-8")

    class LocalFile:
        def __init__(self, p: Path):
            self.filename = p.name
            self._bytes = p.read_bytes()
        def read(self):
            return self._bytes

    ci = ChatIngestor(temp_base=str(tmp_path / "data"), faiss_base=str(tmp_path / "faiss"), use_session_dirs=True)
    retriever = ci.build_retriever([LocalFile(src)], chunk_size=50, chunk_overlap=0, k=2)
    assert retriever is not None


