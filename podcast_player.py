"""
Main podcast player controller.
Coordinates hardware switch input, audio playback, and episode management.
"""

import time
import schedule
from datetime import datetime
from typing import Optional

from config import Config
from state_manager import StateManager
from audio_player import AudioPlayer
from podcast_manager import PodcastManager
from hardware import HardwareController, SwitchState
from utils import Logger

logger = Logger()


class PodcastPlayer:
    """Main controller for the podcast player system."""
    
    def __init__(self, config: Config):
        """
        Initialize the podcast player.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Initialize components
        logger.info("Initializing components...")
        self.state = StateManager()
        self.podcast_manager = PodcastManager(config)
        self.audio = AudioPlayer(
            position_callback=self._save_position,
            save_interval=config.position_save_interval
        )
        self.hardware = HardwareController()
        
        # Current playback state
        self.current_podcast_id: Optional[str] = None
        self.current_episode_index: Optional[int] = None
        
        logger.info("Initialization complete")
    
    def _save_position(self, position: float):
        """
        Callback to save current playback position.
        
        Args:
            position: Current playback position in seconds
        """
        if self.current_podcast_id and self.current_episode_index is not None:
            self.state.update_position(
                self.current_podcast_id, 
                self.current_episode_index, 
                position
            )
            logger.debug(f"Saved position: {position:.1f}s")
    
    def check_for_new_episodes(self):
        """Check all configured podcasts for new episodes."""
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new episodes...")
        
        updated_count = 0
        
        for idx, podcast_config in enumerate(self.config.podcasts):
            podcast_id = f"podcast_{idx + 1}"
            logger.info(f"Checking: {podcast_config['name']}")
            
            try:
                # Fetch latest episodes from RSS
                episodes = self.podcast_manager.fetch_episodes(
                    podcast_config['rss_url'],
                    count=self.config.max_episodes
                )
                
                if not episodes:
                    logger.warning(f"No episodes found for {podcast_config['name']}")
                    continue
                
                # Update podcast state with new episodes
                updated = self._update_podcast_episodes(podcast_id, episodes)
                if updated:
                    updated_count += 1
                
            except Exception as e:
                logger.error(f"Error checking {podcast_config['name']}: {e}")
        
        self.state.set_last_check(time.time())
        logger.info(f"Check complete. Updated {updated_count} podcast(s).")
        logger.info(f"Next check in {self.config.check_interval_hours} hours")
    
    def _update_podcast_episodes(self, podcast_id: str, episodes: list) -> bool:
        """
        Update podcast episodes in state and download new ones.
        
        Args:
            podcast_id: Podcast identifier
            episodes: List of episodes from RSS
            
        Returns:
            True if any updates were made
        """
        podcast_state = self.state.get_podcast(podcast_id)
        existing_guids = {ep['guid'] for ep in podcast_state['episodes']}
        
        updated = False
        new_episodes = []
        
        # Process each episode
        for episode in episodes[:self.config.max_episodes]:
            if episode['guid'] not in existing_guids:
                # New episode - download it
                logger.info(f"New episode: {episode['title'][:50]}...")
                filename = self.podcast_manager.download_episode(episode, podcast_id)
                
                if filename:
                    new_episodes.append({
                        'title': episode['title'],
                        'guid': episode['guid'],
                        'file': filename,
                        'position': 0.0
                    })
                    updated = True
            else:
                # Existing episode - keep it
                for existing in podcast_state['episodes']:
                    if existing['guid'] == episode['guid']:
                        new_episodes.append(existing)
                        break
        
        # Update state if changed
        if updated:
            podcast_state['episodes'] = new_episodes[:self.config.max_episodes]
            
            # Clean up old files
            keep_files = [ep['file'] for ep in podcast_state['episodes']]
            self.podcast_manager.cleanup_old_episodes(podcast_id, keep_files)
            
            self.state.save()
        
        return updated
    
    def switch_to_podcast(self, podcast_id: str):
        """
        Switch playback to specified podcast.
        
        Args:
            podcast_id: Podcast identifier (podcast_1 or podcast_2)
        """
        logger.info(f"Switching to {podcast_id}")
        
        # Stop current playback
        self.audio.stop()
        
        # Get podcast state
        podcast_state = self.state.get_podcast(podcast_id)
        
        if not podcast_state['episodes']:
            logger.warning(f"No episodes available for {podcast_id}")
            return
        
        # Get current episode
        episode_index = podcast_state.get('current_index', 0)
        
        # Ensure index is valid
        if episode_index >= len(podcast_state['episodes']):
            episode_index = 0
            podcast_state['current_index'] = 0
        
        episode = podcast_state['episodes'][episode_index]
        
        # Get file path
        file_path = self.podcast_manager.get_episode_path(podcast_id, episode['file'])
        
        if not file_path.exists():
            logger.error(f"Episode file not found: {file_path}")
            return
        
        # Update tracking
        self.current_podcast_id = podcast_id
        self.current_episode_index = episode_index
        
        # Start playback (with 2-second rewind for context)
        position = max(0, episode['position'] - 2)
        logger.info(f"Playing: {episode['title'][:50]}...")
        logger.info(f"Position: {position:.1f}s")
        
        self.audio.play(str(file_path), position)
    
    def pause(self):
        """Pause current playback."""
        if self.audio.is_playing():
            # Save position before pausing
            if self.current_podcast_id:
                position = self.audio.get_position()
                self._save_position(position)
            
            self.audio.pause()
            logger.info("Playback paused")
    
    def handle_switch_change(self, new_state: SwitchState):
        """
        Handle hardware switch state change.
        
        Args:
            new_state: New switch state
        """
        logger.info(f"Switch changed to: {new_state.value}")
        
        if new_state == SwitchState.PAUSED:
            self.pause()
        elif new_state == SwitchState.PODCAST_1:
            self.switch_to_podcast("podcast_1")
        elif new_state == SwitchState.PODCAST_2:
            self.switch_to_podcast("podcast_2")
    
    def run(self):
        """Main run loop."""
        # Print status
        if self.hardware.is_available():
            logger.info("✅ Hardware control enabled")
            print("   Switch UP     → Podcast 1")
            print("   Switch CENTER → Paused")
            print("   Switch DOWN   → Podcast 2")
        else:
            logger.warning("⚠️  Running in software-only mode (no GPIO)")
        
        print("=" * 60)
        
        # Initial episode check
        self.check_for_new_episodes()
        
        # Schedule periodic checks
        schedule.every(self.config.check_interval_hours).hours.do(
            self.check_for_new_episodes
        )
        
        # Get initial switch state
        last_state = self.hardware.read_state()
        logger.info(f"Initial switch position: {last_state.value}")
        
        # Apply initial state
        if last_state != SwitchState.PAUSED:
            self.handle_switch_change(last_state)
        
        logger.info("Ready. Press Ctrl+C to quit.\n")
        
        # Main loop
        try:
            while True:
                # Run scheduled tasks
                schedule.run_pending()
                
                # Check switch state
                current_state = self.hardware.read_state()
                
                # Handle state changes
                if current_state != last_state:
                    self.handle_switch_change(current_state)
                    last_state = current_state
                
                # Small delay to prevent CPU spinning
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources on shutdown."""
        logger.info("Cleaning up resources...")
        
        # Save final position
        if self.current_podcast_id:
            position = self.audio.get_position()
            self._save_position(position)
        
        # Clean up components
        self.audio.cleanup()
        self.hardware.cleanup()
        self.state.save()
        
        logger.info("Cleanup complete")
