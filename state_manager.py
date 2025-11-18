"""
State management module.
Handles persistent storage of playback state and episode metadata.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from utils import Logger

logger = Logger()


class StateManager:
    """
    Manages persistent state for podcast player.
    Stores episode lists, playback positions, and metadata.
    """
    
    def __init__(self, state_file: str = "state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state JSON file
        """
        self.state_file = Path(state_file)
        self.state = self._load_state()
        self._last_save_time = time.time()
    
    def _load_state(self) -> Dict[str, Any]:
        """
        Load state from JSON file.
        
        Returns:
            State dictionary
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.debug(f"Loaded state from {self.state_file}")
                    return self._validate_state(state)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in state file: {e}")
                logger.info("Creating new state file")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
        
        # Return default state
        return self._create_default_state()
    
    def _validate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and fix state structure.
        
        Args:
            state: State dictionary to validate
            
        Returns:
            Valid state dictionary
        """
        # Ensure required keys exist
        if 'podcasts' not in state:
            state['podcasts'] = {}
        if 'last_check' not in state:
            state['last_check'] = 0
        if 'version' not in state:
            state['version'] = 2
        
        # Validate podcast entries
        for podcast_id, podcast_data in state['podcasts'].items():
            if 'episodes' not in podcast_data:
                podcast_data['episodes'] = []
            if 'current_index' not in podcast_data:
                podcast_data['current_index'] = 0
            
            # Validate episodes
            for episode in podcast_data['episodes']:
                if 'position' not in episode:
                    episode['position'] = 0.0
                if 'title' not in episode:
                    episode['title'] = "Unknown"
                if 'guid' not in episode:
                    episode['guid'] = ""
                if 'file' not in episode:
                    episode['file'] = ""
        
        return state
    
    def _create_default_state(self) -> Dict[str, Any]:
        """
        Create default empty state.
        
        Returns:
            Default state dictionary
        """
        return {
            'version': 2,
            'podcasts': {},
            'last_check': 0,
            'created': datetime.now().isoformat()
        }
    
    def save(self, force: bool = False):
        """
        Save state to JSON file.
        
        Args:
            force: Force save even if recently saved
        """
        # Throttle saves (unless forced)
        if not force:
            if time.time() - self._last_save_time < 1.0:
                return
        
        try:
            # Add metadata
            self.state['last_saved'] = datetime.now().isoformat()
            
            # Write to temporary file first
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self.state_file)
            
            self._last_save_time = time.time()
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def get_podcast(self, podcast_id: str) -> Dict[str, Any]:
        """
        Get podcast state, creating if needed.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            Podcast state dictionary
        """
        if podcast_id not in self.state['podcasts']:
            self.state['podcasts'][podcast_id] = {
                'episodes': [],
                'current_index': 0,
                'total_time': 0,
                'created': datetime.now().isoformat()
            }
            self.save()
        
        return self.state['podcasts'][podcast_id]
    
    def update_position(self, podcast_id: str, episode_index: int, 
                       position: float):
        """
        Update playback position for episode.
        
        Args:
            podcast_id: Podcast identifier
            episode_index: Index of episode in list
            position: Playback position in seconds
        """
        podcast = self.get_podcast(podcast_id)
        
        if 0 <= episode_index < len(podcast['episodes']):
            podcast['episodes'][episode_index]['position'] = position
            podcast['episodes'][episode_index]['last_played'] = datetime.now().isoformat()
            
            # Update total listening time
            if 'total_time' not in podcast:
                podcast['total_time'] = 0
            podcast['total_time'] += 1  # Rough estimate
            
            self.save()
        else:
            logger.warning(f"Invalid episode index: {episode_index}")
    
    def set_last_check(self, timestamp: float):
        """
        Update last RSS check timestamp.
        
        Args:
            timestamp: Unix timestamp
        """
        self.state['last_check'] = timestamp
        self.state['last_check_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        self.save(force=True)
    
    def get_last_check(self) -> float:
        """
        Get last RSS check timestamp.
        
        Returns:
            Unix timestamp of last check
        """
        return self.state.get('last_check', 0)
    
    def mark_episode_completed(self, podcast_id: str, episode_index: int):
        """
        Mark episode as completed.
        
        Args:
            podcast_id: Podcast identifier
            episode_index: Index of episode
        """
        podcast = self.get_podcast(podcast_id)
        
        if 0 <= episode_index < len(podcast['episodes']):
            podcast['episodes'][episode_index]['completed'] = True
            podcast['episodes'][episode_index]['completed_at'] = datetime.now().isoformat()
            
            # Move to next episode
            if episode_index + 1 < len(podcast['episodes']):
                podcast['current_index'] = episode_index + 1
            
            self.save(force=True)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get listening statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_podcasts': len(self.state['podcasts']),
            'total_episodes': 0,
            'total_time_hours': 0,
            'last_check': self.state.get('last_check_iso', 'Never')
        }
        
        for podcast_data in self.state['podcasts'].values():
            stats['total_episodes'] += len(podcast_data['episodes'])
            stats['total_time_hours'] += podcast_data.get('total_time', 0) / 3600
        
        return stats
    
    def export_state(self) -> str:
        """
        Export state as formatted JSON string.
        
        Returns:
            Formatted JSON string
        """
        return json.dumps(self.state, indent=2, default=str)
    
    def cleanup(self):
        """Ensure state is saved on cleanup."""
        self.save(force=True)
        logger.debug("State manager cleanup complete")
