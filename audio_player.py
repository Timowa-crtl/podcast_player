"""
Audio playback module using mpg123 player.
Provides audio control with position tracking via remote control interface.
"""

import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from utils import Logger

logger = Logger()


class AudioPlayer:
    """
    Audio player controller using mpg123 with remote control interface.
    """

    def __init__(self, position_callback: Optional[Callable] = None, save_interval: int = 5):
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

        # Position tracking
        self._position_thread: Optional[threading.Thread] = None
        self._stop_tracking = threading.Event()
        self._is_paused = False
        self._last_position = 0.0
        self._start_position = 0.0
        self._play_start_time = 0.0

        # Output monitoring thread
        self._output_thread: Optional[threading.Thread] = None

        # Check if mpg123 is available
        self._check_mpg123_available()

    def _check_mpg123_available(self):
        """Check if mpg123 is installed."""
        try:
            result = subprocess.run(["which", "mpg123"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("mpg123 not found. Please install: sudo apt install mpg123")
                raise RuntimeError("mpg123 player not installed")
        except Exception as e:
            logger.error(f"Error checking mpg123: {e}")
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
        self._start_position = start_position
        self._is_paused = False
        self._play_start_time = time.time()

        try:
            # Start mpg123 process with remote control
            logger.debug(f"Starting mpg123: {file_path} at {start_position:.1f}s")

            # Calculate frame offset (mpg123 uses frames, ~38.28 frames per second for MP3)
            frame_offset = int(start_position * 38.28)

            self.process = subprocess.Popen(
                [
                    "mpg123",
                    "-R",  # Remote control mode
                    "--loop",
                    "-1",  # Loop infinitely
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )

            # Start output reader thread to prevent blocking
            self._start_output_reader()

            # Load file and seek to position
            self._send_command(f"LOAD {file_path}")

            if frame_offset > 0:
                self._send_command(f"JUMP +{frame_offset}f")

            # Start position tracking
            if self.position_callback:
                self._start_position_tracking()

            logger.debug("Playback started successfully")

        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            self.stop()

    def _send_command(self, command: str):
        """
        Send command to mpg123 remote control interface.

        Args:
            command: Command string to send
        """
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
                logger.debug(f"Sent command: {command}")
            except Exception as e:
                logger.error(f"Failed to send command: {e}")

    def _start_output_reader(self):
        """Start thread to read and discard mpg123 stdout to prevent blocking."""
        self._output_thread = threading.Thread(target=self._read_output, daemon=True)
        self._output_thread.start()
        logger.debug("Output reader thread started")

    def _read_output(self):
        """Read mpg123 output continuously to prevent stdout buffer from filling."""
        if not self.process or not self.process.stdout:
            return

        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if not line:
                    break
                # Optionally log output for debugging
                if line.startswith("@F"):
                    # Frame position update from mpg123
                    logger.debug(f"mpg123 output: {line.strip()}")
        except Exception as e:
            logger.error(f"Error reading mpg123 output: {e}")

    def pause(self):
        """Pause playback."""
        if self.process and not self._is_paused:
            # Update position before pausing
            self._update_position()

            # Send pause command
            self._send_command("PAUSE")
            self._is_paused = True
            logger.debug("Playback paused")

    def resume(self):
        """Resume playback."""
        if self.process and self._is_paused:
            self._send_command("PAUSE")
            self._play_start_time = time.time()
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

        # Terminate mpg123 process
        if self.process:
            try:
                self._send_command("QUIT")
                time.sleep(0.1)

                if self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("mpg123 didn't terminate, killing process")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping mpg123: {e}")

            self.process = None

        # Output reader thread will stop automatically when process ends
        if self._output_thread:
            self._output_thread.join(timeout=1)
            self._output_thread = None

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

        # Check if process is still alive
        if self.process.poll() is not None:
            logger.error("mpg123 process died unexpectedly")
            self.process = None
            return self._last_position

        # If paused, return last known position
        if self._is_paused:
            return self._last_position

        # Calculate position based on elapsed time since play started
        elapsed = time.time() - self._play_start_time
        current_position = self._start_position + elapsed
        self._last_position = current_position

        return current_position

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
        self._position_thread = threading.Thread(target=self._track_position, daemon=True)
        self._position_thread.start()
        logger.debug("Position tracking started")

    def _track_position(self):
        """Background thread to periodically save position."""
        while not self._stop_tracking.wait(self.save_interval):
            if self.process and not self._is_paused:
                # Check if process is still alive
                if self.process.poll() is not None:
                    logger.error("mpg123 process died during playback")
                    break
                self._update_position()

    def _update_position(self):
        """Update current position via callback."""
        if self.position_callback and self.current_file:
            try:
                position = self.get_position()
                self.position_callback(position)
            except Exception as e:
                logger.error(f"Error updating position: {e}")

    def cleanup(self):
        """Clean up all resources."""
        self.stop()
        logger.debug("Audio player cleanup complete")
