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
        Initialize MPV player with IPC control (persistent process)

        Args:
            position_callback: Function to call with current position (every X seconds)
        """
        self.position_callback = position_callback
        self.current_file = None
        self.process = None
        self.socket_path = "/tmp/mpv_socket"
        self._position_thread = None
        self._stop_position_tracking = False
        self._is_paused = True  # Start paused
        self._is_idle = True  # Track if MPV is idle (no file loaded)
        self._socket_lock = threading.Lock()  # Thread-safe socket access

        # Start persistent MPV process
        self._start_mpv_process()

    def _start_mpv_process(self):
        """Start persistent MPV process in idle mode"""
        # Remove old socket if exists
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
                debug_log("Removed old socket")
            except OSError as e:
                debug_log(f"Warning: Could not remove old socket: {e}")

        # Start mpv in idle mode (no file loaded)
        debug_log("Starting persistent MPV process...")
        try:
            self.process = subprocess.Popen(
                [
                    "mpv",
                    "--no-video",
                    "--idle",  # Keep process alive
                    "--loop",
                    f"--input-ipc-server={self.socket_path}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            debug_log("ERROR: mpv not found. Please install mpv.")
            raise

        # Wait for socket to be ready
        socket_ready = False
        for attempt in range(30):  # 3 second max wait
            if os.path.exists(self.socket_path):
                time.sleep(0.15)  # Buffer for socket to be ready
                socket_ready = True
                break
            time.sleep(0.1)

        if not socket_ready:
            debug_log("ERROR: MPV socket not ready after 3 seconds")
            self.cleanup()
            raise RuntimeError("MPV failed to start")

        debug_log("Persistent MPV process started")

        # Start position tracking thread
        if self.position_callback:
            self._stop_position_tracking = False
            self._position_thread = threading.Thread(
                target=self._track_position, daemon=True
            )
            self._position_thread.start()
            debug_log("Position tracking thread started")

    def _send_command(self, command: dict, retry: bool = True) -> Optional[dict]:
        """Send command to mpv via IPC socket with thread-safe access"""
        with self._socket_lock:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)  # 2 second timeout
                sock.connect(self.socket_path)
                sock.send((json.dumps(command) + "\n").encode())
                response = sock.recv(4096).decode()
                sock.close()

                if response:
                    return json.loads(response)
                return None

            except (socket.error, socket.timeout, json.JSONDecodeError) as e:
                debug_log(f"IPC command failed: {e}")

                # Retry once if process died
                if retry and self.process and self.process.poll() is not None:
                    debug_log("Process died, attempting restart...")
                    self._ensure_process_alive()
                    return self._send_command(command, retry=False)

                return None
            except Exception as e:
                debug_log(f"Unexpected IPC error: {e}")
                return None

    def _ensure_process_alive(self):
        """Restart MPV process if it died"""
        if self.process and self.process.poll() is not None:
            debug_log("MPV process died, restarting...")

            # Clean up old socket
            if os.path.exists(self.socket_path):
                try:
                    os.remove(self.socket_path)
                except OSError:
                    pass

            # Stop position tracking temporarily
            was_tracking = self._position_thread is not None
            if was_tracking:
                self._stop_position_tracking = True
                if self._position_thread:
                    self._position_thread.join(timeout=1)

            # Restart
            self._start_mpv_process()

            debug_log("MPV process restarted")

    def play(self, file_path: str, start_position: float = 0):
        """Play audio file from given position (uses existing MPV process)"""
        debug_log(f"AudioPlayer.play() called with position {start_position:.1f}s")

        # Ensure process is alive
        self._ensure_process_alive()

        # Validate file exists
        if not os.path.exists(file_path):
            debug_log(f"ERROR: File not found: {file_path}")
            return

        self.current_file = file_path
        self._is_paused = False
        self._is_idle = False

        # Load file into MPV
        debug_log(f"Loading file into MPV: {file_path}")
        result = self._send_command({"command": ["loadfile", file_path, "replace"]})

        if result is None:
            debug_log("ERROR: Failed to load file")
            self._is_idle = True
            return

        # Wait for file to load before seeking
        if start_position > 0:
            time.sleep(0.2)  # Give MPV time to load file

            # Verify file loaded by checking if we can get duration
            for _ in range(5):
                response = self._send_command({"command": ["get_property", "duration"]})
                if response and "data" in response:
                    break
                time.sleep(0.1)

            debug_log(f"Seeking to {start_position:.1f}s")
            self._send_command({"command": ["seek", start_position, "absolute"]})

        debug_log(f"Now playing from {start_position:.1f}s")

    def pause(self):
        """Pause playback"""
        if self.process and not self._is_paused and not self._is_idle:
            # Save position before pausing
            if self.position_callback and self.current_file:
                position = self.get_position()
                if position > 0:
                    self.position_callback(position)

            result = self._send_command({"command": ["set_property", "pause", True]})
            if result is not None:
                self._is_paused = True
                debug_log("Paused")

    def resume(self):
        """Resume playback"""
        if self.process and self._is_paused and not self._is_idle:
            result = self._send_command({"command": ["set_property", "pause", False]})
            if result is not None:
                self._is_paused = False
                debug_log("Resumed")

    def stop(self):
        """Stop playback (but keep MPV process alive)"""
        if not self._is_idle:
            debug_log("Stopping playback (MPV stays alive)")

            # Save final position before stopping
            if self.position_callback and self.current_file:
                position = self.get_position()
                if position > 0:
                    self.position_callback(position)

            self._send_command({"command": ["stop"]})
            self.current_file = None
            self._is_paused = True
            self._is_idle = True

    def get_position(self) -> float:
        """Get current playback position in seconds"""
        if not self.process or self._is_idle:
            return 0.0

        response = self._send_command({"command": ["get_property", "time-pos"]})
        if response and "data" in response:
            try:
                return float(response["data"])
            except (ValueError, TypeError):
                debug_log("Warning: Invalid position data")
                return 0.0
        return 0.0

    def is_playing(self) -> bool:
        """Check if player is currently playing"""
        return self.process is not None and not self._is_paused and not self._is_idle

    def _track_position(self):
        """Background thread to track and save position every 5 seconds"""
        while not self._stop_position_tracking:
            time.sleep(5)

            # Only save if actively playing
            if (
                self.position_callback
                and self.current_file
                and not self._is_idle
                and not self._is_paused
            ):
                position = self.get_position()
                if position > 0:  # Only save valid positions
                    self.position_callback(position)

    def cleanup(self):
        """Clean up player resources"""
        debug_log("Cleaning up MPV...")

        # Stop position tracking
        self._stop_position_tracking = True
        if self._position_thread:
            self._position_thread.join(timeout=2)

        # Terminate MPV process
        if self.process:
            # Try graceful quit first
            self._send_command({"command": ["quit"]})
            time.sleep(0.3)

            # Force kill if still alive
            if self.process.poll() is None:
                debug_log("Force terminating MPV...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()

            self.process = None

        # Clean up socket
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
                debug_log("Socket cleaned up")
            except OSError as e:
                debug_log(f"Warning: Could not remove socket: {e}")
