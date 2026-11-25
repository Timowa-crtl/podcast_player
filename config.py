"""Configuration loader with validation."""

import json
import shutil
from pathlib import Path

from utils import log

# Tracked preset; copied to the (gitignored) config.json on first start
DEFAULT_CONFIG_FILE = "config.default.json"

DEFAULTS = {
    "episodes_dir": "episodes",
    "max_episodes_per_podcast": 2,
    "check_interval_hours": 1,
    "debug_mode": False,
    "position_save_interval": 5,
    "download_timeout": 30,
    "rss_timeout": 10,
    "music_dir": str(Path.home() / "music"),
    "albums": [],
    "web_port": 8080,  # web config editor; 0 disables it
}

MAX_SLOTS = 12


def ensure_config(config_file: str = "config.json"):
    """Create config_file from the preset if it does not exist yet."""
    path = Path(config_file)
    default = path.with_name(DEFAULT_CONFIG_FILE)
    if not path.exists() and default.exists():
        shutil.copyfile(default, path)
        log("INFO", f"Created {path} from {default}")


def validate(data: dict):
    """Raise ValueError if podcasts/albums are invalid.

    Slots may be null (empty knob position) so that slot N always maps to
    knob position N.
    """
    podcasts = data.get("podcasts") or []
    if not any(podcasts):
        raise ValueError("Config must include at least one podcast")
    if len(podcasts) > MAX_SLOTS:
        raise ValueError(f"Maximum {MAX_SLOTS} podcasts supported")
    for i, p in enumerate(podcasts, 1):
        if p is None:
            continue
        if not p.get("name") or not p.get("rss_url"):
            raise ValueError(f"Podcast {i} missing 'name' or 'rss_url'")

    albums = data.get("albums") or []
    if len(albums) > MAX_SLOTS:
        raise ValueError(f"Maximum {MAX_SLOTS} albums supported")
    for i, a in enumerate(albums, 1):
        if a is None:
            continue
        if not a.get("folder"):
            raise ValueError(f"Album {i} missing 'folder'")


class Config:
    """Load and validate configuration from JSON file."""

    def __init__(self, config_file: str = "config.json"):
        self.path = Path(config_file)
        ensure_config(config_file)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            raise FileNotFoundError(f"Config not found: {self.path}")
        with open(self.path) as f:
            data = {**DEFAULTS, **json.load(f)}
        validate(data)
        return data

    def reload(self):
        """Re-read the config file. On error the old config is kept and the error raised."""
        self._data = self._load()

    def podcast(self, index: int):
        """Podcast entry for knob position 1-12, or None if the slot is empty."""
        podcasts = self._data["podcasts"]
        if 1 <= index <= len(podcasts):
            return podcasts[index - 1]
        return None

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

    @property
    def music_dir(self):
        return self._data["music_dir"]

    @property
    def albums(self):
        return self._data["albums"]

    @property
    def web_port(self):
        return self._data["web_port"]
