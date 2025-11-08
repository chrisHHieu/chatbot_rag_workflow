from pathlib import Path
from multi_doc_chat.utils.document_ops import load_documents


def test_load_text_document(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world", encoding="utf-8")
    docs = load_documents([f])
    assert len(docs) == 1
    assert "hello world" in docs[0].page_content


