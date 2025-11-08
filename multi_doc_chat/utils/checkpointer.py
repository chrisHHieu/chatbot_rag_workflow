import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.utils.api_key_manager import ApiKeyManager
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import RAGException
import sys


class CheckpointerManager:
    """Manager for Postgres checkpoint setup."""
    
    def __init__(self):
        self.config = load_config()
        # Initialize API key manager (DB_URI is optional, can be in config)
        self.api_key_mgr = ApiKeyManager(required_keys=[])  # DB_URI is optional
        self.db_uri = self._get_db_uri()
    
    def _get_db_uri(self) -> str:
        """Get database URI from config or environment."""
        # Priority: 1) Config file 2) POSTGRES_URI env var 3) DB_URI env var (backward compatible)
        db_config = self.config.get("database", {})
        db_uri = db_config.get("uri")
        
        if not db_uri:
            # Try POSTGRES_URI first (preferred), then DB_URI (backward compatible)
            if self.api_key_mgr.has("POSTGRES_URI"):
                db_uri = self.api_key_mgr.get("POSTGRES_URI")
            elif self.api_key_mgr.has("DB_URI"):
                db_uri = self.api_key_mgr.get("DB_URI")
            else:
                raise RAGException(
                    "Database URI not found in config.yaml or environment variables. "
                    "Please set POSTGRES_URI (or DB_URI) in .env file or config.yaml",
                    sys
                )
        
        return db_uri
    
    async def get_checkpointer(self):
        """Get async Postgres checkpointer context manager."""
        log.info("Initializing Postgres checkpointer", db_uri=self.db_uri[:30] + "...")
        return AsyncPostgresSaver.from_conn_string(self.db_uri)

