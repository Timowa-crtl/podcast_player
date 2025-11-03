"""
Podcast management module.
Handles RSS feed parsing, episode downloading, and file management.
"""

import requests
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from utils import Logger

logger = Logger()


class PodcastManager:
    """
    Manages podcast episodes including fetching, downloading, and cleanup.
    """
    
    def __init__(self, config):
        """
        Initialize podcast manager.
        
        Args:
            config: Application configuration object
        """
        self.config = config
        self.episodes_dir = Path(config.episodes_dir)
        self.episodes_dir.mkdir(exist_ok=True)
        
        logger.debug(f"Episodes directory: {self.episodes_dir}")
    
    def get_podcast_dir(self, podcast_id: str) -> Path:
        """
        Get directory for specific podcast.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            Path to podcast directory
        """
        podcast_dir = self.episodes_dir / podcast_id
        podcast_dir.mkdir(exist_ok=True)
        return podcast_dir
    
    def fetch_episodes(self, rss_url: str, count: int = 2) -> List[Dict]:
        """
        Fetch latest episodes from RSS feed.
        
        Args:
            rss_url: RSS feed URL
            count: Number of episodes to fetch
            
        Returns:
            List of episode dictionaries
        """
        episodes = []
        
        try:
            logger.debug(f"Fetching RSS: {rss_url[:50]}...")
            
            # Download RSS feed
            response = requests.get(
                rss_url, 
                timeout=self.config.rss_timeout,
                headers={'User-Agent': 'PodcastPlayer/1.0'}
            )
            response.raise_for_status()
            
            logger.debug(f"RSS downloaded: {len(response.content)} bytes")
            
            # Parse XML
            episodes = self._parse_rss(response.content, count)
            
            logger.debug(f"Parsed {len(episodes)} episodes")
            
        except requests.Timeout:
            logger.warning(f"RSS fetch timeout ({self.config.rss_timeout}s)")
        except requests.RequestException as e:
            logger.error(f"RSS fetch error: {e}")
        except ET.ParseError as e:
            logger.error(f"RSS parse error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching RSS: {e}")
        
        return episodes
    
    def _parse_rss(self, xml_content: bytes, count: int) -> List[Dict]:
        """
        Parse RSS XML content.
        
        Args:
            xml_content: Raw XML content
            count: Maximum episodes to extract
            
        Returns:
            List of episode dictionaries
        """
        episodes = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find all items (episodes)
            # Try different RSS formats
            items = root.findall('.//item')
            if not items:
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            logger.debug(f"Found {len(items)} items in RSS")
            
            # Extract episode information
            for item in items[:count]:
                episode = self._extract_episode_info(item)
                if episode:
                    episodes.append(episode)
                    if len(episodes) >= count:
                        break
        
        except Exception as e:
            logger.error(f"Error parsing RSS: {e}")
        
        return episodes
    
    def _extract_episode_info(self, item: ET.Element) -> Optional[Dict]:
        """
        Extract episode information from RSS item.
        
        Args:
            item: XML element for episode
            
        Returns:
            Episode dictionary or None if invalid
        """
        try:
            # Extract title
            title_elem = item.find('title')
            if title_elem is None:
                title_elem = item.find('{http://www.w3.org/2005/Atom}title')
            
            title = title_elem.text if title_elem is not None else "Unknown Episode"
            
            # Extract audio URL from enclosure
            enclosure = item.find('enclosure')
            if enclosure is None:
                enclosure = item.find('{http://www.w3.org/2005/Atom}link[@rel="enclosure"]')
            
            if enclosure is None:
                logger.debug(f"No enclosure found for: {title}")
                return None
            
            url = enclosure.get('url') or enclosure.get('href')
            if not url:
                logger.debug(f"No URL in enclosure for: {title}")
                return None
            
            # Extract GUID (unique identifier)
            guid_elem = item.find('guid')
            if guid_elem is None:
                guid_elem = item.find('{http://www.w3.org/2005/Atom}id')
            
            guid = guid_elem.text if guid_elem is not None else url
            
            # Clean up title
            title = self._clean_title(title)
            
            return {
                'title': title,
                'url': url,
                'guid': guid
            }
            
        except Exception as e:
            logger.error(f"Error extracting episode info: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """
        Clean up episode title.
        
        Args:
            title: Raw title string
            
        Returns:
            Cleaned title
        """
        if not title:
            return "Unknown Episode"
        
        # Remove excessive whitespace
        title = ' '.join(title.split())
        
        # Limit length
        if len(title) > 100:
            title = title[:97] + "..."
        
        return title
    
    def download_episode(self, episode: Dict, podcast_id: str) -> Optional[str]:
        """
        Download episode audio file.
        
        Args:
            episode: Episode information
            podcast_id: Podcast identifier
            
        Returns:
            Filename on success, None on failure
        """
        try:
            # Generate filename
            filename = self._generate_filename(episode['guid'])
            podcast_dir = self.get_podcast_dir(podcast_id)
            filepath = podcast_dir / filename
            
            # Check if already downloaded
            if filepath.exists():
                logger.info(f"Already exists: {episode['title'][:50]}")
                return filename
            
            # Download file
            logger.info(f"Downloading: {episode['title'][:50]}...")
            
            response = requests.get(
                episode['url'],
                stream=True,
                timeout=self.config.download_timeout,
                headers={'User-Agent': 'PodcastPlayer/1.0'}
            )
            response.raise_for_status()
            
            # Save to file
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Progress indicator
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if percent % 10 < 0.1:  # Log every 10%
                                logger.debug(f"Download progress: {percent:.0f}%")
            
            logger.info(f"Downloaded: {filename} ({downloaded / 1024 / 1024:.1f} MB)")
            return filename
            
        except requests.Timeout:
            logger.error(f"Download timeout ({self.config.download_timeout}s)")
        except requests.RequestException as e:
            logger.error(f"Download error: {e}")
        except IOError as e:
            logger.error(f"File write error: {e}")
        except Exception as e:
            logger.error(f"Unexpected download error: {e}")
        
        # Clean up partial download
        if filepath and filepath.exists():
            try:
                filepath.unlink()
                logger.debug("Removed partial download")
            except:
                pass
        
        return None
    
    def _generate_filename(self, guid: str) -> str:
        """
        Generate safe filename from GUID.
        
        Args:
            guid: Episode GUID
            
        Returns:
            Safe filename
        """
        # Create hash for consistent filename
        hash_str = hashlib.md5(guid.encode()).hexdigest()[:12]
        return f"episode_{hash_str}.mp3"
    
    def cleanup_old_episodes(self, podcast_id: str, keep_files: List[str]):
        """
        Delete episodes not in keep list.
        
        Args:
            podcast_id: Podcast identifier
            keep_files: List of filenames to keep
        """
        podcast_dir = self.get_podcast_dir(podcast_id)
        
        try:
            for file_path in podcast_dir.iterdir():
                if file_path.is_file() and file_path.name not in keep_files:
                    logger.info(f"Removing old episode: {file_path.name}")
                    file_path.unlink()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_episode_path(self, podcast_id: str, filename: str) -> Path:
        """
        Get full path to episode file.
        
        Args:
            podcast_id: Podcast identifier
            filename: Episode filename
            
        Returns:
            Full path to episode
        """
        return self.get_podcast_dir(podcast_id) / filename
    
    def get_storage_info(self) -> Dict:
        """
        Get storage usage information.
        
        Returns:
            Dictionary with storage statistics
        """
        total_size = 0
        episode_count = 0
        
        try:
            for podcast_dir in self.episodes_dir.iterdir():
                if podcast_dir.is_dir():
                    for file_path in podcast_dir.iterdir():
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            episode_count += 1
        except Exception as e:
            logger.error(f"Error getting storage info: {e}")
        
        return {
            'total_size_mb': total_size / 1024 / 1024,
            'episode_count': episode_count,
            'episodes_dir': str(self.episodes_dir)
        }
