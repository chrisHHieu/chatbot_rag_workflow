from pathlib import Path
import os
import yaml
import threading
from typing import Optional, Dict
from multi_doc_chat.logger import GLOBAL_LOGGER as log

# Thread-safe cache
_config_cache: Optional[Dict] = None
_config_lock = threading.Lock()
_config_path: Optional[str] = None


def _project_root() -> Path:
    """Get project root directory."""
    root = Path(__file__).resolve().parents[1]
    log.debug("Project root resolved", root=str(root), config_loader_file=__file__)
    return root


def load_config(config_path: str | None = None, force_reload: bool = False) -> dict:
    """
    Load configuration from YAML file with thread-safe caching.
    
    Priority: explicit arg > CONFIG_PATH env > <project_root>/config/config.yaml
    
    Args:
        config_path: Optional path to config file
        force_reload: If True, force reload from file (useful for hot reload)
    
    Returns:
        Dict containing configuration
    """
    global _config_cache, _config_path
    
    # Determine config path
    if config_path is None:
        env_path = os.getenv("CONFIG_PATH")
        if env_path:
            log.info("Using CONFIG_PATH from environment", path=env_path)
            config_path = env_path
        else:
            project_root = _project_root()
            config_path = str(project_root / "config" / "config.yaml")
            log.info("Using default config path", project_root=str(project_root), config_path=config_path)
    
    path = Path(config_path)
    if not path.is_absolute():
        project_root = _project_root()
        path = project_root / path
        log.debug("Resolved relative config path", relative_path=config_path, absolute_path=str(path))
    
    if not path.exists():
        error_msg = f"Config file not found: {path}"
        log.error(
            "Config file not found",
            config_path=str(path),
            exists=path.exists(),
            parent_exists=path.parent.exists() if path.parent else False,
            cwd=os.getcwd(),
            project_root=str(_project_root())
        )
        raise FileNotFoundError(error_msg)
    
    log.debug("Config file found", config_path=str(path), exists=path.exists())
    
    # Thread-safe caching
    with _config_lock:
        # Check if cache is valid
        if (
            _config_cache is not None
            and _config_path == str(path)
            and not force_reload
        ):
            return _config_cache
        
        # Load config from file
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        # Update cache
        _config_cache = config
        _config_path = str(path)
        
        return config


def reload_config():
    """Clear config cache to force reload on next call."""
    global _config_cache
    with _config_lock:
        _config_cache = None

