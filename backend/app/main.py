"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .api.routes import router
from .api.websocket import websocket_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    os.makedirs(settings.storage_path, exist_ok=True)
    yield
    # Shutdown
    pass


# Create FastAPI app
app = FastAPI(
    title="PPTMaker Agent API",
    description="AI-powered PPT generation with multi-agent collaboration",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for downloads
os.makedirs(settings.storage_path, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "PPTMaker Agent",
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
