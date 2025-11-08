from fastapi import APIRouter, HTTPException
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.api.schemas import ConfigSummary
from multi_doc_chat.logger import GLOBAL_LOGGER as log


router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigSummary)
def get_config():
    """Get configuration summary (sanitized, no secrets)."""
    try:
        cfg = load_config()
        log.debug("Config loaded successfully", config_keys=list(cfg.keys()))
        
        # Return a curated subset to avoid leaking secrets
        result = ConfigSummary(
            embedding_model=cfg.get("embedding_model", {}),
            hybrid_retriever=cfg.get("hybrid_retriever", {}),
            text_splitter=cfg.get("text_splitter", {}),
            llm={
                "response": cfg.get("llm", {}).get("response"),
                "grader": cfg.get("llm", {}).get("grader"),
            },
            summarization=cfg.get("summarization", {}),
            message_trimming=cfg.get("message_trimming", {}),
        )
        return result
    except FileNotFoundError as e:
        log.error("Config file not found", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Configuration file not found: {str(e)}. Please check CONFIG_PATH environment variable or ensure config.yaml exists."
        )
    except Exception as e:
        log.error("Failed to load config", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration: {str(e)}"
        )


@router.get("/path")
def get_config_path():
    """Get the resolved config file path (for debugging)."""
    import os
    from pathlib import Path
    from multi_doc_chat.utils.config_loader import _project_root
    
    env_path = os.getenv("CONFIG_PATH")
    project_root = _project_root()
    default_path = project_root / "config" / "config.yaml"
    
    config_path = env_path or str(default_path)
    path = Path(config_path)
    if not path.is_absolute():
        path = project_root / path
    
    return {
        "config_path": str(path),
        "exists": path.exists(),
        "env_config_path": env_path,
        "default_path": str(default_path),
        "project_root": str(project_root),
        "cwd": os.getcwd()
    }


