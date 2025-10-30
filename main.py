#!/usr/bin/env python3
import json
import time
import schedule
from pathlib import Path
from datetime import datetime

from state_manager import StateManager
from audio_player import AudioPlayer
from podcast_manager import PodcastManager

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️  RPi.GPIO not available - switch control disabled")


# === DEBUG MODE ===
DEBUG_MODE = True  # Set to False to disable debug output


# === GPIO PIN DEFINITIONS ===
PIN_PODCAST_1 = 17  # Physical Pin 11
PIN_PODCAST_2 = 27  # Physical Pin 13


def debug_log(message):
    """Print debug message with timestamp if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")


class PodcastPlayer:
    def __init__(self, config_file: str = "config.json"):
        # Load config
        with open(config_file) as f:
            self.config = json.load(f)
        
        # Initialize managers
        self.state_mgr = StateManager()
        self.podcast_mgr = PodcastManager(
            self.config["episodes_dir"],
            self.config["max_episodes_per_podcast"]
        )
        self.player = AudioPlayer(position_callback=self._save_position)
        
        # Track current playback
        self.current_podcast_id = None
        self.current_episode_index = None
        
        # Setup GPIO
        if GPIO_AVAILABLE:
            self._setup_gpio()
    
    def _setup_gpio(self):
        """Initialize GPIO pins for switch"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_PODCAST_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_PODCAST_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        debug_log("GPIO initialized (BCM mode)")
        debug_log(f"  GPIO17 (Pin 11) - Pull-up enabled")
        debug_log(f"  GPIO27 (Pin 13) - Pull-up enabled")
    
    def _read_switch_state(self) -> str:
        """Read switch position and return state name"""
        if not GPIO_AVAILABLE:
            return "paused"
        
        pin1 = GPIO.input(PIN_PODCAST_1)  # 1=HIGH, 0=LOW
        pin2 = GPIO.input(PIN_PODCAST_2)
        
        if pin1 == 0 and pin2 == 1:
            return "podcast_1"
        elif pin1 == 1 and pin2 == 0:
            return "podcast_2"
        elif pin1 == 1 and pin2 == 1:
            return "paused"
        else:
            debug_log(f"⚠️  Invalid switch state: GPIO17={pin1}, GPIO27={pin2}")
            return "paused"
    
    def _save_position(self, position: float):
        """Callback to save current playback position"""
        if self.current_podcast_id is not None and self.current_episode_index is not None:
            self.state_mgr.update_position(
                self.current_podcast_id,
                self.current_episode_index,
                position
            )
    
    def check_for_new_episodes(self):
        """Check all podcasts for new episodes and download them"""
        print(f"\n🔍 [{datetime.now().strftime('%H:%M:%S')}] Checking for new episodes...")
        
        for idx, podcast_config in enumerate(self.config["podcasts"]):
            podcast_id = f"podcast_{idx + 1}"
            print(f"\n📻 {podcast_config['name']}")
            
            # Fetch latest episodes from RSS (only check newest 1)
            debug_log("Fetching RSS feed...")
            episodes = self.podcast_mgr.fetch_latest_episodes(
                podcast_config["rss_url"],
                count=1  # Only check newest episode
            )
            debug_log(f"Got {len(episodes)} episodes from RSS")
            
            if not episodes:
                continue
            
            # Get current state
            podcast_state = self.state_mgr.get_podcast(podcast_id)
            existing_guids = {ep["guid"] for ep in podcast_state["episodes"]}
            debug_log(f"Existing GUIDs in state: {len(existing_guids)}")
            
            # Download new episodes
            new_episodes = []
            for episode in episodes:
                debug_log(f"Processing: {episode['title'][:50]}...")
                # Check if episode is new
                if episode["guid"] not in existing_guids:
                    debug_log("New episode detected, downloading...")
                    filename = self.podcast_mgr.download_episode(episode, podcast_id)
                    if filename:
                        new_episodes.append({
                            "title": episode["title"],
                            "guid": episode["guid"],
                            "file": filename,
                            "position": 0.0
                        })
                else:
                    # Episode already exists, keep it
                    debug_log("Episode already in state, keeping...")
                    for existing_ep in podcast_state["episodes"]:
                        if existing_ep["guid"] == episode["guid"]:
                            new_episodes.append(existing_ep)
                            break
            
            # Add older episodes from state (keep up to 2 total)
            for existing_ep in podcast_state["episodes"]:
                if existing_ep["guid"] not in [ep["guid"] for ep in new_episodes]:
                    new_episodes.append(existing_ep)
                    if len(new_episodes) >= self.config["max_episodes_per_podcast"]:
                        break
            
            debug_log(f"Updating state with {len(new_episodes)} episodes")
            # Update state with new episode list (max 2)
            podcast_state["episodes"] = new_episodes[:self.config["max_episodes_per_podcast"]]
            
            # Cleanup old files
            keep_files = [ep["file"] for ep in podcast_state["episodes"]]
            self.podcast_mgr.cleanup_old_episodes(podcast_id, keep_files)
        
        self.state_mgr.set_last_check(time.time())
        print(f"\n✅ [{datetime.now().strftime('%H:%M:%S')}] Check complete. Next check in {self.config['check_interval_hours']}h\n")
    
    def switch_to_podcast(self, podcast_id: str):
        """Switch playback to a specific podcast"""
        debug_log(f"Switching to {podcast_id}")
        
        # Stop current playback
        if self.player.is_playing():
            debug_log("Stopping current playback")
            self.player.stop()
        
        # Get podcast state
        podcast_state = self.state_mgr.get_podcast(podcast_id)
        
        if not podcast_state["episodes"]:
            print(f"⚠️  No episodes available for {podcast_id}")
            return
        
        # Get current episode
        episode_index = podcast_state["current_index"]
        episode = podcast_state["episodes"][episode_index]
        debug_log(f"Loading episode {episode_index}: {episode['title'][:50]}")
        
        # Get file path
        file_path = self.podcast_mgr.get_episode_path(podcast_id, episode["file"])
        
        if not file_path.exists():
            print(f"⚠️  Episode file not found: {file_path}")
            return
        
        # Update tracking
        self.current_podcast_id = podcast_id
        self.current_episode_index = episode_index
        
        # Start playback
        print(f"🎧 Playing: {episode['title']}")
        print(f"   Position: {episode['position']:.1f}s")
        debug_log(f"Starting MPV with file: {file_path}")
        self.player.play(str(file_path), episode["position"])
        
        self.state_mgr.set_current_state(podcast_id)
        debug_log(f"State updated to {podcast_id}")
    
    def pause(self):
        """Pause playback"""
        if self.player.is_playing():
            self.player.pause()
            self.state_mgr.set_current_state("paused")
            print("⏸️  Paused")
    
    def handle_state_change(self, new_state: str):
        """Handle state change from switch"""
        current_state = self.state_mgr.get_current_state()
        
        if new_state == current_state:
            return  # No change
        
        print(f"\n🔄 State change: {current_state} → {new_state}")
        
        if new_state == "paused":
            self.pause()
        elif new_state in ["podcast_1", "podcast_2"]:
            self.switch_to_podcast(new_state)
    
    def run(self):
        """Main loop with GPIO switch polling"""
        print("🚀 Podcast Player Starting...")
        print("=" * 60)
        
        if GPIO_AVAILABLE:
            print("✅ GPIO initialized - switch control enabled")
            print("   Switch UP     → Podcast 1")
            print("   Switch CENTER → Paused")
            print("   Switch DOWN   → Podcast 2")
        else:
            print("⚠️  GPIO not available - running in test mode")
        
        print("=" * 60)
        
        # Initial episode check
        self.check_for_new_episodes()
        
        # Schedule hourly checks
        schedule.every(self.config["check_interval_hours"]).hours.do(self.check_for_new_episodes)
        
        # Start in paused state
        print("\n⏸️  Ready. Use physical switch to control playback.")
        print("   Press Ctrl+C to quit\n")
        
        last_switch_state = None
        
        try:
            while True:
                # Check schedule
                schedule.run_pending()
                
                # Poll switch state
                if GPIO_AVAILABLE:
                    switch_state = self._read_switch_state()
                    
                    # Only act on state changes
                    if switch_state != last_switch_state:
                        debug_log(f"Switch state changed: {last_switch_state} → {switch_state}")
                        self.handle_state_change(switch_state)
                        last_switch_state = switch_state
                
                time.sleep(0.2)  # Poll every 200ms
        
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.player.cleanup()
            self.state_mgr.save()
            if GPIO_AVAILABLE:
                GPIO.cleanup()
                debug_log("GPIO cleanup done")


if __name__ == "__main__":
    player = PodcastPlayer()
    player.run()
