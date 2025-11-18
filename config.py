"""
Configuration module for the podcast player.
Handles loading and validating configuration from JSON file.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


class Config:
    """Manages application configuration with validation."""

    DEFAULT_CONFIG = {"episodes_dir": "episodes", "max_episodes_per_podcast": 2, "check_interval_hours": 1, "debug_mode": False, "position_save_interval": 5, "download_timeout": 30, "rss_timeout": 10}

    def __init__(self, config_file: str = "config.json"):
        """
        Initialize configuration from JSON file.

        Args:
            config_file: Path to configuration file
        """
        self.config_file = Path(config_file)
        self.data = self._load_config()
        self._validate()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        with open(self.config_file, "r") as f:
            config = json.load(f)

        # Merge with defaults
        for key, default_value in self.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = default_value

        return config

    def _validate(self):
        """Validate configuration values."""
        # Check required fields
        if "podcasts" not in self.data:
            raise ValueError("Configuration must include 'podcasts' list")

        if not self.data["podcasts"]:
            raise ValueError("At least one podcast must be configured")

        if len(self.data["podcasts"]) > 12:
            raise ValueError("Maximum 12 podcasts supported (12-position switch)")

        # Validate each podcast
        for i, podcast in enumerate(self.data["podcasts"]):
            if "name" not in podcast:
                raise ValueError(f"Podcast {i+1} missing 'name' field")
            if "rss_url" not in podcast:
                raise ValueError(f"Podcast {i+1} missing 'rss_url' field")

        # Validate numeric values
        if self.data["max_episodes_per_podcast"] < 1:
            raise ValueError("max_episodes_per_podcast must be at least 1")

        if self.data["check_interval_hours"] < 0.1:
            raise ValueError("check_interval_hours must be at least 0.1")

    @property
    def podcasts(self) -> List[Dict[str, str]]:
        """Get podcast configurations."""
        return self.data["podcasts"]

    @property
    def episodes_dir(self) -> str:
        """Get episodes directory path."""
        return self.data["episodes_dir"]

    @property
    def max_episodes(self) -> int:
        """Get maximum episodes per podcast."""
        return self.data["max_episodes_per_podcast"]

    @property
    def check_interval_hours(self) -> float:
        """Get check interval in hours."""
        return self.data["check_interval_hours"]

    @property
    def debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.data["debug_mode"]

    @property
    def position_save_interval(self) -> int:
        """Get position save interval in seconds."""
        return self.data["position_save_interval"]

    @property
    def download_timeout(self) -> int:
        """Get download timeout in seconds."""
        return self.data["download_timeout"]

    @property
    def rss_timeout(self) -> int:
        """Get RSS fetch timeout in seconds."""
        return self.data["rss_timeout"]
