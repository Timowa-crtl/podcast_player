#!/usr/bin/env python3
"""Raspberry Pi Podcast Player - Main Entry Point."""

import argparse
import signal
import sys

from config import Config
from podcast_player import PodcastPlayer
from utils import log, safe_cleanup


def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Podcast Player")
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip the initial RSS episode check on startup",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print("=" * 60)
    print("🎧 Raspberry Pi Podcast Player")
    print("=" * 60)

    player = None
    try:
        player = PodcastPlayer(Config(), skip_initial_check=args.skip_check)
        log("INFO", "🚀 Starting...")
        player.run()
    except FileNotFoundError as e:
        log("ERROR", f"Config not found: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        log("INFO", "👋 Shutting down...")
    except Exception as e:
        log("ERROR", f"Fatal: {e}")
        sys.exit(1)
    finally:
        if player:
            safe_cleanup(player.cleanup)
        log("INFO", "Shutdown complete.")


if __name__ == "__main__":
    main()