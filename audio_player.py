"""
Audio playback module using python-vlc.
Provides audio control with position tracking via VLC media player API.
"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import vlc
from utils import Logger

logger = Logger()


class AudioPlayer:
    """
    Audio player controller using python-vlc.
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

        # Force ALSA to avoid PulseAudio warnings
        self.instance = vlc.Instance("--aout=alsa")

        # VLC objects
        self.player: Optional[vlc.MediaPlayer] = None
        self.media: Optional[vlc.Media] = None

        # State
        self.current_file: Optional[str] = None
        self._is_paused = False
        self._last_position = 0.0

        # Threads
        self._position_thread: Optional[threading.Thread] = None
        self._stop_tracking = threading.Event()

    # ----------------------------------------------
    # Utility: read duration (waits briefly)
    # ----------------------------------------------

    def _get_duration(self, timeout=2.0) -> float:
        """
        Return media duration in seconds.
        We wait a short moment so VLC has time to read metadata.

        Args:
            timeout: max seconds to wait for duration
        """
        if not self.player:
            return 0.0

        deadline = time.time() + timeout

        duration_ms = self.player.get_length()

        # VLC may return -1 or 0 if it hasn't parsed the file yet,
        # so we wait a bit for real metadata to load.
        while duration_ms <= 0 and time.time() < deadline:
            time.sleep(0.05)
            duration_ms = self.player.get_length()

        # convert to seconds
        return max(duration_ms / 1000.0, 0.0)

    # ----------------------------------------------
    # Playback controls
    # ----------------------------------------------

    def play(self, file_path: str, start_position: float = 0.0):
        """
        Start playing audio file.

        Args:
            file_path: Path to audio file
            start_position: Starting position in seconds
        """
        self.stop()

        if not Path(file_path).exists():
            logger.error(f"Audio file not found: {file_path}")
            return

        self.current_file = file_path
        self._last_position = start_position
        self._is_paused = False

        logger.debug(f"Starting VLC: {file_path} at {start_position:.1f}s")

        try:
            self.media = self.instance.media_new(file_path)
            self.player = self.instance.media_player_new()
            self.player.set_media(self.media)

            # Start playback so VLC begins reading file info
            self.player.play()
            time.sleep(0.1)  # brief pause so VLC starts reading metadata

            # --- NEW: get duration and clamp resume position ---
            duration = self._get_duration()
            RESUME_END_THRESHOLD_SECONDS = 10
            
            if duration > 0:
                remaining = duration - start_position
            
                if remaining <= RESUME_END_THRESHOLD_SECONDS:
                    logger.info(
                        f"Only {remaining:.1f}s left in episode → starting from beginning"
                    )
                    start_position = 0.0
                    self._last_position = 0.0
            # ---------------------------------------------------

            # Apply final seek target
            if start_position > 0:
                self.seek(start_position)

            # Start position tracking
            if self.position_callback:
                self._start_position_tracking()

            logger.debug("Playback started successfully")

        except Exception as e:
            logger.error(f"Failed to start VLC playback: {e}")
            self.stop()

    def pause(self):
        """Pause playback."""
        if self.player and not self._is_paused:
            self.player.pause()
            self._is_paused = True
            logger.debug("Playback paused")

    def resume(self):
        """Resume playback."""
        if self.player and self._is_paused:
            self.player.pause()  # VLC toggles pause
            self._is_paused = False
            logger.debug("Playback resumed")

    def stop(self):
        """Stop playback completely and stop tracking threads."""
        # Stop tracking thread
        if self._position_thread:
            self._stop_tracking.set()
            self._position_thread.join(timeout=1)
            self._position_thread = None

        # Stop VLC player
        if self.player:
            try:
                self.player.stop()
            except Exception as e:
                logger.error(f"Error stopping VLC: {e}")

        # Reset state
        self.player = None
        self.media = None
        self.current_file = None
        self._is_paused = False

        logger.debug("Playback stopped")

    # ----------------------------------------------
    # Position / seeking
    # ----------------------------------------------

    def get_position(self) -> float:
        """Return current playback position in seconds."""
        if not self.player:
            return self._last_position

        try:
            ms = self.player.get_time()
            if ms < 0:
                return self._last_position

            self._last_position = ms / 1000.0
            return self._last_position
        except Exception:
            return self._last_position

    def seek(self, seconds: float):
        """Seek to position in seconds."""
        if not self.player:
            return
        try:
            self.player.set_time(int(seconds * 1000))
            self._last_position = seconds
        except Exception as e:
            logger.error(f"Failed to seek: {e}")

    def is_playing(self) -> bool:
        """Return True if VLC reports playback active."""
        return self.player is not None and self.player.is_playing()

    # ----------------------------------------------
    # Position tracking
    # ----------------------------------------------

    def _start_position_tracking(self):
        """Start background position tracking thread."""
        self._stop_tracking.clear()
        self._position_thread = threading.Thread(
            target=self._track_position, daemon=True
        )
        self._position_thread.start()
        logger.debug("Position tracking started")

    def _track_position(self):
        """Every few seconds, send the latest position to the callback."""
        while not self._stop_tracking.wait(self.save_interval):
            if self.player and not self._is_paused:
                self._update_position()

    def _update_position(self):
        """Call the user-provided callback with the current position."""
        if self.position_callback and self.current_file:
            try:
                pos = self.get_position()
                self.position_callback(pos)
            except Exception as e:
                logger.error(f"Error updating position: {e}")

    # ----------------------------------------------
    # Cleanup
    # ----------------------------------------------

    def cleanup(self):
        """Stop playback and release resources."""
        self.stop()
        logger.debug("Audio player cleanup complete")
