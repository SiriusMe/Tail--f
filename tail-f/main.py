# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

import log_watcher
from websocket_manager import manager
from log_watcher import LogTailWatcher
from config import LOG_FILES
import asyncio
import os
import json

app = FastAPI()

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Send last 10 lines from each log file to new client
    historical_lines = []
    for log_id, filepath in LOG_FILES.items():
        lines = log_watcher.get_last_lines(filepath, 5)  # 5 lines per log to make total ~10
        for line in lines:
            historical_lines.append(f"[{log_id}] {line}")
    
    if historical_lines:
        await websocket.send_text(json.dumps({
            "type": "historical",
            "lines": historical_lines
        }))
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    for log_id, filepath in LOG_FILES.items():
        watcher = LogTailWatcher(log_id, filepath)
        asyncio.create_task(watcher.watch())

