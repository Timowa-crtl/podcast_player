#!/usr/bin/env python3
import json
import time
import schedule
from pathlib import Path
from datetime import datetime

from state_manager import StateManager
from audio_player import AudioPlayer
from podcast_manager import PodcastManager


# === DEBUG MODE ===
DEBUG_MODE = True  # Set to False to disable debug output


# === KEYBOARD INPUT ===
# Press keys to control: 1=podcast_0, 2=podcast_1, p=pause
import sys
import termios
import tty

def get_key():
    """Get a single keypress (non-blocking)"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

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
            podcast_id = f"podcast_{idx}"
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
        """Handle state change from button press"""
        current_state = self.state_mgr.get_current_state()
        
        if new_state == current_state:
            return  # No change
        
        print(f"\n🔄 State change: {current_state} → {new_state}")
        
        if new_state == "paused":
            self.pause()
        elif new_state in ["podcast_0", "podcast_1"]:
            self.switch_to_podcast(new_state)
    
    def run(self):
        """Main loop"""
        print("🚀 Podcast Player Starting...")
        
        # Initial episode check
        self.check_for_new_episodes()
        
        # Schedule hourly checks
        schedule.every(self.config["check_interval_hours"]).hours.do(self.check_for_new_episodes)
        
        # Start in paused state
        print("\n⏸️  Ready. Press keys to control:")
        print("   1 = Play Podcast 1")
        print("   2 = Play Podcast 2")
        print("   p = Pause")
        print("   q = Quit\n")
        
        try:
            import select
            
            while True:
                # Check schedule
                schedule.run_pending()
                
                # Check for keyboard input (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = get_key()
                    debug_log(f"Key pressed: {repr(key)}")
                    
                    if key == '1':
                        self.handle_state_change("podcast_0")
                    elif key == '2':
                        self.handle_state_change("podcast_1")
                    elif key == 'p':
                        self.handle_state_change("paused")
                    elif key == 'q':
                        print("\n👋 Quitting...")
                        break
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.player.cleanup()
            self.state_mgr.save()


if __name__ == "__main__":
    player = PodcastPlayer()
    player.run()
