#!/usr/bin/env python3
"""Status display tool for podcast player."""

import sys
from pathlib import Path

from config import Config
from podcast_manager import PodcastManager
from state_manager import StateManager
from utils import format_duration, format_file_size


def main():
    print("=" * 60)
    print("📊 Podcast Player Status")
    print("=" * 60)

    try:
        config = Config()
        state = StateManager()
        manager = PodcastManager(config)

        # Config
        print(f"\n📋 Config: {config.episodes_dir}, max {config.max_episodes}/podcast, check every {config.check_interval_hours}h")

        # Podcasts
        print(f"\n📻 Podcasts ({len(config.podcasts)}):")
        for i, p in enumerate(config.podcasts, 1):
            print(f"   {i}. {p['name']}")

        # Stats
        stats = state.get_statistics()
        print(f"\n📈 Stats: {stats['total_episodes']} episodes, {stats['total_time_hours']:.1f}h listened, last check: {stats['last_check']}")

        # Episodes
        print("\n📚 Episodes:")
        for i, pc in enumerate(config.podcasts):
            podcast_id = f"podcast_{i + 1}"
            ps = state.get_podcast(podcast_id)
            print(f"\n   {pc['name']}:")

            if not ps["episodes"]:
                print("      (none)")
                continue

            curr = ps.get("current_index", 0)
            for j, ep in enumerate(ps["episodes"]):
                marker = "▶️" if j == curr else ("✅" if ep.get("completed") else "  ")
                path = manager.get_episode_path(podcast_id, ep["file"])
                size = format_file_size(path.stat().st_size) if path.exists() else "missing"
                print(f"      {marker} {j+1}. {ep['title'][:40]} | {format_duration(ep.get('position', 0))} | {size}")

        # Storage
        info = manager.get_storage_info()
        print(f"\n💾 Storage: {info['episode_count']} files, {info['total_size_mb']:.1f} MB in {info['episodes_dir']}")

        # Disk space
        try:
            import shutil
            st = shutil.disk_usage(config.episodes_dir)
            print(f"💿 Disk: {st.free / 1e9:.1f} GB free / {st.total / 1e9:.1f} GB ({st.used / st.total * 100:.0f}% used)")
        except:
            pass

        print("\n✅ Done")

    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
