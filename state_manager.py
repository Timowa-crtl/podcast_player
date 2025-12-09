"""Persistent state storage for playback positions and episode metadata."""

import json
import time
from datetime import datetime
from pathlib import Path

from utils import log


class StateManager:
    """Manages persistent JSON state for podcast player."""

    def __init__(self, state_file: str = "state.json"):
        self.state_file = Path(state_file)
        self.state = self._load()
        self._last_save = 0.0

    def _load(self):
        """Load state from file or create default."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                state.setdefault("podcasts", {})
                state.setdefault("last_check", 0)
                return state
            except (json.JSONDecodeError, Exception) as e:
                log("ERROR", f"Error loading state: {e}")
        return {"version": 2, "podcasts": {}, "last_check": 0}

    def save(self, force: bool = False):
        """Save state to file (throttled unless forced)."""
        if not force and time.time() - self._last_save < 1.0:
            return
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
            self._last_save = time.time()
        except Exception as e:
            log("ERROR", f"Failed to save state: {e}")

    def get_podcast(self, podcast_id: str):
        """Get or create podcast state."""
        if podcast_id not in self.state["podcasts"]:
            self.state["podcasts"][podcast_id] = {
                "episodes": [],
                "current_index": 0,
                "total_time": 0,
            }
            self.save()
        return self.state["podcasts"][podcast_id]

    def update_position(self, podcast_id: str, episode_index: int, position: float):
        """Update playback position for episode."""
        podcast = self.get_podcast(podcast_id)
        if 0 <= episode_index < len(podcast["episodes"]):
            podcast["episodes"][episode_index]["position"] = position
            podcast["episodes"][episode_index]["last_played"] = datetime.now().isoformat()
            podcast["total_time"] = podcast.get("total_time", 0) + 1
            self.save()

    def set_last_check(self, timestamp: float):
        """Update last RSS check timestamp."""
        self.state["last_check"] = timestamp
        self.save(force=True)

    def get_last_check(self) -> float:
        return self.state.get("last_check", 0)

    def mark_episode_completed(self, podcast_id: str, episode_index: int):
        """Mark episode complete and advance to next."""
        podcast = self.get_podcast(podcast_id)
        if 0 <= episode_index < len(podcast["episodes"]):
            podcast["episodes"][episode_index]["completed"] = True
            if episode_index + 1 < len(podcast["episodes"]):
                podcast["current_index"] = episode_index + 1
            self.save(force=True)

    def get_statistics(self):
        """Get listening statistics."""
        total_eps = sum(len(p["episodes"]) for p in self.state["podcasts"].values())
        total_time = sum(p.get("total_time", 0) for p in self.state["podcasts"].values())
        last_check = self.state.get("last_check", 0)
        if last_check > 0:
            last_check_str = datetime.fromtimestamp(last_check).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_check_str = "Never"
        return {
            "total_podcasts": len(self.state["podcasts"]),
            "total_episodes": total_eps,
            "total_time_hours": total_time / 3600,
            "last_check": last_check_str,
        }

    def cleanup(self):
        self.save(force=True)
