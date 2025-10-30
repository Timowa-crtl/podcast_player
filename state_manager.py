import json
from pathlib import Path
from typing import Dict, Any


class StateManager:
    def __init__(self, state_file: str = "state.json"):
        self.state_file = Path(state_file)
        self.state = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load state from JSON file or create default state"""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        
        # Default state
        return {
            "podcasts": {},
            "current_state": "paused",  # "podcast_1", "podcast_2", or "paused"
            "last_check": 0
        }
    
    def save(self):
        """Save current state to JSON file"""
        self.state_file.write_text(json.dumps(self.state, indent=2))
    
    def get_podcast(self, podcast_id: str) -> Dict[str, Any]:
        """Get podcast state, create if doesn't exist"""
        if podcast_id not in self.state["podcasts"]:
            self.state["podcasts"][podcast_id] = {
                "episodes": [],
                "current_index": 0
            }
        return self.state["podcasts"][podcast_id]
    
    def set_current_state(self, state: str):
        """Set current playback state"""
        self.state["current_state"] = state
        self.save()
    
    def get_current_state(self) -> str:
        """Get current playback state"""
        return self.state["current_state"]
    
    def update_position(self, podcast_id: str, episode_index: int, position: float):
        """Update playback position for an episode"""
        podcast = self.get_podcast(podcast_id)
        if episode_index < len(podcast["episodes"]):
            podcast["episodes"][episode_index]["position"] = position
            self.save()
    
    def set_last_check(self, timestamp: float):
        """Update last RSS check timestamp"""
        self.state["last_check"] = timestamp
        self.save()
