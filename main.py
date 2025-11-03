#!/usr/bin/env python3
"""
Raspberry Pi Podcast Player - Main Entry Point
A hardware-controlled podcast player using a 3-position switch.
"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime

from config import Config
from podcast_player import PodcastPlayer
from utils import Logger, safe_cleanup

# Initialize logger
logger = Logger()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("\n👋 Shutdown signal received...")
    sys.exit(0)


def main():
    """Main entry point for the podcast player."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print welcome banner
    print("=" * 60)
    print("🎧 Raspberry Pi Podcast Player v12")
    print("=" * 60)
    
    player = None
    
    try:
        # Load configuration
        config = Config()
        
        # Initialize player
        player = PodcastPlayer(config)
        
        # Start the player
        logger.info("🚀 Starting podcast player...")
        player.run()
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        # Clean up resources
        if player:
            safe_cleanup(player.cleanup)
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
