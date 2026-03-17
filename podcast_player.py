"""Main podcast player controller coordinating all components."""

import time
from datetime import datetime

import schedule

from audio_player import AudioPlayer
from config import Config
from eink_display import EinkDisplay
from hardware import HardwareController, SwitchState
from led_controller import LEDController, LEDState
from music_manager import MusicManager
from podcast_manager import PodcastManager
from state_manager import StateManager
from utils import log, set_led_controller

# How often to refresh the e-ink progress bar during playback (seconds)
DISPLAY_UPDATE_INTERVAL = 30


class PodcastPlayer:
    """Main controller for the podcast player system."""

    def __init__(self, config: Config, skip_initial_check: bool = False):
        self.config = config
        self.skip_initial_check = skip_initial_check

        log("INFO", "Initializing components...")
        self.led = LEDController()
        set_led_controller(self.led)

        self.state = StateManager()
        self.podcast_manager = PodcastManager(config)
        self.music_manager = MusicManager()
        self.audio = AudioPlayer(
            position_callback=self._save_position,
            save_interval=config.position_save_interval,
        )
        self.hardware = HardwareController()
        self.display = EinkDisplay()

        # Podcast state
        self.current_podcast_id = None
        self.current_episode_index = None

        # Music state
        self.current_music_id = None
        self.current_music_album_path = None
        self.current_music_tracks = None
        self.current_music_track_index = None

        # Shared state
        self.current_mode = SwitchState.PAUSED
        self.current_podcast_index = None

        # Display timing
        self._last_display_update = 0.0

        log("INFO", "Initialization complete")

    def _is_music_mode(self) -> bool:
        return self.current_mode == SwitchState.MUSIC_MODE

    # --- Display helpers ---

    def _update_display(self):
        """Redraw the e-ink display with current state."""
        if not self.display.available:
            return

        try:
            if self._is_music_mode():
                self._update_display_music()
            elif self.current_mode == SwitchState.PLAYING:
                self._update_display_podcast()
            elif self.current_mode == SwitchState.PAUSED:
                # Show whichever mode was last active, or blank
                if self.current_music_id is not None:
                    self._update_display_music()
                elif self.current_podcast_id is not None:
                    self._update_display_podcast()
                # else: nothing has played yet, leave display as-is
        except Exception as e:
            log("ERROR", f"Display update failed: {e}")

        self._last_display_update = time.time()

    def _update_display_podcast(self):
        """Draw podcast info on the e-ink display."""
        if self.current_podcast_id is None or self.current_episode_index is None:
            return

        # Get podcast name from config
        idx = int(self.current_podcast_id.split("_")[1]) - 1
        if idx < 0 or idx >= len(self.config.podcasts):
            return
        name = self.config.podcasts[idx]["name"]

        # Get episode info from state
        ps = self.state.get_podcast(self.current_podcast_id)
        if not ps["episodes"] or self.current_episode_index >= len(ps["episodes"]):
            self.display.show(
                name=name,
                title="Error - no episode found",
                progress=0.0,
                knob_position=idx + 1,
                is_playing=False,
                is_completed=False,
                icon="podcast",
            )
            return

        ep = ps["episodes"][self.current_episode_index]
        title = ep.get("title", "Unknown")
        position = ep.get("position", 0.0)
        duration = ep.get("duration", 0.0)
        is_completed = ep.get("ever_completed", False)

        # Use live position if audio is active
        if self.audio.is_active():
            position = self.audio.get_position()

        progress = position / duration if duration > 0 else 0.0

        self.display.show(
            name=name,
            title=title,
            progress=progress,
            knob_position=idx + 1,
            is_playing=self.audio.is_playing(),
            is_completed=is_completed,
            icon="podcast",
        )

    def _update_display_music(self):
        """Draw music info on the e-ink display."""
        if self.current_music_id is None:
            return

        knob_pos = int(self.current_music_id.split("_")[1])
        ms = self.state.get_music(self.current_music_id)

        # Get album display name
        album = self.music_manager.get_album_for_position(knob_pos)
        name = album["name"] if album else f"Album {knob_pos}"

        # Get track info
        tracks = ms.get("tracks", [])
        track_idx = ms.get("current_track", 0)
        position = ms.get("position", 0.0)
        duration = ms.get("current_track_duration", 0.0)
        is_completed = ms.get("ever_completed", False)

        if tracks and track_idx < len(tracks):
            title = tracks[track_idx]
        else:
            title = ""

        # Use live position if audio is active
        if self.audio.is_active():
            position = self.audio.get_position()

        progress = position / duration if duration > 0 else 0.0

        self.display.show(
            name=name,
            title=title,
            progress=progress,
            knob_position=knob_pos,
            is_playing=self.audio.is_playing(),
            is_completed=is_completed,
            icon="music",
        )

    def _update_display_preview(self, knob_position: int):
        """Show a preview of what's at this knob position (while paused)."""
        if not self.display.available:
            return

        if self.current_mode == SwitchState.PAUSED:
            # Guess which mode to preview: if music was last active, preview music
            if self.current_music_id is not None:
                self._preview_album(knob_position)
            else:
                self._preview_podcast(knob_position)

    def _preview_podcast(self, knob_position: int):
        """Show podcast preview while paused."""
        idx = knob_position - 1
        if idx < 0 or idx >= len(self.config.podcasts):
            return

        name = self.config.podcasts[idx]["name"]
        podcast_id = f"podcast_{knob_position}"
        ps = self.state.get_podcast(podcast_id)

        if not ps["episodes"]:
            self.display.show(
                name=name, title="No episodes", progress=0.0,
                knob_position=knob_position, is_playing=False,
                is_completed=False, icon="podcast",
            )
            return

        ep_idx = min(ps.get("current_index", 0), len(ps["episodes"]) - 1)
        ep = ps["episodes"][ep_idx]
        position = ep.get("position", 0.0)
        duration = ep.get("duration", 0.0)
        progress = position / duration if duration > 0 else 0.0

        self.display.show(
            name=name, title=ep.get("title", "Unknown"), progress=progress,
            knob_position=knob_position, is_playing=False,
            is_completed=ep.get("ever_completed", False), icon="podcast",
        )

    def _preview_album(self, knob_position: int):
        """Show album preview while paused."""
        album = self.music_manager.get_album_for_position(knob_position)
        if not album:
            return

        music_id = f"music_{knob_position}"
        ms = self.state.get_music(music_id)
        name = album["name"]

        if not ms:
            self.display.show(
                name=name, title="Not started", progress=0.0,
                knob_position=knob_position, is_playing=False,
                is_completed=False, icon="music",
            )
            return

        tracks = ms.get("tracks", [])
        track_idx = ms.get("current_track", 0)
        title = tracks[track_idx] if track_idx < len(tracks) else ""
        position = ms.get("position", 0.0)
        duration = ms.get("current_track_duration", 0.0)
        progress = position / duration if duration > 0 else 0.0

        self.display.show(
            name=name, title=title, progress=progress,
            knob_position=knob_position, is_playing=False,
            is_completed=ms.get("ever_completed", False), icon="music",
        )

    def _capture_duration(self):
        """Read duration from VLC and store it. Called once right after play().

        VLC needs a moment to parse the file, so _get_duration_internal() polls
        for up to 2 seconds. This blocks briefly but only runs once per
        episode/track — if duration is already in state, it's skipped entirely.
        """
        duration = self.audio._get_duration_internal(timeout=2.0)
        if duration <= 0:
            log("DEBUG", "Could not read duration from VLC")
            return

        if self._is_music_mode():
            if self.current_music_id:
                self.state.update_music_track_duration(self.current_music_id, duration)
                log("DEBUG", f"Music track duration: {duration:.1f}s")
        else:
            if self.current_podcast_id is not None and self.current_episode_index is not None:
                self.state.update_episode_duration(
                    self.current_podcast_id, self.current_episode_index, duration
                )
                log("DEBUG", f"Episode duration: {duration:.1f}s")

    # --- Position saving ---

    def _save_position(self, position: float):
        """Position callback from AudioPlayer. Routes to podcast or music."""
        if self._is_music_mode():
            self._save_music_position(position)
        else:
            self._save_podcast_position(position)

    def _save_podcast_position(self, position: float):
        if self.current_podcast_id is not None and self.current_episode_index is not None:
            self.state.update_position(self.current_podcast_id, self.current_episode_index, position)

    def _save_music_position(self, position: float):
        if self.current_music_id is not None and self.current_music_track_index is not None:
            self.state.update_music_position(self.current_music_id, self.current_music_track_index, position)

    def _save_current_position(self):
        """Save current playback position if audio is active."""
        if self.audio.is_active():
            pos = self.audio.get_position()
            if self._is_music_mode():
                self._save_music_position(pos)
            elif self.current_podcast_id:
                self._save_podcast_position(pos)

    # --- Podcast mode (unchanged logic) ---

    def check_for_new_episodes(self):
        """Check RSS feeds for new episodes."""
        log("INFO", f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new episodes...")
        self.led.set_state(LEDState.REFRESHING)

        updated = 0
        for idx, pc in enumerate(self.config.podcasts):
            podcast_id = f"podcast_{idx + 1}"
            log("INFO", f"Checking: {pc['name']}")

            try:
                episodes = self.podcast_manager.fetch_episodes(pc["rss_url"], count=1)
                if not episodes:
                    log("WARNING", f"No episodes for {pc['name']}")
                    continue
                if self._update_episodes(podcast_id, episodes):
                    updated += 1
            except Exception as e:
                log("ERROR", f"Error checking {pc['name']}: {e}")

        self.state.set_last_check(time.time())
        log("INFO", f"Check complete. Updated {updated} podcast(s).")
        log("INFO", f"Next check in {self.config.check_interval_hours} hours")

        # Restore LED state
        if self.audio.is_playing():
            self.led.set_state(LEDState.PLAYING)
        else:
            self.led.set_state(LEDState.PAUSED)

    def _update_episodes(self, podcast_id: str, episodes: list) -> bool:
        """Update episodes for a podcast. Returns True if updated."""
        ps = self.state.get_podcast(podcast_id)
        existing_guids = {ep["guid"] for ep in ps["episodes"]}
        new_eps = []
        updated = False

        for ep in episodes:
            if ep["guid"] not in existing_guids:
                log("INFO", f"New: {ep['title'][:50]}...")
                self.led.set_state(LEDState.DOWNLOADING)
                filename = self.podcast_manager.download_episode(ep, podcast_id)
                if filename:
                    new_eps.append({"title": ep["title"], "guid": ep["guid"], "file": filename, "position": 0.0, "duration": 0.0})
                    updated = True
            else:
                for existing in ps["episodes"]:
                    if existing["guid"] == ep["guid"]:
                        new_eps.append(existing)
                        break

        if updated:
            ps["episodes"] = new_eps[: self.config.max_episodes]
            keep = [e["file"] for e in ps["episodes"]]
            self.podcast_manager.cleanup_old_episodes(podcast_id, keep)
            self.state.save()

        return updated

    def switch_to_podcast(self, podcast_index: int):
        """Switch to podcast by index (1-12)."""
        if podcast_index < 1 or podcast_index > len(self.config.podcasts):
            log("WARNING", f"Invalid podcast: {podcast_index}")
            return

        podcast_id = f"podcast_{podcast_index}"
        name = self.config.podcasts[podcast_index - 1]["name"]
        log("INFO", f"Switching to podcast {podcast_index}: {name}")

        self.audio.stop()
        ps = self.state.get_podcast(podcast_id)

        if not ps["episodes"]:
            log("WARNING", f"No episodes for {name}")
            self.led.set_state(LEDState.PAUSED)

            # Show "no episode" on display
            self.current_podcast_id = podcast_id
            self.current_podcast_index = podcast_index
            self.current_episode_index = 0
            self.current_music_id = None
            self._update_display()
            return

        ep_idx = min(ps.get("current_index", 0), len(ps["episodes"]) - 1)
        ep = ps["episodes"][ep_idx]
        path = self.podcast_manager.get_episode_path(podcast_id, ep["file"])

        if not path.exists():
            log("ERROR", f"File not found: {path}")
            self.led.set_state(LEDState.PAUSED)
            return

        self.current_podcast_id = podcast_id
        self.current_podcast_index = podcast_index
        self.current_episode_index = ep_idx

        # Clear music state
        self.current_music_id = None
        self.current_music_album_path = None
        self.current_music_tracks = None
        self.current_music_track_index = None

        pos = max(0, ep["position"] - 2)
        log("INFO", f"Playing: {ep['title'][:50]}... at {pos:.1f}s")
        self.audio.play(str(path), pos)

        # Capture duration once (skipped if already stored from a previous play)
        if ep.get("duration", 0.0) <= 0:
            self._capture_duration()

        self.led.set_state(LEDState.PLAYING)
        self._update_display()

    # --- Music mode ---

    def switch_to_album(self, knob_position: int):
        """Switch to album by knob position (1-12)."""
        album = self.music_manager.get_album_for_position(knob_position)
        if not album:
            log("WARNING", f"No album for position {knob_position}")
            self.audio.stop()
            self.led.set_state(LEDState.PAUSED)
            return

        music_id = f"music_{knob_position}"
        log("INFO", f"Switching to album {knob_position}: {album['name']}")

        # Save current position before switching
        self._save_current_position()
        self.audio.stop()

        # Check saved state
        saved = self.state.get_music(music_id)
        folder_changed = saved.get("folder") != album["folder"]

        if saved and not saved.get("completed") and not folder_changed:
            # Resume: use saved track list and position
            tracks = saved.get("tracks", [])
            track_idx = saved.get("current_track", 0)
            position = saved.get("position", 0.0)

            if not tracks:
                # State corrupted, do fresh scan
                tracks = self.music_manager.scan_tracks(album["path"])
                track_idx = 0
                position = 0.0
        else:
            # Fresh start: completed album, new folder, or no saved state
            if saved and saved.get("completed"):
                log("INFO", f"Album completed, restarting from beginning")
                self.state.reset_music(music_id)

            tracks = self.music_manager.scan_tracks(album["path"])
            track_idx = 0
            position = 0.0

        if not tracks:
            log("WARNING", f"No tracks for album: {album['name']}")
            self.led.set_state(LEDState.PAUSED)
            return

        # Clamp track index
        if track_idx >= len(tracks):
            track_idx = 0
            position = 0.0

        # Set music state
        self.current_music_id = music_id
        self.current_music_album_path = album["path"]
        self.current_music_tracks = tracks
        self.current_music_track_index = track_idx

        # Clear podcast state
        self.current_podcast_id = None
        self.current_episode_index = None

        # Save initial state
        self.state.save_music(music_id, album["folder"], tracks, track_idx, position, completed=False)

        # Play the track
        self._play_music_track(track_idx, position)

    def _play_music_track(self, track_idx: int, position: float = 0.0):
        """Play a specific track from the current album."""
        if not self.current_music_tracks or track_idx >= len(self.current_music_tracks):
            log("ERROR", f"Invalid track index: {track_idx}")
            return

        filename = self.current_music_tracks[track_idx]
        track_path = self.music_manager.get_track_path(self.current_music_album_path, filename)

        if not track_path.exists():
            log("WARNING", f"Track file not found: {filename}, skipping")
            self._advance_music_track()
            return

        self.current_music_track_index = track_idx
        total = len(self.current_music_tracks)
        log("INFO", f"Now playing track {track_idx + 1}/{total}: {filename}")

        pos = max(0, position - 2) if position > 0 else 0.0
        self.audio.play(str(track_path), pos)

        # Capture duration once (skipped if already stored from a previous play)
        if self.state.get_music_track_duration(self.current_music_id) <= 0:
            self._capture_duration()

        self.led.set_state(LEDState.PLAYING)
        self._update_display()

    def _advance_music_track(self):
        """Advance to next track, or mark album completed."""
        if not self.current_music_tracks or self.current_music_track_index is None:
            return

        next_idx = self.current_music_track_index + 1

        if next_idx >= len(self.current_music_tracks):
            # Album finished
            log("INFO", "Album finished")
            self.state.mark_music_completed(self.current_music_id)
            self.audio.stop()
            self.led.set_state(LEDState.PAUSED)
            self._update_display()
            return

        # Save state for next track
        self.state.save_music(
            self.current_music_id,
            self.state.get_music(self.current_music_id).get("folder", ""),
            self.current_music_tracks,
            next_idx,
            0.0,
            completed=False,
        )

        self._play_music_track(next_idx)

    def _on_track_ended(self):
        """Called from main loop when audio ends in music mode."""
        log("DEBUG", "Track ended, advancing...")
        self._advance_music_track()

    # --- Shared controls ---

    def pause(self):
        """Pause playback."""
        if self.audio.is_playing():
            self._save_current_position()
            self.audio.pause()
            log("INFO", "Paused")
        self.led.set_state(LEDState.PAUSED)
        self._update_display()

    def handle_switch_change(self, state: SwitchState, podcast_index):
        """Handle mode or podcast/album selection change."""
        mode_changed = state != self.current_mode
        knob_changed = podcast_index != self.current_podcast_index

        if mode_changed:
            log("INFO", f"Mode: {state.value}")

            # Save position before mode change
            self._save_current_position()

            old_mode = self.current_mode
            self.current_mode = state

            if state == SwitchState.PAUSED:
                self.pause()

            elif state == SwitchState.PLAYING:
                # Podcast mode
                self.audio.stop()
                if podcast_index:
                    self.switch_to_podcast(podcast_index)

            elif state == SwitchState.MUSIC_MODE:
                # Music mode
                self.audio.stop()
                if podcast_index:
                    self.switch_to_album(podcast_index)

        elif knob_changed and podcast_index:
            log("INFO", f"Knob selection: {podcast_index}")
            self.current_podcast_index = podcast_index

            if state == SwitchState.PLAYING:
                self.switch_to_podcast(podcast_index)
            elif state == SwitchState.MUSIC_MODE:
                self.switch_to_album(podcast_index)
            elif state == SwitchState.PAUSED:
                # Show preview of the selected position on the display
                self._update_display_preview(podcast_index)

    def run(self):
        """Main event loop."""
        if self.hardware.is_available():
            log("INFO", "✅ Hardware enabled")
            print("Rotary → Select 1-12 | Mode → Podcast/Pause/Music")
        else:
            log("WARNING", "⚠️ Software-only mode (no GPIO)")
        print("=" * 60)

        self.led.startup_test()

        # Clear display on startup (full refresh)
        self.display.clear()

        # Initial episode check (skipped with --skip-check)
        if self.skip_initial_check:
            log("INFO", "Skipping initial episode check (--skip-check)")
        else:
            self.check_for_new_episodes()

        schedule.every(self.config.check_interval_hours).hours.do(self.check_for_new_episodes)

        last_state, last_podcast = self.hardware.read_state()
        self.handle_switch_change(last_state, last_podcast)

        log("INFO", "Ready. Ctrl+C to quit.\n")

        try:
            while True:
                schedule.run_pending()

                # Check for end-of-track in music mode
                if self._is_music_mode() and self.audio.has_ended():
                    self._on_track_ended()

                # Periodic display update for progress bar
                if self.audio.is_playing() and time.time() - self._last_display_update > DISPLAY_UPDATE_INTERVAL:
                    self._update_display()

                state, podcast = self.hardware.read_state()
                if state != last_state or podcast != last_podcast:
                    self.handle_switch_change(state, podcast)
                    last_state, last_podcast = state, podcast

                time.sleep(0.1)
        except KeyboardInterrupt:
            raise

    def cleanup(self):
        """Clean up all resources."""
        log("INFO", "Cleaning up...")
        self._save_current_position()
        self.audio.cleanup()
        self.hardware.cleanup()
        self.led.cleanup()
        self.display.cleanup()
        self.state.save()
        log("INFO", "Cleanup complete")