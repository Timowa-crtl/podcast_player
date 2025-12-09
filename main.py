#!/usr/bin/env python3
"""Raspberry Pi Podcast Player - Main Entry Point."""

import signal
import sys

from config import Config
from podcast_player import PodcastPlayer
from utils import log, safe_cleanup


def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print("=" * 60)
    print("🎧 Raspberry Pi Podcast Player")
    print("=" * 60)

    player = None
    try:
        player = PodcastPlayer(Config())
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
