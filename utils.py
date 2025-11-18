"""
Utility functions and helpers for the podcast player.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Callable


class Logger:
    """
    Simple logging wrapper with consistent formatting.
    Supports debug, info, warning, and error levels.
    """

    # ANSI color codes for terminal output
    COLORS = {"DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m", "ERROR": "\033[31m", "RESET": "\033[0m"}  # Cyan  # Green  # Yellow  # Red  # Reset

    def __init__(self, name: str = "PodcastPlayer", debug: bool = None):
        """
        Initialize logger.

        Args:
            name: Logger name
            debug: Enable debug output (reads from config if None)
        """
        self.name = name
        self._debug_enabled = debug

        # Try to read debug setting from config
        if self._debug_enabled is None:
            try:
                import json

                with open("config.json", "r") as f:
                    config = json.load(f)
                    self._debug_enabled = config.get("debug_mode", False)
            except:
                self._debug_enabled = False

    def _format_message(self, level: str, message: str) -> str:
        """
        Format log message with timestamp and level.

        Args:
            level: Log level
            message: Message to log

        Returns:
            Formatted message
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Add color for terminal output
        if sys.stdout.isatty():
            color = self.COLORS.get(level, "")
            reset = self.COLORS["RESET"]
            return f"[{timestamp}] {color}{level:8}{reset} {message}"
        else:
            return f"[{timestamp}] {level:8} {message}"

    def debug(self, message: str):
        """Log debug message."""
        if self._debug_enabled:
            print(self._format_message("DEBUG", message))

    def info(self, message: str):
        """Log info message."""
        print(self._format_message("INFO", message))

    def warning(self, message: str):
        """Log warning message."""
        print(self._format_message("WARNING", message), file=sys.stderr)

    def error(self, message: str):
        """Log error message."""
        print(self._format_message("ERROR", message), file=sys.stderr)


def safe_cleanup(cleanup_func: Callable, *args, **kwargs) -> bool:
    """
    Safely execute cleanup function with error handling.

    Args:
        cleanup_func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        True if successful, False if error occurred
    """
    logger = Logger()

    try:
        cleanup_func(*args, **kwargs)
        return True
    except Exception as e:
        logger.error(f"Cleanup error in {cleanup_func.__name__}: {e}")
        return False


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    if seconds < 0:
        return "0s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_file_size(bytes_size: float) -> str:
    """
    Format file size in bytes to human-readable string.

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string (e.g., "12.3 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size = bytes_size / 1024.0

    return f"{bytes_size:.1f} TB"


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def validate_url(url: str) -> bool:
    """
    Validate if string is a valid URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid URL
    """
    import re

    pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return bool(pattern.match(url))


class ProgressBar:
    """Simple progress bar for terminal output."""

    def __init__(self, total: int, width: int = 40):
        """
        Initialize progress bar.

        Args:
            total: Total items/bytes
            width: Width of progress bar in characters
        """
        self.total = total
        self.width = width
        self.current = 0
        self.logger = Logger()

    def update(self, current: int):
        """
        Update progress bar.

        Args:
            current: Current progress value
        """
        self.current = min(current, self.total)

        if self.total > 0:
            percent = (self.current / self.total) * 100
            filled = int((self.current / self.total) * self.width)

            bar = "█" * filled + "░" * (self.width - filled)

            # Print with carriage return to update same line
            print(f"\r[{bar}] {percent:.1f}%", end="", flush=True)

            if self.current >= self.total:
                print()  # New line when complete
