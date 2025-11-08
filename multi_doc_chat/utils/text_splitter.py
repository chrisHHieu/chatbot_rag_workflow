"""
Text splitter utilities with tiktoken support for accurate token counting.
"""
from tiktoken import get_encoding
from typing import Callable, Optional
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log


def get_tiktoken_length_function(model_name: Optional[str] = None) -> Callable[[str], int]:
    """
    Get tiktoken length function for accurate token counting.
    
    Args:
        model_name: OpenAI model name. If None, loads response model from config.
                   Uses response model (gpt-4.1-mini) by default since chunks will be
                   processed by LLM, not just embedded.
        
    Returns:
        Length function that counts tokens instead of characters
    """
    if model_name is None:
        config = load_config()
        # Use response model encoding since chunks will be processed by LLM
        model_name = config["llm"]["response"]["model_name"]
    
    # Map OpenAI models to tiktoken encodings
    encoding_map = {
        "text-embedding-3-large": "cl100k_base",
        "text-embedding-3-small": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        "gpt-4o-mini": "o200k_base",
        "gpt-4.1-mini": "o200k_base",  # ✅ Updated: gpt-4.1-mini uses o200k_base
        "gpt-3.5-turbo": "cl100k_base",
    }
    
    encoding_name = encoding_map.get(model_name, "cl100k_base")
    
    try:
        encoding = get_encoding(encoding_name)
        log.info("Tiktoken encoding loaded", model=model_name, encoding=encoding_name)
    except Exception as e:
        log.warning("Failed to load tiktoken encoding, falling back to cl100k_base", error=str(e))
        encoding = get_encoding("cl100k_base")
    
    def tiktoken_len(text: str) -> int:
        """Count tokens in text using tiktoken."""
        return len(encoding.encode(text))
    
    return tiktoken_len


def get_length_function(use_tiktoken: bool = True) -> Callable[[str], int]:
    """
    Get length function (tiktoken or len) based on config.
    
    Args:
        use_tiktoken: Whether to use tiktoken. If False, uses len().
        
    Returns:
        Length function
    """
    if use_tiktoken:
        return get_tiktoken_length_function()
    else:
        return len

