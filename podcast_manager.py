import requests
import feedparser
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from utils import debug_log


class PodcastManager:
    def __init__(self, episodes_dir: str, max_episodes: int = 2):
        self.episodes_dir = Path(episodes_dir)
        self.episodes_dir.mkdir(exist_ok=True)
        self.max_episodes = max_episodes

    def get_podcast_dir(self, podcast_id: str) -> Path:
        """Get directory for a specific podcast"""
        podcast_dir = self.episodes_dir / podcast_id
        podcast_dir.mkdir(exist_ok=True)
        return podcast_dir

    def fetch_latest_episodes(self, rss_url: str, count: int = 2) -> List[Dict]:
        """
        Fetch latest episodes from RSS feed (fast XML parsing)

        Returns list of dicts with: title, url, guid
        """
        try:
            debug_log(f"Requesting RSS from {rss_url[:50]}...")
            response = requests.get(rss_url, timeout=10)
            response.raise_for_status()
            debug_log(f"Downloaded {len(response.content)} bytes")

            # Fast XML parsing - only get what we need
            debug_log("Parsing XML (fast mode)...")
            root = ET.fromstring(response.content)

            episodes = []

            # Find namespace if present
            ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

            # Try RSS 2.0 format first
            items = root.findall(".//item")
            if not items:
                # Try Atom format
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            debug_log(f"Found {len(items)} items, extracting top {count}")

            for item in items[:count]:
                # Extract title
                title_elem = item.find("title")
                if title_elem is None:
                    title_elem = item.find("{http://www.w3.org/2005/Atom}title")
                title = title_elem.text if title_elem is not None else "Unknown"

                # Extract enclosure URL
                enclosure = item.find("enclosure")
                if enclosure is None:
                    enclosure = item.find(
                        '{http://www.w3.org/2005/Atom}link[@rel="enclosure"]'
                    )

                if enclosure is not None:
                    url = enclosure.get("url") or enclosure.get("href")

                    # Extract GUID
                    guid_elem = item.find("guid")
                    if guid_elem is None:
                        guid_elem = item.find("{http://www.w3.org/2005/Atom}id")

                    guid = guid_elem.text if guid_elem is not None else url

                    episodes.append({"title": title, "url": url, "guid": guid})

                    if len(episodes) >= count:
                        break

            debug_log(f"Extracted {len(episodes)} episodes")
            return episodes
        except requests.Timeout:
            print(f"  ⚠️  Timeout fetching RSS (10s limit)")
            return []
        except Exception as e:
            print(f"  ⚠️  Error fetching RSS: {e}")
            return []

    def download_episode(self, episode: Dict, podcast_id: str) -> Optional[str]:
        """
        Download episode and return local filename

        Returns filename on success, None on failure
        """
        try:
            # Generate filename from guid
            filename = self._generate_filename(episode["guid"])
            podcast_dir = self.get_podcast_dir(podcast_id)
            filepath = podcast_dir / filename

            # Skip if already exists
            if filepath.exists():
                print(f"  ✓ Already downloaded: {episode['title']}")
                return filename

            # Download
            print(f"  ⬇️  Downloading: {episode['title']}")
            response = requests.get(episode["url"], stream=True, timeout=30)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  ✅ Downloaded: {filename}")
            return filename

        except Exception as e:
            print(f"  ⚠️  Download failed: {e}")
            return None

    def cleanup_old_episodes(self, podcast_id: str, keep_files: List[str]):
        """
        Delete episodes not in keep_files list

        Args:
            podcast_id: Podcast identifier
            keep_files: List of filenames to keep
        """
        podcast_dir = self.get_podcast_dir(podcast_id)

        for file in podcast_dir.iterdir():
            if file.is_file() and file.name not in keep_files:
                print(f"  🗑️  Deleting old episode: {file.name}")
                file.unlink()

    def get_episode_path(self, podcast_id: str, filename: str) -> Path:
        """Get full path to episode file"""
        return self.get_podcast_dir(podcast_id) / filename

    def _generate_filename(self, guid: str) -> str:
        """Generate safe filename from guid"""
        # Use hash to create consistent, filesystem-safe name
        hash_str = hashlib.md5(guid.encode()).hexdigest()[:12]
        return f"episode_{hash_str}.mp3"
