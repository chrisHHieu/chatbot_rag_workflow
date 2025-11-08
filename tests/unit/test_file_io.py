from pathlib import Path
from multi_doc_chat.utils.file_io import save_uploaded_files


class DummyUpload:
    def __init__(self, path: Path):
        self.filename = path.name
        self._bytes = path.read_bytes()
    def read(self):
        return self._bytes


def test_save_uploaded_files_txt(tmp_path: Path):
    src = tmp_path / "note.txt"
    src.write_text("abc", encoding="utf-8")
    files = [DummyUpload(src)]

    out_dir = tmp_path / "out"
    saved = save_uploaded_files(files, out_dir)
    assert len(saved) == 1
    assert saved[0].exists()
    assert saved[0].suffix == ".txt"


