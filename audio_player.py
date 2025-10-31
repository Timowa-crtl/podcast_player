import subprocess
import threading
import time
import json
import socket
import os
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime
from utils import debug_log


class AudioPlayer:
    def __init__(self, position_callback: Optional[Callable[[float], None]] = None):
        """
        Initialize MPV player with IPC control

        Args:
            position_callback: Function to call with current position (every 5 sec)
        """
        self.position_callback = position_callback
        self.current_file = None
        self.process = None
        self.socket_path = "/tmp/mpv_socket"
        self._position_thread = None
        self._stop_position_tracking = False
        self._is_paused = False
        self._start_position = 0.0

    def play(self, file_path: str, start_position: float = 0):
        """Play audio file from given position"""
        debug_log(f"AudioPlayer.play() called with position {start_position:.1f}s")
        self.stop()

        self.current_file = file_path
        self._start_position = start_position
        self._is_paused = False

        # Remove old socket if exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            debug_log("Removed old socket")

        # Start mpv with IPC server
        debug_log(f"Starting MPV process...")
        self.process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--loop",
                f"--start={start_position}",
                f"--input-ipc-server={self.socket_path}",
                file_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for socket to be ready
        time.sleep(0.5)
        debug_log("MPV process started")

        # Start position tracking thread
        if self.position_callback:
            self._stop_position_tracking = False
            self._position_thread = threading.Thread(
                target=self._track_position, daemon=True
            )
            self._position_thread.start()
            debug_log("Position tracking thread started")

    def _send_command(self, command: dict) -> Optional[dict]:
        """Send command to mpv via IPC socket"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.send((json.dumps(command) + "\n").encode())
            response = sock.recv(4096).decode()
            sock.close()
            return json.loads(response) if response else None
        except:
            return None

    def pause(self):
        """Pause playback"""
        if self.process and not self._is_paused:
            self._send_command({"command": ["set_property", "pause", True]})
            self._is_paused = True

    def resume(self):
        """Resume playback"""
        if self.process and self._is_paused:
            self._send_command({"command": ["set_property", "pause", False]})
            self._is_paused = False

    def stop(self):
        """Stop playback"""
        self._stop_position_tracking = True
        if self._position_thread:
            self._position_thread.join(timeout=1)

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except:
                self.process.kill()
            self.process = None

        self.current_file = None
        self._is_paused = False

    def get_position(self) -> float:
        """Get current playback position in seconds"""
        if not self.process:
            return 0.0

        response = self._send_command({"command": ["get_property", "time-pos"]})
        if response and "data" in response:
            return float(response["data"])
        return self._start_position

    def is_playing(self) -> bool:
        """Check if player is currently playing"""
        return self.process is not None and not self._is_paused

    def _track_position(self):
        """Background thread to track and save position every X seconds"""
        while not self._stop_position_tracking:
            time.sleep(5)
            if self.position_callback and self.current_file and self.process:
                position = self.get_position()
                self.position_callback(position)

    def cleanup(self):
        """Clean up player resources"""
        self.stop()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
