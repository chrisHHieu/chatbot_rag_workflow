import os
import sys
from typing import Optional
from langchain_openai import OpenAIEmbeddings
from langchain.chat_models import init_chat_model
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.utils.api_key_manager import ApiKeyManager
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import RAGException


class ModelLoader:
    """Loads embedding models and LLMs based on config."""
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize ModelLoader.
        
        Args:
            config: Optional config dict. If None, loads from cache.
        """
        # Initialize API key manager (handles .env loading)
        self.api_key_mgr = ApiKeyManager()
        
        # ✅ Use provided config or load from cache
        self.config = config or load_config()
        log.info("YAML config loaded", config_keys=list(self.config.keys()))

    def load_embeddings(self):
        """Load and return embedding model."""
        try:
            embedding_config = self.config["embedding_model"]
            model_name = embedding_config["model_name"]
            provider = embedding_config.get("provider", "openai")
            
            log.info("Loading embedding model", provider=provider, model=model_name)
            
            if provider == "openai":
                api_key = self.api_key_mgr.get("OPENAI_API_KEY")
                return OpenAIEmbeddings(
                    model=model_name,
                    openai_api_key=api_key
                )
            else:
                raise ValueError(f"Unsupported embedding provider: {provider}")
                
        except Exception as e:
            log.error("Error loading embedding model", error=str(e))
            raise RAGException("Failed to load embedding model", sys)

    def load_response_model(self):
        """Load response LLM model."""
        try:
            llm_config = self.config["llm"]["response"]
            model_name = llm_config["model_name"]
            temperature = llm_config.get("temperature", 0.3)
            
            log.info("Loading response model", model=model_name, temperature=temperature)
            
            # init_chat_model automatically uses OPENAI_API_KEY from environment
            # We ensure it's set via ApiKeyManager
            _ = self.api_key_mgr.get("OPENAI_API_KEY")  # Validate key exists
            return init_chat_model(model_name, temperature=temperature)
            
        except Exception as e:
            log.error("Error loading response model", error=str(e))
            raise RAGException("Failed to load response model", sys)

    def load_grader_model(self):
        """Load grader LLM model (used for summarization)."""
        try:
            llm_config = self.config["llm"]["grader"]
            model_name = llm_config["model_name"]
            temperature = llm_config.get("temperature", 0)
            
            log.info("Loading grader model", model=model_name, temperature=temperature)
            
            # init_chat_model automatically uses OPENAI_API_KEY from environment
            _ = self.api_key_mgr.get("OPENAI_API_KEY")  # Validate key exists
            return init_chat_model(model_name, temperature=temperature)
            
        except Exception as e:
            log.error("Error loading grader model", error=str(e))
            raise RAGException("Failed to load grader model", sys)

