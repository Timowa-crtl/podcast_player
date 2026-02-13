"""Music album management: discovery, track scanning, config reading."""

import json
import re
from pathlib import Path
from typing import Optional

from utils import log


def natural_sort_key(s: str):
    """Sort key for natural/numeric ordering: '2-foo' before '10-bar'."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


class MusicManager:
    """Manages album discovery and track listing for music mode."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path

    def _read_music_config(self) -> dict:
        """Read music config fresh from config.json. Called on every knob selection."""
        try:
            with open(self.config_path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log("ERROR", f"Failed to read config: {e}")
            return {"music_dir": str(Path.home() / "music"), "albums": []}

        music_dir = data.get("music_dir", str(Path.home() / "music"))
        albums = data.get("albums", [])
        return {"music_dir": music_dir, "albums": albums}

    def get_album_for_position(self, position: int) -> Optional[dict]:
        """Get album info for knob position (1-12). Re-reads config each time.

        Returns dict with keys: folder, name, path  — or None if not mapped.
        """
        if position < 1 or position > 12:
            log("WARNING", f"Invalid album position: {position}")
            return None

        config = self._read_music_config()
        music_dir = Path(config["music_dir"])
        albums = config["albums"]

        if albums:
            # Configured albums: position maps to list index
            idx = position - 1
            if idx >= len(albums):
                log("WARNING", f"No album configured for position {position}")
                return None

            entry = albums[idx]
            folder = entry.get("folder", "")
            name = entry.get("name", folder)
            path = music_dir / folder

        else:
            # Fallback: auto-discover first 12 folders alphabetically
            if not music_dir.is_dir():
                log("WARNING", f"Music directory not found: {music_dir}")
                return None

            folders = sorted(
                [d.name for d in music_dir.iterdir() if d.is_dir()],
                key=natural_sort_key,
            )

            idx = position - 1
            if idx >= len(folders):
                log("WARNING", f"No album folder for position {position} (only {len(folders)} found)")
                return None

            folder = folders[idx]
            name = folder
            path = music_dir / folder

        if not path.is_dir():
            log("WARNING", f"Album folder not found: {path}")
            return None

        return {"folder": folder, "name": name, "path": str(path)}

    def scan_tracks(self, album_path: str) -> list:
        """Scan album folder for mp3 files, natural sorted. Top-level only."""
        path = Path(album_path)
        if not path.is_dir():
            log("WARNING", f"Cannot scan, not a directory: {path}")
            return []

        tracks = sorted(
            [f.name for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"],
            key=natural_sort_key,
        )

        if not tracks:
            log("WARNING", f"No mp3 files found in: {path}")

        return tracks

    def get_track_path(self, album_path: str, filename: str) -> Path:
        """Get full path to a track file."""
        return Path(album_path) / filename

    def get_all_albums_info(self) -> list:
        """Get info for all configured/discovered albums. Used by status display."""
        config = self._read_music_config()
        music_dir = Path(config["music_dir"])
        albums = config["albums"]
        result = []

        if albums:
            for i, entry in enumerate(albums[:12]):
                folder = entry.get("folder", "")
                name = entry.get("name", folder)
                path = music_dir / folder
                result.append(
                    {
                        "position": i + 1,
                        "folder": folder,
                        "name": name,
                        "path": str(path),
                        "exists": path.is_dir(),
                    }
                )
        else:
            if music_dir.is_dir():
                folders = sorted(
                    [d.name for d in music_dir.iterdir() if d.is_dir()],
                    key=natural_sort_key,
                )
                for i, folder in enumerate(folders[:12]):
                    path = music_dir / folder
                    result.append(
                        {
                            "position": i + 1,
                            "folder": folder,
                            "name": folder,
                            "path": str(path),
                            "exists": True,
                        }
                    )

        return result
