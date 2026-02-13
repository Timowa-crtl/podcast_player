"""Audio playback using python-vlc with position tracking."""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import vlc

from utils import log

RESUME_END_THRESHOLD = 10  # seconds from end to restart from beginning


class AudioPlayer:
    """VLC-based audio player with position tracking."""

    def __init__(self, position_callback: Optional[Callable] = None, save_interval: int = 5):
        self.position_callback = position_callback
        self.save_interval = save_interval

        self.instance = vlc.Instance("--aout=alsa")
        self.player: Optional[vlc.MediaPlayer] = None
        self.current_file: Optional[str] = None
        self._last_position = 0.0
        self._is_paused = False

        self._stop_tracking = threading.Event()
        self._track_thread: Optional[threading.Thread] = None
        self._end_reached = threading.Event()

    def _get_duration(self, timeout=2.0) -> float:
        """Get media duration, waiting briefly for VLC to parse."""
        if not self.player:
            return 0.0
        deadline = time.time() + timeout
        while time.time() < deadline:
            dur = self.player.get_length()
            if dur > 0:
                return dur / 1000.0
            time.sleep(0.05)
        return 0.0

    def play(self, file_path: str, start_position: float = 0.0):
        """Start playing audio file from position."""
        self.stop()

        if not Path(file_path).exists():
            log("ERROR", f"File not found: {file_path}")
            return

        self.current_file = file_path
        self._last_position = start_position
        self._is_paused = False
        self._end_reached.clear()

        try:
            self.player = self.instance.media_player_new()
            self.player.set_media(self.instance.media_new(file_path))

            # Attach end-of-media event
            events = self.player.event_manager()
            events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end)

            self.player.play()
            time.sleep(0.1)

            # Check if near end, restart if so
            duration = self._get_duration()
            if duration > 0 and (duration - start_position) <= RESUME_END_THRESHOLD:
                log("INFO", f"Near end ({duration - start_position:.1f}s left) → starting from beginning")
                start_position = 0.0
                self._last_position = 0.0

            if start_position > 0:
                self.seek(start_position)

            # Start position tracking
            if self.position_callback:
                self._stop_tracking.clear()
                self._track_thread = threading.Thread(target=self._track_position, daemon=True)
                self._track_thread.start()

        except Exception as e:
            log("ERROR", f"Playback failed: {e}")
            self.stop()

    def _on_media_end(self, event):
        """Called by VLC when media reaches end. Runs in VLC thread."""
        self._end_reached.set()

    def has_ended(self) -> bool:
        """Check if current media reached end. Clears the flag."""
        if self._end_reached.is_set():
            self._end_reached.clear()
            return True
        return False

    def pause(self):
        """Pause playback."""
        if self.player and not self._is_paused:
            self.player.pause()
            self._is_paused = True
            log("DEBUG", "VLC paused")

    def resume(self):
        """Resume playback."""
        if self.player and self._is_paused:
            self.player.pause()  # VLC toggles
            self._is_paused = False
            log("DEBUG", "VLC resumed")

    def stop(self):
        """Stop playback and tracking thread."""
        self._stop_tracking.set()
        self._end_reached.clear()
        if self._track_thread:
            self._track_thread.join(timeout=1)
            self._track_thread = None

        if self.player:
            try:
                self.player.stop()
            except:
                pass
            self.player = None

        self.current_file = None
        self._is_paused = False

    def get_position(self) -> float:
        """Get current position in seconds."""
        if self.player:
            ms = self.player.get_time()
            if ms >= 0:
                self._last_position = ms / 1000.0
        return self._last_position

    def seek(self, seconds: float):
        if self.player:
            self.player.set_time(int(seconds * 1000))
            self._last_position = seconds

    def is_playing(self) -> bool:
        """Return True if actively playing (not paused, not stopped)."""
        return self.player is not None and not self._is_paused and self.player.is_playing()

    def is_active(self) -> bool:
        """Return True if player has media loaded (playing or paused)."""
        return self.player is not None and self.current_file is not None

    def _track_position(self):
        """Background thread: periodically call position callback."""
        while not self._stop_tracking.wait(self.save_interval):
            if self.player and self.position_callback and self.current_file and not self._is_paused:
                try:
                    self.position_callback(self.get_position())
                except Exception as e:
                    log("ERROR", f"Position callback error: {e}")

    def cleanup(self):
        self.stop()