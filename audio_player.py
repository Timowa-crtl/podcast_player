"""
Audio playback module using MPV player.
Provides audio control with position tracking and IPC communication.
"""

import subprocess
import threading
import time
import json
import socket
import os
from pathlib import Path
from typing import Optional, Callable

from utils import Logger

logger = Logger()


class AudioPlayer:
    """
    Audio player controller using MPV with IPC socket communication.
    """
    
    def __init__(self, position_callback: Optional[Callable] = None, 
                 save_interval: int = 5):
        """
        Initialize audio player.
        
        Args:
            position_callback: Function to call with position updates
            save_interval: Interval in seconds for position updates
        """
        self.position_callback = position_callback
        self.save_interval = save_interval
        
        # Player state
        self.current_file: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.socket_path = "/tmp/mpv_socket"
        
        # Position tracking
        self._position_thread: Optional[threading.Thread] = None
        self._stop_tracking = threading.Event()
        self._is_paused = False
        self._last_position = 0.0
        
        # Check if MPV is available
        self._check_mpv_available()
    
    def _check_mpv_available(self):
        """Check if MPV is installed."""
        try:
            result = subprocess.run(
                ["which", "mpv"], 
                capture_output=True, 
                text=True
            )
            if result.returncode != 0:
                logger.error("MPV not found. Please install: sudo apt install mpv")
                raise RuntimeError("MPV player not installed")
        except Exception as e:
            logger.error(f"Error checking MPV: {e}")
            raise
    
    def play(self, file_path: str, start_position: float = 0):
        """
        Start playing audio file.
        
        Args:
            file_path: Path to audio file
            start_position: Starting position in seconds
        """
        # Stop any current playback
        self.stop()
        
        # Verify file exists
        if not Path(file_path).exists():
            logger.error(f"Audio file not found: {file_path}")
            return
        
        self.current_file = file_path
        self._last_position = start_position
        self._is_paused = False
        
        # Clean up old socket
        self._cleanup_socket()
        
        try:
            # Start MPV process
            logger.debug(f"Starting MPV: {file_path} at {start_position:.1f}s")
            
            self.process = subprocess.Popen(
                [
                    "mpv",
                    "--no-video",
                    "--really-quiet",
                    "--loop",
                    f"--start={start_position}",
                    f"--input-ipc-server={self.socket_path}",
                    file_path
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for socket to be ready
            self._wait_for_socket()
            
            # Start position tracking
            if self.position_callback:
                self._start_position_tracking()
            
            logger.debug("Playback started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            self.stop()
    
    def _wait_for_socket(self, timeout: float = 2.0):
        """
        Wait for MPV socket to be ready.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(self.socket_path):
                time.sleep(0.1)  # Extra delay for socket to be ready
                return
            time.sleep(0.05)
        
        logger.warning("MPV socket not ready within timeout")
    
    def _send_command(self, command: dict) -> Optional[dict]:
        """
        Send command to MPV via IPC socket.
        
        Args:
            command: Command dictionary to send
            
        Returns:
            Response dictionary or None if failed
        """
        if not self.process or not os.path.exists(self.socket_path):
            return None
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(self.socket_path)
            
            # Send command
            message = json.dumps(command) + "\n"
            sock.send(message.encode())
            
            # Read response
            response = sock.recv(4096).decode()
            sock.close()
            
            if response:
                return json.loads(response.strip())
            
        except (socket.error, json.JSONDecodeError) as e:
            logger.debug(f"IPC command failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected IPC error: {e}")
        
        return None
    
    def pause(self):
        """Pause playback."""
        if self.process and not self._is_paused:
            # Save position before pausing
            self._update_position()
            
            # Send pause command
            self._send_command({"command": ["set_property", "pause", True]})
            self._is_paused = True
            logger.debug("Playback paused")
    
    def resume(self):
        """Resume playback."""
        if self.process and self._is_paused:
            self._send_command({"command": ["set_property", "pause", False]})
            self._is_paused = False
            logger.debug("Playback resumed")
    
    def stop(self):
        """Stop playback and clean up."""
        # Stop position tracking
        if self._position_thread:
            self._stop_tracking.set()
            self._position_thread.join(timeout=1)
            self._position_thread = None
        
        # Save final position
        if self.process and self.current_file:
            self._update_position()
        
        # Terminate MPV process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("MPV didn't terminate, killing process")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping MPV: {e}")
            
            self.process = None
        
        # Clean up
        self._cleanup_socket()
        self.current_file = None
        self._is_paused = False
        
        logger.debug("Playback stopped")
    
    def get_position(self) -> float:
        """
        Get current playback position.
        
        Returns:
            Position in seconds
        """
        if not self.process:
            return self._last_position
        
        response = self._send_command({"command": ["get_property", "time-pos"]})
        
        if response and "data" in response:
            position = float(response["data"])
            self._last_position = position
            return position
        
        return self._last_position
    
    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            True if playing (not paused or stopped)
        """
        return self.process is not None and not self._is_paused
    
    def _start_position_tracking(self):
        """Start background position tracking thread."""
        self._stop_tracking.clear()
        self._position_thread = threading.Thread(
            target=self._track_position,
            daemon=True
        )
        self._position_thread.start()
        logger.debug("Position tracking started")
    
    def _track_position(self):
        """Background thread to periodically save position."""
        while not self._stop_tracking.wait(self.save_interval):
            if self.process and not self._is_paused:
                self._update_position()
    
    def _update_position(self):
        """Update current position via callback."""
        if self.position_callback and self.current_file:
            try:
                position = self.get_position()
                self.position_callback(position)
            except Exception as e:
                logger.error(f"Error updating position: {e}")
    
    def _cleanup_socket(self):
        """Remove IPC socket file."""
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception as e:
                logger.error(f"Error removing socket: {e}")
    
    def cleanup(self):
        """Clean up all resources."""
        self.stop()
        logger.debug("Audio player cleanup complete")
