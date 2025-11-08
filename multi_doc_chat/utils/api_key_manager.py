import os
import sys
import json
from typing import Optional
from dotenv import load_dotenv
from multi_doc_chat.logger import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import RAGException


class ApiKeyManager:
    """Manages API keys and secrets from environment variables."""
    
    # Required keys for the system
    REQUIRED_KEYS = {
        "openai": ["OPENAI_API_KEY"],
        "database": ["POSTGRES_URI", "DB_URI"],  # POSTGRES_URI preferred, DB_URI for backward compatibility
    }
    
    def __init__(self, required_keys: Optional[list] = None):
        """
        Initialize API key manager.
        
        Args:
            required_keys: List of required key names. If None, uses default REQUIRED_KEYS.
        """
        self.api_keys = {}
        
        # Load .env file if in local mode
        if os.getenv("ENV", "local").lower() != "production":
            load_dotenv()
            log.info("Running in LOCAL mode: .env loaded")
        else:
            log.info("Running in PRODUCTION mode: using environment variables")
        
        # Try to load from JSON secret (for cloud deployments like ECS)
        self._load_from_json_secret()
        
        # Load individual environment variables
        self._load_from_env()
        
        # Validate required keys
        if required_keys:
            self._validate_keys(required_keys)
        else:
            self._validate_default_keys()
        
        # Log loaded keys (masked for security)
        masked_keys = {k: v[:6] + "..." if v else "NOT_SET" for k, v in self.api_keys.items()}
        log.info("API keys loaded", keys=masked_keys)
    
    def _load_from_json_secret(self):
        """Load API keys from JSON secret (for cloud deployments)."""
        raw = os.getenv("API_KEYS_JSON")
        if raw:
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("API_KEYS_JSON is not a valid JSON object")
                self.api_keys.update(parsed)
                # Set in environment for langchain to use
                for key, value in parsed.items():
                    if value:
                        os.environ[key] = value
                log.info("Loaded API keys from JSON secret")
            except Exception as e:
                log.warning("Failed to parse API_KEYS_JSON", error=str(e))
    
    def _load_from_env(self):
        """Load API keys from individual environment variables."""
        # OpenAI keys
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.api_keys["OPENAI_API_KEY"] = openai_key
            # Ensure it's set in environment for langchain to use
            os.environ["OPENAI_API_KEY"] = openai_key
        
        # Database URI - check POSTGRES_URI first (preferred), then DB_URI
        postgres_uri = os.getenv("POSTGRES_URI")
        if postgres_uri:
            self.api_keys["POSTGRES_URI"] = postgres_uri
            # Also set as DB_URI for backward compatibility
            self.api_keys["DB_URI"] = postgres_uri
        
        db_uri = os.getenv("DB_URI")
        if db_uri and "POSTGRES_URI" not in self.api_keys:
            self.api_keys["DB_URI"] = db_uri
        
        # Alternative: Build DB_URI from individual components
        if "POSTGRES_URI" not in self.api_keys and "DB_URI" not in self.api_keys:
            db_host = os.getenv("DB_HOST")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            
            if all([db_host, db_name, db_user, db_password]):
                db_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=disable"
                self.api_keys["POSTGRES_URI"] = db_uri
                self.api_keys["DB_URI"] = db_uri  # Also set for backward compatibility
                log.info("Built POSTGRES_URI from individual components")
        
        # LangSmith configuration (optional)
        langsmith_tracing = os.getenv("LANGSMITH_TRACING", "false")
        if langsmith_tracing.lower() == "true":
            self.api_keys["LANGSMITH_TRACING"] = "true"
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
        
        langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT")
        if langsmith_endpoint:
            self.api_keys["LANGSMITH_ENDPOINT"] = langsmith_endpoint
            os.environ["LANGCHAIN_ENDPOINT"] = langsmith_endpoint
        
        langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
        if langsmith_api_key:
            self.api_keys["LANGSMITH_API_KEY"] = langsmith_api_key
            os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
        
        langsmith_project = os.getenv("LANGSMITH_PROJECT")
        if langsmith_project:
            self.api_keys["LANGSMITH_PROJECT"] = langsmith_project
            os.environ["LANGCHAIN_PROJECT"] = langsmith_project
    
    def _validate_keys(self, required_keys: list):
        """Validate that required keys are present."""
        missing = [k for k in required_keys if not self.api_keys.get(k)]
        if missing:
            log.error("Missing required API keys", missing_keys=missing)
            raise RAGException(
                f"Missing required API keys: {', '.join(missing)}. "
                "Please set them in .env file or environment variables.",
                sys
            )
    
    def _validate_default_keys(self):
        """Validate default required keys (OpenAI is mandatory)."""
        missing = [k for k in self.REQUIRED_KEYS["openai"] if not self.api_keys.get(k)]
        if missing:
            log.error("Missing required API keys", missing_keys=missing)
            raise RAGException(
                f"Missing required API keys: {', '.join(missing)}. "
                "Please set OPENAI_API_KEY in .env file or environment variables.",
                sys
            )
    
    def get(self, key: str, default: Optional[str] = None) -> str:
        """
        Get API key by name.
        
        Args:
            key: Key name
            default: Default value if key not found (only used if not required)
        
        Returns:
            API key value
        
        Raises:
            KeyError: If key is required but not found
        """
        val = self.api_keys.get(key, default)
        if val is None:
            raise KeyError(f"API key '{key}' is missing and no default provided")
        return val
    
    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self.api_keys and self.api_keys[key] is not None

