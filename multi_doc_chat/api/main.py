from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from multi_doc_chat.api.routes.health import router as health_router
from multi_doc_chat.api.routes.sessions import router as sessions_router
from multi_doc_chat.api.routes.chat import router as chat_router
from multi_doc_chat.api.routes.config import router as config_router
from multi_doc_chat.api.routes.files import router as files_router
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log


# ✅ Application state (shared across all requests)
class AppState:
    """Application-level state that persists across requests."""
    def __init__(self):
        self.model_loader: Optional[ModelLoader] = None
        self.config: Optional[dict] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize shared resources (called once at startup)."""
        if not self._initialized:
            log.info("Initializing application state...")
            # Load config first (will be cached)
            self.config = load_config()
            # Create ModelLoader with cached config
            self.model_loader = ModelLoader(config=self.config)
            self._initialized = True
            log.info("Application state initialized", config_keys=list(self.config.keys()))
    
    def get_model_loader(self) -> ModelLoader:
        """Get shared ModelLoader instance."""
        if not self._initialized:
            self.initialize()
        return self.model_loader
    
    def get_config(self) -> dict:
        """Get cached config."""
        if not self._initialized:
            self.initialize()
        return self.config


# Global app state
app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    # Startup: Initialize shared resources
    log.info("🚀 Starting up application...")
    app_state.initialize()
    yield
    # Shutdown: Cleanup (if needed)
    log.info("🛑 Shutting down application...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="llmops_rag API",
        version="0.1.0",
        lifespan=lifespan  # ✅ Add lifespan events
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for document preview
    data_dir = Path("data")
    if data_dir.exists():
        app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")
    
    # ✅ Store app_state in app for access in routes
    app.state.app_state = app_state

    # Include API routers first (important for route precedence)
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(config_router)
    app.include_router(files_router)
    
    # Mount frontend static files (built from UI/dist) - must be after routers
    ui_dist_dir = Path("UI/dist")
    if ui_dist_dir.exists() and (ui_dist_dir / "index.html").exists():
        # Serve static assets (JS, CSS, etc.) from dist/assets
        assets_dir = ui_dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        
        # Serve index.html and handle SPA routing (must be last route)
        from fastapi.responses import FileResponse
        from fastapi.exceptions import HTTPException
        
        @app.get("/")
        async def serve_index():
            index_path = ui_dist_dir / "index.html"
            return FileResponse(str(index_path))
        
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Skip known API paths and static assets
            if path in ["docs", "redoc", "openapi.json"] or path.startswith(("api/", "data/", "health", "chat", "upload", "ingest", "sessions", "config", "assets")):
                raise HTTPException(status_code=404, detail="Not found")
            # Try to serve file from dist
            file_path = ui_dist_dir / path
            if file_path.exists() and file_path.is_file():
                # Security check: ensure file is within dist directory
                try:
                    file_path.resolve().relative_to(ui_dist_dir.resolve())
                    return FileResponse(str(file_path))
                except ValueError:
                    raise HTTPException(status_code=403, detail="Access denied")
            # For SPA routing, serve index.html for unknown routes
            index_path = ui_dist_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            raise HTTPException(status_code=404, detail="Not found")
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("multi_doc_chat.api.main:app", host="0.0.0.0", port=8000, reload=True)


