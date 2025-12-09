"""Configuration loader with validation."""

import json
from pathlib import Path

DEFAULTS = {
    "episodes_dir": "episodes",
    "max_episodes_per_podcast": 2,
    "check_interval_hours": 1,
    "debug_mode": False,
    "position_save_interval": 5,
    "download_timeout": 30,
    "rss_timeout": 10,
}


class Config:
    """Load and validate configuration from JSON file."""

    def __init__(self, config_file: str = "config.json"):
        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")

        with open(path) as f:
            self._data = {**DEFAULTS, **json.load(f)}

        self._validate()

    def _validate(self):
        if "podcasts" not in self._data or not self._data["podcasts"]:
            raise ValueError("Config must include non-empty 'podcasts' list")
        if len(self._data["podcasts"]) > 12:
            raise ValueError("Maximum 12 podcasts supported")
        for i, p in enumerate(self._data["podcasts"], 1):
            if "name" not in p or "rss_url" not in p:
                raise ValueError(f"Podcast {i} missing 'name' or 'rss_url'")

    @property
    def podcasts(self):
        return self._data["podcasts"]

    @property
    def episodes_dir(self):
        return self._data["episodes_dir"]

    @property
    def max_episodes(self):
        return self._data["max_episodes_per_podcast"]

    @property
    def check_interval_hours(self):
        return self._data["check_interval_hours"]

    @property
    def debug_mode(self):
        return self._data["debug_mode"]

    @property
    def position_save_interval(self):
        return self._data["position_save_interval"]

    @property
    def download_timeout(self):
        return self._data["download_timeout"]

    @property
    def rss_timeout(self):
        return self._data["rss_timeout"]
