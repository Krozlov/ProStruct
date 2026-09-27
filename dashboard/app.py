"""
ProStruct Dashboard: FastAPI + WebSocket backend for real-time monitoring.
"""

import sys
import os
from pathlib import Path
from typing import List
from datetime import datetime
import json
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.queue_system import TaskQueue


app = FastAPI(title="ProStruct Dashboard")

# Initialize queue connection
queue = TaskQueue()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


@app.get("/")
async def get_dashboard():
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "index.html"
    with open(html_path, 'r') as f:
        return HTMLResponse(content=f.read())


@app.get("/api/stats")
async def get_stats():
    """Get current queue statistics."""
    return queue.get_queue_stats()


@app.get("/api/results")
async def get_results(limit: int = 100):
    """Get recent results."""
    return queue.get_results(limit)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        # Send initial stats
        await websocket.send_json({
            "type": "stats",
            "data": queue.get_queue_stats()
        })
        
        # Background task to poll for updates
        while True:
            await asyncio.sleep(1)
            stats = queue.get_queue_stats()
            await websocket.send_json({
                "type": "stats",
                "data": stats
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    """Initialize Redis pub/sub for real-time updates."""
    print("Dashboard started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("Dashboard stopped")


if __name__ == "__main__":
    import uvicorn
    config = queue.load_config('config.yaml')
    uvicorn.run(
        app,
        host=config['dashboard']['host'],
        port=config['dashboard']['port']
    )
