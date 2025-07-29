# websocket_manager.py
from fastapi import WebSocket
from typing import Set
import asyncio
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, log_id: str, message: str):
        """Broadcast real-time log messages to all connected clients"""
        data = json.dumps({
            "type": "realtime",
            "log_id": log_id,
            "message": message
        })
        await self._send_to_all(data)
    
    async def send_historical(self, websocket: WebSocket, lines: list):
        """Send historical data to a specific client"""
        data = json.dumps({
            "type": "historical", 
            "lines": lines
        })
        try:
            await websocket.send_text(data)
        except:
            self.disconnect(websocket)
    
    async def _send_to_all(self, data: str):
        """Internal method to send data to all connected clients"""
        to_remove = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except:
                to_remove.add(connection)
        
        # Clean up failed connections
        for conn in to_remove:
            self.disconnect(conn)

manager = WebSocketManager()
