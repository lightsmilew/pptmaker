"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.routes import router
from .api.workspace import router as workspace_router
from .api.websocket import websocket_handler
from .api.auth import router as auth_router, allowed_origins
from .api.files import router as files_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    os.makedirs(settings.storage_path, exist_ok=True)
    from .storage.memory import memory_store
    memory_store.recover_interrupted()
    yield
    # Shutdown
    pass


# Create FastAPI app
app = FastAPI(
    title="Folio Studio API",
    description="A quiet workspace for ideas, editable presentations, and your creative archive.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth_router)
app.include_router(files_router)
app.include_router(router)
app.include_router(workspace_router)


@app.middleware("http")
async def private_response_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/", "/storage/")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Folio Studio",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time updates."""
    await websocket_handler(websocket, project_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
