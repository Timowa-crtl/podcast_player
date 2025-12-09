"""Podcast RSS feed parsing and episode downloading."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from utils import log


class PodcastManager:
    """Manages podcast episode fetching, downloading, and cleanup."""

    def __init__(self, config):
        self.config = config
        self.episodes_dir = Path(config.episodes_dir)
        self.episodes_dir.mkdir(exist_ok=True)

    def get_podcast_dir(self, podcast_id: str) -> Path:
        """Get/create directory for podcast."""
        d = self.episodes_dir / podcast_id
        d.mkdir(exist_ok=True)
        return d

    def fetch_episodes(self, rss_url: str, count: int = 1):
        """Fetch latest episodes from RSS feed."""
        try:
            log("DEBUG", f"Fetching RSS: {rss_url[:50]}...")
            resp = requests.get(
                rss_url,
                timeout=self.config.rss_timeout,
                headers={"User-Agent": "PodcastPlayer/1.0"},
            )
            resp.raise_for_status()
            log("DEBUG", f"RSS downloaded: {len(resp.content)} bytes")
            return self._parse_rss(resp.content, count)
        except requests.Timeout:
            log("WARNING", f"RSS timeout ({self.config.rss_timeout}s)")
        except requests.RequestException as e:
            log("ERROR", f"RSS fetch error: {e}")
        except ET.ParseError as e:
            log("ERROR", f"RSS parse error: {e}")
        return []

    def _parse_rss(self, xml_content: bytes, count: int):
        """Parse RSS XML content."""
        episodes = []
        root = ET.fromstring(xml_content)

        # Find all items (episodes) - try different RSS formats
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        log("DEBUG", f"Found {len(items)} items in RSS")

        for item in items[:count]:
            episode = self._extract_episode_info(item)
            if episode:
                episodes.append(episode)
                if len(episodes) >= count:
                    break

        return episodes

    def _extract_episode_info(self, item: ET.Element):
        """Extract episode information from RSS item."""
        try:
            # Extract title
            title_elem = item.find("title")
            if title_elem is None:
                title_elem = item.find("{http://www.w3.org/2005/Atom}title")

            title = title_elem.text if title_elem is not None else "Unknown Episode"

            # Extract audio URL from enclosure
            enclosure = item.find("enclosure")
            if enclosure is None:
                enclosure = item.find('{http://www.w3.org/2005/Atom}link[@rel="enclosure"]')

            if enclosure is None:
                log("DEBUG", f"No enclosure found for: {title}")
                return None

            url = enclosure.get("url") or enclosure.get("href")
            if not url:
                log("DEBUG", f"No URL in enclosure for: {title}")
                return None

            # Extract GUID (unique identifier)
            guid_elem = item.find("guid")
            if guid_elem is None:
                guid_elem = item.find("{http://www.w3.org/2005/Atom}id")

            guid = guid_elem.text if guid_elem is not None else url

            # Clean up title
            if title:
                title = " ".join(title.split())
                if len(title) > 100:
                    title = title[:97] + "..."
            else:
                title = "Unknown Episode"

            return {"title": title, "url": url, "guid": guid}

        except Exception as e:
            log("ERROR", f"Error extracting episode info: {e}")
            return None

    def download_episode(self, episode: dict, podcast_id: str):
        """Download episode audio file. Returns filename or None."""
        filename = f"episode_{hashlib.md5(episode['guid'].encode()).hexdigest()[:12]}.mp3"
        filepath = self.get_podcast_dir(podcast_id) / filename

        if filepath.exists():
            log("INFO", f"Already exists: {episode['title'][:50]}")
            return filename

        log("INFO", f"Downloading: {episode['title'][:50]}...")
        try:
            resp = requests.get(
                episode["url"],
                stream=True,
                timeout=self.config.download_timeout,
                headers={"User-Agent": "PodcastPlayer/1.0"},
            )
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_percent = -1

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if percent // 10 > last_percent:
                                last_percent = percent // 10
                                log("DEBUG", f"Download progress: {int(last_percent * 10)}%")

            size_mb = filepath.stat().st_size / 1024 / 1024
            log("INFO", f"Downloaded: {filename} ({size_mb:.1f} MB)")
            return filename

        except requests.Timeout:
            log("ERROR", f"Download timeout ({self.config.download_timeout}s)")
        except requests.RequestException as e:
            log("ERROR", f"Download error: {e}")
        except IOError as e:
            log("ERROR", f"File write error: {e}")

        # Clean up partial download
        if filepath.exists():
            try:
                filepath.unlink()
                log("DEBUG", "Removed partial download")
            except:
                pass
        return None

    def cleanup_old_episodes(self, podcast_id: str, keep_files: list):
        """Delete episodes not in keep list."""
        try:
            for f in self.get_podcast_dir(podcast_id).iterdir():
                if f.is_file() and f.name not in keep_files:
                    log("INFO", f"Removing old episode: {f.name}")
                    f.unlink()
        except Exception as e:
            log("ERROR", f"Error during cleanup: {e}")

    def get_episode_path(self, podcast_id: str, filename: str) -> Path:
        return self.get_podcast_dir(podcast_id) / filename

    def get_storage_info(self):
        """Get storage usage statistics."""
        total_size, count = 0, 0
        try:
            for pdir in self.episodes_dir.iterdir():
                if pdir.is_dir():
                    for f in pdir.iterdir():
                        if f.is_file():
                            total_size += f.stat().st_size
                            count += 1
        except Exception as e:
            log("ERROR", f"Error getting storage info: {e}")
        return {
            "total_size_mb": total_size / 1024 / 1024,
            "episode_count": count,
            "episodes_dir": str(self.episodes_dir),
        }
