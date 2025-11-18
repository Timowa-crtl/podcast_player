#!/usr/bin/env python3
"""
Status Display Tool
Shows current player state, episodes, and storage information.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from config import Config
from podcast_manager import PodcastManager
from state_manager import StateManager
from utils import format_duration, format_file_size


def main():
    """Display current status of podcast player."""
    print("=" * 60)
    print("📊 Podcast Player Status")
    print("=" * 60)

    try:
        # Load configuration and state
        config = Config()
        state = StateManager()
        manager = PodcastManager(config)

        # Display configuration
        print("\n📋 Configuration:")
        print(f"   Episodes directory: {config.episodes_dir}")
        print(f"   Max episodes/podcast: {config.max_episodes}")
        print(f"   Check interval: {config.check_interval_hours} hours")
        print(f"   Debug mode: {'Enabled' if config.debug_mode else 'Disabled'}")

        # Display podcasts
        print(f"\n📻 Configured Podcasts ({len(config.podcasts)}):")
        for i, podcast in enumerate(config.podcasts, 1):
            print(f"   {i}. {podcast['name']}")
            print(f"      RSS: {podcast['rss_url'][:50]}...")

        # Display state information
        stats = state.get_statistics()
        print(f"\n📈 Statistics:")
        print(f"   Total episodes: {stats['total_episodes']}")
        print(f"   Listening time: {stats['total_time_hours']:.1f} hours")
        print(f"   Last RSS check: {stats['last_check']}")

        # Display episode details for each podcast
        print("\n📚 Downloaded Episodes:")

        for i, podcast_config in enumerate(config.podcasts):
            podcast_id = f"podcast_{i + 1}"
            podcast_state = state.get_podcast(podcast_id)

            print(f"\n   {podcast_config['name']}:")

            if not podcast_state["episodes"]:
                print("      No episodes downloaded")
            else:
                current_index = podcast_state.get("current_index", 0)

                for j, episode in enumerate(podcast_state["episodes"]):
                    # Get file info
                    file_path = manager.get_episode_path(podcast_id, episode["file"])

                    # Episode status
                    if j == current_index:
                        marker = "▶️"  # Current episode
                    elif episode.get("completed"):
                        marker = "✅"  # Completed
                    else:
                        marker = "  "

                    # Display episode info
                    print(f"      {marker} {j+1}. {episode['title'][:40]}")

                    # Position and file info
                    position = format_duration(episode.get("position", 0))
                    print(f"           Position: {position}")

                    if file_path.exists():
                        size = format_file_size(file_path.stat().st_size)
                        print(f"           File: {episode['file']} ({size})")
                    else:
                        print(f"           File: {episode['file']} (missing)")

                    if "last_played" in episode:
                        print(f"           Last played: {episode['last_played']}")

        # Display storage information
        storage_info = manager.get_storage_info()
        print(f"\n💾 Storage Usage:")
        print(f"   Episodes directory: {storage_info['episodes_dir']}")
        print(f"   Total episodes: {storage_info['episode_count']}")
        print(f"   Total size: {storage_info['total_size_mb']:.1f} MB")

        # Check available disk space
        try:
            import shutil

            stat = shutil.disk_usage(config.episodes_dir)
            free_gb = stat.free / (1024**3)
            total_gb = stat.total / (1024**3)
            used_percent = (stat.used / stat.total) * 100

            print(f"\n💿 Disk Space:")
            print(f"   Free: {free_gb:.1f} GB / {total_gb:.1f} GB")
            print(f"   Used: {used_percent:.1f}%")

            if free_gb < 0.5:
                print("   ⚠️  WARNING: Low disk space!")
        except:
            pass

        # Display state file info
        state_file = Path("state.json")
        if state_file.exists():
            modified = datetime.fromtimestamp(state_file.stat().st_mtime)
            print(f"\n📄 State File:")
            print(f"   Path: {state_file.absolute()}")
            print(f"   Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Size: {state_file.stat().st_size} bytes")

        print("\n✅ Status check complete")

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Make sure config.json exists")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
