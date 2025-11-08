from __future__ import annotations
import re
import uuid
import json
from pathlib import Path
from typing import Iterable, List, Dict
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import RAGException


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def load_filename_mapping(target_dir: Path) -> Dict[str, str]:
    """Load filename mapping (saved_name -> original_name) from JSON file."""
    mapping_file = target_dir / "filename_mapping.json"
    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load filename mapping", error=str(e))
    return {}


def save_filename_mapping(target_dir: Path, mapping: Dict[str, str]):
    """Save filename mapping (saved_name -> original_name) to JSON file."""
    mapping_file = target_dir / "filename_mapping.json"
    try:
        # Load existing mapping and merge
        existing = load_filename_mapping(target_dir)
        existing.update(mapping)
        
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("Failed to save filename mapping", error=str(e))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe while preserving Vietnamese characters.
    
    Only replaces dangerous filesystem characters, keeps Vietnamese accents.
    Spaces are replaced with underscores for better URL compatibility.
    """
    # Get stem and extension
    path = Path(filename)
    stem = path.stem
    ext = path.suffix.lower()
    
    # Replace only dangerous filesystem characters: / \ : * ? " < > |
    # Keep Vietnamese characters (ă, â, ê, ô, ơ, ư, đ, etc.)
    dangerous_chars = r'[/\\:*?"<>|]'
    safe_stem = re.sub(dangerous_chars, '_', stem)
    
    # Replace spaces with underscores for better URL compatibility
    safe_stem = safe_stem.replace(' ', '_')
    
    # Replace multiple consecutive underscores with single underscore
    safe_stem = re.sub(r'_+', '_', safe_stem)
    
    # Trim underscores from start and end
    safe_stem = safe_stem.strip('_')
    
    # If empty after sanitization, use default name
    if not safe_stem:
        safe_stem = "file"
    
    # Add UUID suffix to ensure uniqueness (before extension)
    unique_id = uuid.uuid4().hex[:8]
    fname = f"{safe_stem}_{unique_id}{ext}"
    
    return fname


def save_uploaded_files(uploaded_files: Iterable, target_dir: Path) -> List[Path]:
    """Save uploaded files and return local paths.

    Supports FastAPI's UploadFile (has .filename and .file), generic objects with .name,
    or objects exposing a getbuffer() method returning bytes-like.
    
    Also saves a mapping of saved_name -> original_name to filename_mapping.json.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        saved: List[Path] = []
        filename_mapping: Dict[str, str] = {}

        for uf in uploaded_files:
            # Derive an original name if possible
            original_name = getattr(uf, "filename", getattr(uf, "name", "file"))
            ext = Path(original_name).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                log.warning("Unsupported file skipped", filename=original_name)
                continue

            # Sanitize filename while preserving Vietnamese characters
            saved_name = sanitize_filename(original_name)
            out_path = target_dir / saved_name
            
            # Store mapping: saved_name -> original_name
            filename_mapping[saved_name] = original_name

            # Write bytes
            with open(out_path, "wb") as f:
                if hasattr(uf, "file") and hasattr(uf.file, "read"):
                    f.write(uf.file.read())
                elif hasattr(uf, "read"):
                    data = uf.read()
                    if isinstance(data, memoryview):
                        data = data.tobytes()
                    f.write(data)
                else:
                    buf = getattr(uf, "getbuffer", None)
                    if callable(buf):
                        data = buf()
                        if isinstance(data, memoryview):
                            data = data.tobytes()
                        f.write(data)
                    else:
                        raise ValueError("Unsupported uploaded file object; no readable interface")

            saved.append(out_path)
            log.info("File saved for ingestion", uploaded=original_name, saved_as=str(out_path))

        # Save filename mapping to JSON file
        if filename_mapping:
            save_filename_mapping(target_dir, filename_mapping)

        return saved
    except Exception as e:
        log.error("Failed to save uploaded files", error=str(e), dir=str(target_dir))
        raise RAGException("Failed to save uploaded files", e)


