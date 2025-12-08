"""
Main podcast player controller.
Coordinates hardware switch input, audio playback, and episode management.
"""

import time
from datetime import datetime
from typing import Optional

import schedule

from audio_player import AudioPlayer
from config import Config
from hardware import HardwareController, SwitchState
from led_controller import LEDController, LEDState
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
        
        # Initialize LED controller first
        self.led = LEDController()
        
        # Connect LED to logger so warnings/errors trigger LEDs
        Logger.set_led_controller(self.led)
        
        self.state = StateManager()
        self.podcast_manager = PodcastManager(config)
        self.audio = AudioPlayer(
            position_callback=self._save_position,
            save_interval=config.position_save_interval
        )
        self.hardware = HardwareController()

        # Playback tracking
        self.current_podcast_id: Optional[str] = None
        self.current_episode_index: Optional[int] = None
        self.current_mode: SwitchState = SwitchState.PAUSED
        self.current_podcast_index: Optional[int] = None

        logger.info("Initialization complete")

    def _save_position(self, position: float):
        """Save current playback position."""
        if self.current_podcast_id and self.current_episode_index is not None:
            self.state.update_position(
                self.current_podcast_id,
                self.current_episode_index,
                position
            )

    def check_for_new_episodes(self):
        """Check RSS feeds for new episodes."""
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new episodes...")
        self.led.set_state(LEDState.REFRESHING)
        
        updated_count = 0

        for idx, podcast_config in enumerate(self.config.podcasts):
            podcast_id = f"podcast_{idx + 1}"
            logger.info(f"Checking: {podcast_config['name']}")
            
            try:
                episodes = self.podcast_manager.fetch_episodes(
                    podcast_config["rss_url"],
                    count=1
                )
                
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
        
        # Return to previous state
        if self.audio.is_playing():
            self.led.set_state(LEDState.PLAYING)
        else:
            self.led.set_state(LEDState.PAUSED)

    def _update_podcast_episodes(self, podcast_id: str, episodes: list) -> bool:
        """Update episodes for a podcast."""
        podcast_state = self.state.get_podcast(podcast_id)
        existing_guids = {ep["guid"] for ep in podcast_state["episodes"]}
        updated = False
        new_episodes = []

        for episode in episodes:
            if episode["guid"] not in existing_guids:
                logger.info(f"New episode: {episode['title'][:50]}...")
                self.led.set_state(LEDState.DOWNLOADING)
                
                filename = self.podcast_manager.download_episode(episode, podcast_id)
                
                if filename:
                    new_episodes.append({
                        "title": episode["title"],
                        "guid": episode["guid"],
                        "file": filename,
                        "position": 0.0
                    })
                    updated = True
            else:
                # Keep existing episode
                for existing in podcast_state["episodes"]:
                    if existing["guid"] == episode["guid"]:
                        new_episodes.append(existing)
                        break

        if updated:
            # Keep only max episodes
            podcast_state["episodes"] = new_episodes[: self.config.max_episodes]
            
            # Clean up old files
            keep_files = [ep["file"] for ep in podcast_state["episodes"]]
            self.podcast_manager.cleanup_old_episodes(podcast_id, keep_files)
            
            self.state.save()

        return updated

    def switch_to_podcast(self, podcast_index: int):
        """Switch to a specific podcast by index (1-12)."""
        podcast_id = f"podcast_{podcast_index}"

        # Check if podcast exists in config
        if podcast_index < 1 or podcast_index > len(self.config.podcasts):
            logger.warning(f"Invalid podcast index: {podcast_index}")
            return

        podcast_name = self.config.podcasts[podcast_index - 1]['name']
        logger.info(f"Switching to podcast {podcast_index}: {podcast_name}")

        # Stop current playback
        self.audio.stop()

        podcast_state = self.state.get_podcast(podcast_id)
        if not podcast_state["episodes"]:
            logger.warning(f"No episodes available for {podcast_name}")
            self.led.set_state(LEDState.PAUSED)
            return

        episode_index = podcast_state.get("current_index", 0)
        if episode_index >= len(podcast_state["episodes"]):
            episode_index = 0
            podcast_state["current_index"] = 0

        episode = podcast_state["episodes"][episode_index]
        file_path = self.podcast_manager.get_episode_path(podcast_id, episode["file"])
        
        if not file_path.exists():
            logger.error(f"Episode file not found: {file_path}")
            self.led.set_state(LEDState.PAUSED)
            return

        self.current_podcast_id = podcast_id
        self.current_podcast_index = podcast_index
        self.current_episode_index = episode_index

        position = max(0, episode["position"] - 2)
        logger.info(f"Playing: {episode['title'][:50]}...")
        logger.info(f"Position: {position:.1f}s")
        
        self.audio.play(str(file_path), position)
        self.led.set_state(LEDState.PLAYING)

    def pause(self):
        """Pause playback."""
        if self.audio.is_playing():
            if self.current_podcast_id:
                position = self.audio.get_position()
                self._save_position(position)
            self.audio.pause()
            logger.info("Playback paused")
        
        # Always set LED to paused state (stops lightshow too)
        self.led.set_state(LEDState.PAUSED)

    def handle_switch_change(self, state: SwitchState, podcast_index: Optional[int]):
        """Handle changes in switch state."""

        # Check if mode changed
        mode_changed = state != self.current_mode

        # Check if podcast selection changed
        podcast_changed = podcast_index != self.current_podcast_index

        if mode_changed:
            logger.info(f"Mode changed to: {state.value}")
            self.current_mode = state

            if state == SwitchState.PAUSED:
                self.pause()

            elif state == SwitchState.PLAYING:
                if podcast_index:
                    self.switch_to_podcast(podcast_index)

            elif state == SwitchState.MUSIC_MODE:
                # Stop any podcast playback first
                if self.audio.is_playing():
                    if self.current_podcast_id:
                        position = self.audio.get_position()
                        self._save_position(position)
                    self.audio.pause()
                
                # Start lightshow
                self.led.set_state(LEDState.MUSIC_MODE)
                logger.info("Music mode - Lightshow active!")

        elif podcast_changed and podcast_index:
            # Podcast selection changed while in same mode
            logger.info(f"Podcast selection changed to: {podcast_index}")

            if state == SwitchState.PLAYING:
                # If we're playing, switch to the new podcast immediately
                self.switch_to_podcast(podcast_index)
            else:
                # Just remember the selection for when we switch to play mode
                self.current_podcast_index = podcast_index

    def run(self):
        """Main run loop."""
        if self.hardware.is_available():
            logger.info("✅ Hardware control enabled")
            print("Rotary switch → Podcast select 1–12")
            print("3-position mode → Play / Pause / Music")
        else:
            logger.warning("⚠️  Running in software-only mode (no GPIO)")

        print("=" * 60)

        # Startup LED test
        self.led.startup_test()

        # Initial episode check
        self.check_for_new_episodes()
        schedule.every(self.config.check_interval_hours).hours.do(
            self.check_for_new_episodes
        )

        # Apply initial switch state
        last_state, last_podcast = self.hardware.read_state()
        self.handle_switch_change(last_state, last_podcast)

        logger.info("Ready. Press Ctrl+C to quit.\n")
        
        try:
            while True:
                schedule.run_pending()
                current_state, current_podcast = self.hardware.read_state()

                # Check if anything changed
                if current_state != last_state or current_podcast != last_podcast:
                    self.handle_switch_change(current_state, current_podcast)
                    last_state = current_state
                    last_podcast = current_podcast

                time.sleep(0.1)
                
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            raise

    def cleanup(self):
        """Clean up all resources."""
        logger.info("Cleaning up resources...")
        
        if self.current_podcast_id:
            position = self.audio.get_position()
            self._save_position(position)
            
        self.audio.cleanup()
        self.hardware.cleanup()
        self.led.cleanup()
        self.state.save()
        
        logger.info("Cleanup complete")
