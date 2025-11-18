"""
Main podcast player controller.
Coordinates hardware switch input, audio playback, and episode management.
"""

import time
from datetime import datetime
from typing import Optional, Tuple

import schedule

from audio_player import AudioPlayer
from config import Config
from hardware import HardwareController, SwitchState
from podcast_manager import PodcastManager
from state_manager import StateManager
from utils import Logger

logger = Logger()


class PodcastPlayer:
    """Main controller for the podcast player system."""

    def __init__(self, config: Config):
        self.config = config

        # Initialize components
        logger.info("Initializing components...")
        self.state = StateManager()
        self.podcast_manager = PodcastManager(config)
        self.audio = AudioPlayer(position_callback=self._save_position, save_interval=config.position_save_interval)
        self.hardware = HardwareController()

        # Playback tracking
        self.current_podcast_id: Optional[str] = None
        self.current_episode_index: Optional[int] = None
        self.last_selected_podcast: Optional[int] = 1  # tracks rotary selection

        logger.info("Initialization complete")

    def _save_position(self, position: float):
        if self.current_podcast_id and self.current_episode_index is not None:
            self.state.update_position(self.current_podcast_id, self.current_episode_index, position)
            logger.debug(f"Saved position: {position:.1f}s")

    def check_for_new_episodes(self):
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new episodes...")
        updated_count = 0

        for idx, podcast_config in enumerate(self.config.podcasts):
            podcast_id = f"podcast_{idx + 1}"
            logger.info(f"Checking: {podcast_config['name']}")
            try:
                episodes = self.podcast_manager.fetch_episodes(podcast_config["rss_url"], count=1)
                if not episodes:
                    logger.warning(f"No episodes found for {podcast_config['name']}")
                    continue

                updated = self._update_podcast_episodes(podcast_id, episodes)
                if updated:
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error checking {podcast_config['name']}: {e}")

        self.state.set_last_check(time.time())
        logger.info(f"Check complete. Updated {updated_count} podcast(s).")
        logger.info(f"Next check in {self.config.check_interval_hours} hours")

    def _update_podcast_episodes(self, podcast_id: str, episodes: list) -> bool:
        podcast_state = self.state.get_podcast(podcast_id)
        existing_guids = {ep["guid"] for ep in podcast_state["episodes"]}
        updated = False
        new_episodes = []

        for episode in episodes:
            if episode["guid"] not in existing_guids:
                logger.info(f"New episode: {episode['title'][:50]}...")
                filename = self.podcast_manager.download_episode(episode, podcast_id)
                if filename:
                    new_episodes.append({"title": episode["title"], "guid": episode["guid"], "file": filename, "position": 0.0})
                    updated = True
            else:
                for existing in podcast_state["episodes"]:
                    if existing["guid"] == episode["guid"]:
                        new_episodes.append(existing)
                        break

        if updated:
            podcast_state["episodes"] = new_episodes[: self.config.max_episodes]
            keep_files = [ep["file"] for ep in podcast_state["episodes"]]
            self.podcast_manager.cleanup_old_episodes(podcast_id, keep_files)
            self.state.save()

        return updated

    def switch_to_podcast(self, podcast_id: str):
        logger.info(f"Switching to {podcast_id}")
        self.audio.stop()

        podcast_state = self.state.get_podcast(podcast_id)
        if not podcast_state["episodes"]:
            logger.warning(f"No episodes available for {podcast_id}")
            return

        episode_index = podcast_state.get("current_index", 0)
        if episode_index >= len(podcast_state["episodes"]):
            episode_index = 0
            podcast_state["current_index"] = 0

        episode = podcast_state["episodes"][episode_index]
        file_path = self.podcast_manager.get_episode_path(podcast_id, episode["file"])
        if not file_path.exists():
            logger.error(f"Episode file not found: {file_path}")
            return

        self.current_podcast_id = podcast_id
        self.current_episode_index = episode_index

        position = max(0, episode["position"] - 2)
        logger.info(f"Playing: {episode['title'][:50]}...")
        logger.info(f"Position: {position:.1f}s")
        self.audio.play(str(file_path), position)

    def pause(self):
        if self.audio.is_playing():
            if self.current_podcast_id:
                position = self.audio.get_position()
                self._save_position(position)
            self.audio.pause()
            logger.info("Playback paused")

    def handle_switch_change(self, state_tuple: Tuple[SwitchState, Optional[int]]):
        state, value = state_tuple
        logger.info(f"Switch changed to: {state.value}, value={value}")

        if state == SwitchState.PAUSED:
            self.pause()
        elif state == SwitchState.PLAYING:
            if self.last_selected_podcast:
                podcast_id = f"podcast_{self.last_selected_podcast}"
                self.switch_to_podcast(podcast_id)
        elif state == SwitchState.MUSIC_MODE:
            logger.info("Music mode selected (not implemented yet)")
        elif state == SwitchState.PODCAST_SELECT:
            self.last_selected_podcast = value
            logger.debug(f"Selected podcast index: {value}")

    def run(self):
        if self.hardware.is_available():
            logger.info("✅ Hardware control enabled")
            print("Rotary switch → Podcast select 1–12")
            print("3-position mode → Play / Pause / Music")
        else:
            logger.warning("⚠️  Running in software-only mode (no GPIO)")

        print("=" * 60)

        # Initial episode check
        self.check_for_new_episodes()
        schedule.every(self.config.check_interval_hours).hours.do(self.check_for_new_episodes)

        # Apply initial switch state
        last_state = self.hardware.read_state()
        self.handle_switch_change(last_state)

        logger.info("Ready. Press Ctrl+C to quit.\n")
        try:
            while True:
                schedule.run_pending()
                current_state = self.hardware.read_state()
                if current_state != last_state:
                    self.handle_switch_change(current_state)
                    last_state = current_state
                time.sleep(0.1)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            raise

    def cleanup(self):
        logger.info("Cleaning up resources...")
        if self.current_podcast_id:
            position = self.audio.get_position()
            self._save_position(position)
        self.audio.cleanup()
        self.hardware.cleanup()
        self.state.save()
        logger.info("Cleanup complete")
