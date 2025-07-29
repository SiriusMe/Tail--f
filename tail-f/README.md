# Tail-F: Real-Time Log Monitoring System

This project is a **real-time log monitoring system** that watches log files and displays their contents in a web browser as they change. It's like the Unix `tail -f` command, but with a web interface that multiple users can access simultaneously.

## 🎯 What Does This System Do?

Imagine you have log files on your server that are constantly being updated with new information. Instead of manually checking these files or running commands repeatedly, this system:

1. **Watches** your log files continuously
2. **Detects** when new lines are added
3. **Broadcasts** new content to all connected web browsers in real-time
4. **Handles** log file rotation (when old logs are moved and new ones created)

## 📁 Project Structure

```
tail-f/
├── main.py              # Main application entry point
├── websocket_manager.py # Manages WebSocket connections
├── log_watcher.py       # Monitors log files for changes
├── config.py            # Configuration settings
├── requirements.txt     # Python dependencies
├── index.html          # Web interface for viewing logs
└── log/                # Directory containing log files
    ├── app.log         # Application log file
    └── error.log       # Error log file
```

## 🔧 Dependencies (requirements.txt)

Before running this system, you need to install these Python packages:

```
fastapi==0.104.1        # Web framework for creating APIs
uvicorn==0.24.0         # ASGI server to run the web application
websockets==12.0        # WebSocket library for real-time communication
watchfiles==0.21.0     # File watching utilities (not currently used)
python-multipart==0.0.6 # For handling multipart form data
```

**Install them with:** `pip install -r requirements.txt`

## 📋 Configuration (config.py)

This file contains all the settings for the system:

```python
# config.py
LOG_FILES = {
    "app_log": "./log/app.log",    # Main application logs
    "error_log": "./log/error.log" # Error logs
}
POLL_INTERVAL = 1.0  # How often to check for changes (seconds)
```

### What each setting means:

- **`LOG_FILES`**: A dictionary that maps log names to file paths
  - `"app_log"`: A friendly name for the log
  - `"./log/app.log"`: The actual file path to monitor
  - You can add more log files by adding more entries

- **`POLL_INTERVAL`**: How often (in seconds) the system checks for file changes
  - `1.0` means check every second
  - Lower values = more responsive but use more CPU
  - Higher values = less CPU usage but slower updates

## 🌐 Web Interface (index.html)

This is the frontend that users see in their web browser:

```html
<!DOCTYPE html>
<html>
<body>
  <h2>Log Viewer</h2>
  <pre id="log"></pre>

  <script>
    const log = document.getElementById("log");
    const ws = new WebSocket("ws://192.168.226.96:8800/ws/logs");

    ws.onmessage = (event) => {
      log.textContent += event.data + "\n";
    };
  </script>
</body>
</html>
```

### How it works:

1. **HTML Structure**: Creates a simple page with a heading and a `<pre>` element to display logs
2. **WebSocket Connection**: Connects to the server using WebSockets for real-time communication
3. **Message Handling**: When new log data arrives, it's automatically added to the display

**Note**: You'll need to change the IP address `192.168.226.96` to match your server's IP address.

## 🔌 WebSocket Manager (websocket_manager.py)

This module handles all WebSocket connections and broadcasts messages to connected clients:

```python
from fastapi import WebSocket
from typing import Set
import asyncio
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
```

### Key Components:

#### 1. Connection Management
```python
async def connect(self, websocket: WebSocket):
    await websocket.accept()  # Accept the WebSocket connection
    self.active_connections.add(websocket)  # Add to active connections
```

#### 2. Disconnection Handling
```python
def disconnect(self, websocket: WebSocket):
    self.active_connections.discard(websocket)  # Remove from active connections
```

#### 3. Broadcasting Messages
```python
async def broadcast(self, log_id: str, message: str):
    data = json.dumps({
        "log_id": log_id,    # Which log file this came from
        "message": message   # The actual log content
    })
    
    to_remove = set()
    for connection in self.active_connections:
        try:
            await connection.send_text(data)  # Send to each connected client
        except:
            to_remove.add(connection)  # Mark failed connections for removal
    
    # Clean up failed connections
    for conn in to_remove:
        self.disconnect(conn)
```

### How Broadcasting Works:

1. **Input**: Receives a log ID and message
2. **Format**: Converts to JSON format with both log source and content
3. **Send**: Attempts to send to all connected clients
4. **Cleanup**: Removes any failed connections automatically

## 👁️ Log Watcher (log_watcher.py)

This is the core component that monitors log files for changes:

```python
class LogTailWatcher:
    def __init__(self, log_id: str, filepath: str):
        self.log_id = log_id      # Friendly name for this log
        self.filepath = filepath   # Path to the log file
        self.inode = None         # File system identifier
        self.file = None          # File handle
        self.first_open = True    # Track if this is the first time opening
        self.position = 0         # Current position in file
```

### Key Concepts:

#### 1. File Rotation Detection
Log files are often "rotated" - the old file is moved to `.log.1` and a new file is created. We detect this using **inodes** (unique file system identifiers):

```python
def _is_rotated(self):
    try:
        if not os.path.exists(self.filepath):
            return True
        current_inode = os.stat(self.filepath).st_ino
        return current_inode != self.inode if self.inode is not None else False
    except FileNotFoundError:
        return True
```

