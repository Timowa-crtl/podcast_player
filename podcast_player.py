"""Main podcast player controller coordinating all components."""

import time
from datetime import datetime

import schedule

from audio_player import AudioPlayer
from config import Config
from hardware import HardwareController, SwitchState
from led_controller import LEDController, LEDState
from podcast_manager import PodcastManager
from state_manager import StateManager
from utils import log, set_led_controller


class PodcastPlayer:
    """Main controller for the podcast player system."""

    def __init__(self, config: Config):
        self.config = config

        log("INFO", "Initializing components...")
        self.led = LEDController()
        set_led_controller(self.led)

        self.state = StateManager()
        self.podcast_manager = PodcastManager(config)
        self.audio = AudioPlayer(
            position_callback=self._save_position,
            save_interval=config.position_save_interval,
        )
        self.hardware = HardwareController()

        self.current_podcast_id = None
        self.current_episode_index = None
        self.current_mode = SwitchState.PAUSED
        self.current_podcast_index = None

        log("INFO", "Initialization complete")

    def _save_position(self, position: float):
        if self.current_podcast_id is not None and self.current_episode_index is not None:
            self.state.update_position(self.current_podcast_id, self.current_episode_index, position)

    def _save_current_position(self):
        """Save current playback position if audio is active."""
        if self.current_podcast_id and self.audio.is_active():
            self._save_position(self.audio.get_position())

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
        self.led.set_state(LEDState.PLAYING if self.audio.is_playing() else LEDState.PAUSED)

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
                    new_eps.append({"title": ep["title"], "guid": ep["guid"], "file": filename, "position": 0.0})
                    updated = True
            else:
                # Keep existing
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
        log("INFO", f"Switching to {podcast_index}: {name}")

        self.audio.stop()
        ps = self.state.get_podcast(podcast_id)

        if not ps["episodes"]:
            log("WARNING", f"No episodes for {name}")
            self.led.set_state(LEDState.PAUSED)
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

        pos = max(0, ep["position"] - 2)
        log("INFO", f"Playing: {ep['title'][:50]}... at {pos:.1f}s")
        self.audio.play(str(path), pos)
        self.led.set_state(LEDState.PLAYING)

    def pause(self):
        """Pause playback."""
        if self.audio.is_playing():
            self._save_current_position()
            self.audio.pause()
            log("INFO", "Paused")
        self.led.set_state(LEDState.PAUSED)

    def handle_switch_change(self, state: SwitchState, podcast_index):
        """Handle mode or podcast selection change."""
        mode_changed = state != self.current_mode
        podcast_changed = podcast_index != self.current_podcast_index

        if mode_changed:
            log("INFO", f"Mode: {state.value}")
            self.current_mode = state

            if state == SwitchState.PAUSED:
                self.pause()
            elif state == SwitchState.PLAYING and podcast_index:
                self.switch_to_podcast(podcast_index)
            elif state == SwitchState.MUSIC_MODE:
                self._save_current_position()
                self.audio.stop()
                self.led.set_state(LEDState.MUSIC_MODE)
                log("INFO", "Music mode - Lightshow!")

        elif podcast_changed and podcast_index:
            log("INFO", f"Podcast selection: {podcast_index}")
            if state == SwitchState.PLAYING:
                self.switch_to_podcast(podcast_index)
            else:
                self.current_podcast_index = podcast_index

    def run(self):
        """Main event loop."""
        if self.hardware.is_available():
            log("INFO", "✅ Hardware enabled")
            print("Rotary → Podcast 1-12 | Mode → Play/Pause/Music")
        else:
            log("WARNING", "⚠️ Software-only mode (no GPIO)")
        print("=" * 60)

        self.led.startup_test()
        self.check_for_new_episodes()
        schedule.every(self.config.check_interval_hours).hours.do(self.check_for_new_episodes)

        last_state, last_podcast = self.hardware.read_state()
        self.handle_switch_change(last_state, last_podcast)

        log("INFO", "Ready. Ctrl+C to quit.\n")

        try:
            while True:
                schedule.run_pending()
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
        self.state.save()
        log("INFO", "Cleanup complete")
