import sys
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio

# Add current directory and project root to path
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '../..'))

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api import upload, process, status, download
from services.task_manager import task_manager

app = FastAPI(
    title="Video Subtitle Remover Web",
    description="Web interface for video subtitle removal",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(download.router, prefix="/api", tags=["download"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Video Subtitle Remover Web API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.websocket("/ws/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time progress updates
    """
    await websocket.accept()

    try:
        while True:
            # Get progress
            progress = await task_manager.get_progress(task_id)

            # Send to client
            await websocket.send_json(progress)

            # Stop if completed or error
            if progress["status"] in ["completed", "error"]:
                break

            # Wait before next update
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "message": str(e)
        })


# Mount static files (frontend) if exists
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
