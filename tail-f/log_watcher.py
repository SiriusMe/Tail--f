import os
import asyncio
from config import POLL_INTERVAL
from websocket_manager import manager

class LogTailWatcher:
    def __init__(self, log_id: str, filepath: str):
        self.log_id = log_id
        self.filepath = filepath
        self.inode = self.file = None
        self.first_open = True
        self.position = 0

    def _open_file(self):
        """Open the file and store its inode number"""
        try:
            self.file = open(self.filepath, 'r', encoding='utf-8', newline=None)
            self.inode = os.fstat(self.file.fileno()).st_ino
        except Exception as e:
            print(f"[ERROR] Failed to open {self.filepath}: {e}")
            self.file = self.inode = None

    def _is_rotated(self):
        try:
            return (not os.path.exists(self.filepath) or 
                   (self.inode is not None and os.stat(self.filepath).st_ino != self.inode))
        except Exception as e:
            print(f"[ERROR] Failed to check rotation for {self.filepath}: {e}")
            return True

    async def _wait_for_file(self):
        while not os.path.exists(self.filepath):
            print(f"[INFO] Waiting for {self.filepath} to reappear...")
            await asyncio.sleep(POLL_INTERVAL)

    def _close_file(self):
        if self.file:
            try:
                self.file.close()
            except:
                pass
            self.file = None

    def get_last_lines(self, n: int = 10) -> list:
        """Efficiently get last N lines from large files using reverse reading"""
        try:
            if not os.path.exists(self.filepath):
                return []
            
            with open(self.filepath, 'rb') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    return []
                
                lines, buffer, chunk_size, pos = [], bytearray(), min(8192, file_size), file_size
                
                while len(lines) < n and pos > 0:
                    read_size = min(chunk_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    buffer = f.read(read_size) + buffer
                    
                    text = buffer.decode('utf-8', errors='ignore')
                    split_lines = text.split('\n')
                    
                    if pos > 0 and len(split_lines) > 1:
                        buffer, lines = split_lines[0].encode('utf-8'), split_lines[1:] + lines
                    else:
                        buffer, lines = bytearray(), split_lines + lines
                    
                    lines = [line for line in lines if line.strip()]
                    if len(lines) > n:
                        return lines[-n:]
                
                return lines[-n:] if lines else []
                
        except Exception as e:
            print(f"[ERROR] Failed to get last lines from {self.filepath}: {e}")
            return []

    async def watch(self):
        while True:
            try:
                rotated = False
                
                if self.file is None or self._is_rotated():
                    if self.file:
                        self._close_file()
                        print(f"[INFO] Rotation detected for {self.filepath}")
                        rotated = True
                    
                    await self._wait_for_file()
                    self._open_file()
                    
                    if not self.file:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
                    
                    if self.first_open:
                        print(f"[INFO] First open of {self.filepath} - seeking to end")
                        self.file.seek(0, os.SEEK_END)
                        self.first_open = False
                    elif rotated:
                        print(f"[INFO] Rotation detected for {self.filepath} - reading from start")
                        self.file.seek(0, os.SEEK_SET)
                    self.position = self.file.tell()

                size = os.path.getsize(self.filepath)
                if size < self.position:
                    print(f"[INFO] File truncated {self.filepath} - reading from start")
                    self.file.seek(0, os.SEEK_SET)
                    self.position = 0
                elif size > self.position:
                    self.file.seek(self.position, os.SEEK_SET)

                if line := self.file.readline():
                    if line := line.rstrip('\r\n'):
                        await manager.broadcast(self.log_id, line)
                        self.position = self.file.tell()
                else:
                    await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                print(f"[ERROR] Failed watching {self.filepath}: {e}")
                self._close_file()
                await asyncio.sleep(POLL_INTERVAL)

    def __del__(self):
        self._close_file()

def get_last_lines(filepath: str, n: int = 10) -> list:
    """Module-level function to get last N lines from a log file"""
    return LogTailWatcher("temp", filepath).get_last_lines(n)
