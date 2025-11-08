"""
FastAPI dependencies for shared resources.
"""
from fastapi import Request
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config


def get_model_loader(request: Request) -> ModelLoader:
    """Dependency to get shared ModelLoader instance."""
    return request.app.state.app_state.get_model_loader()


def get_config(request: Request) -> dict:
    """Dependency to get cached config."""
    return load_config()