#### 2. Smart File Opening
```python
def _open_file(self):
    try:
        # Open with universal newlines mode and utf-8 encoding
        self.file = open(self.filepath, 'r', encoding='utf-8', newline=None)
        self.inode = os.fstat(self.file.fileno()).st_ino
    except Exception as e:
        print(f"[ERROR] Failed to open {self.filepath}: {e}")
        self.file = None
        self.inode = None
```

#### 3. The Main Watching Loop
This is where the magic happens:

```python
async def watch(self):
    while True:  # Run forever
        try:
            rotated = False
            
            # Check if we need to open/reopen the file
            if self.file is None or self._is_rotated():
                if self.file:
                    self.file.close()
                    print(f"[INFO] Rotation detected for {self.filepath}")
                    rotated = True
                
                await self._wait_for_file()  # Wait for file to exist
                self._open_file()
                
                if not self.file:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                
                # Decide where to start reading
                if self.first_open:
                    # First time: start at end (like tail -f)
                    self.file.seek(0, os.SEEK_END)
                    self.position = self.file.tell()
                    self.first_open = False
                elif rotated:
                    # After rotation: start at beginning
                    self.file.seek(0, os.SEEK_SET)
                    self.position = 0
            
            # Handle file truncation (when file is cleared)
            size = os.path.getsize(self.filepath)
            if size < self.position:
                print(f"[INFO] File truncated {self.filepath} - reading from start")
                self.file.seek(0, os.SEEK_SET)
                self.position = 0
            elif size > self.position:
                self.file.seek(self.position, os.SEEK_SET)
            
            # Read new content
            line = self.file.readline()
            if line:
                line = line.rstrip('\r\n')
                if line:  # Only broadcast non-empty lines
                    await manager.broadcast(self.log_id, line)
                    self.position = self.file.tell()
            else:
                await asyncio.sleep(POLL_INTERVAL)  # No new content, wait
                
        except Exception as e:
            print(f"[ERROR] Failed watching {self.filepath}: {e}")
            # Clean up and retry
            if self.file:
                try:
                    self.file.close()
                except:
                    pass
            self.file = None
            await asyncio.sleep(POLL_INTERVAL)
```

### Reading Strategy:

- **First Open**: Start at the end of the file (like `tail -f`)
- **After Rotation**: Start at the beginning of the new file
- **After Truncation**: Start at the beginning
- **Normal Operation**: Continue from last position

## 🚀 Main Application (main.py)

This ties everything together using FastAPI:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websocket_manager import manager
from log_watcher import LogTailWatcher
from config import LOG_FILES
import asyncio

app = FastAPI()  # Create FastAPI application
```

### WebSocket Endpoint
```python
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)  # Connect new client
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)  # Clean up on disconnect
```

### Application Startup
```python
@app.on_event("startup")
async def startup_event():
    # Start watching each configured log file
    for log_id, filepath in LOG_FILES.items():
        watcher = LogTailWatcher(log_id, filepath)
        asyncio.create_task(watcher.watch())  # Run in background
```

## 🔄 How Everything Works Together

1. **Startup**: When you run the application:
   - FastAPI starts the web server
   - Log watchers are created for each configured log file
   - Each watcher runs in its own background task

2. **Client Connection**: When someone opens the web page:
   - Browser establishes WebSocket connection
   - Connection is added to the manager's active connections

3. **Log Monitoring**: Continuously:
   - Each watcher checks its log file for changes
   - New lines are read and sent to the WebSocket manager
   - Manager broadcasts to all connected clients

4. **Real-time Updates**: In the browser:
   - WebSocket receives JSON messages
   - New content is immediately displayed
   - Multiple users see the same updates simultaneously

## 🎯 Running the System

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Start the server**: `uvicorn main:app --host 0.0.0.0 --port 8800`
3. **Open browser**: Navigate to your `index.html` file
4. **View logs**: New log entries appear automatically

## 🧪 Testing Log Rotation

To test the rotation feature:

```bash
# Add content to log
echo "before rotation" >> log/app.log

# Simulate rotation
copy log/app.log log/app.log.1
type nul > log/app.log
echo "after rotation" >> log/app.log
```

You should see both messages appear in the web interface.

## 🔧 Key Features

- **Real-time**: Updates appear instantly in browser
- **Multi-client**: Multiple users can watch simultaneously
- **Rotation-aware**: Handles log file rotation gracefully
- **Robust**: Recovers from file system errors
- **Cross-platform**: Works on Windows, Linux, macOS
- **Lightweight**: Minimal CPU and memory usage

## 🚨 Common Issues & Solutions

1. **"WebSocketManager.broadcast() takes 2 positional arguments but 3 were given"**
   - Fixed by updating broadcast method to accept both log_id and message

2. **Missing "after rotation" messages**
   - Fixed by improving rotation detection and file positioning

3. **Empty/null messages**
   - Fixed by proper Windows line ending handling and encoding

4. **Connection issues**
   - Check IP address in HTML file matches your server
   - Ensure firewall allows connections on port 8800

This system provides a powerful, real-time log monitoring solution that's both simple to understand and robust in operation. 