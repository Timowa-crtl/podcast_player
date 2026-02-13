"""Utility functions and helpers."""

import sys
from datetime import datetime
from typing import Callable

# Global LED controller reference (set by PodcastPlayer)
_led_controller = None

# Cache debug mode (loaded once)
_debug_mode = None


def _get_debug_mode():
    """Get debug mode, cached after first call."""
    global _debug_mode
    if _debug_mode is None:
        try:
            import json

            with open("config.json", "r") as f:
                _debug_mode = json.load(f).get("debug_mode", False)
        except:
            _debug_mode = False
    return _debug_mode


def set_led_controller(controller):
    """Set global LED controller for log-triggered LED feedback."""
    global _led_controller
    _led_controller = controller


def log(level: str, message: str):
    """Log message with timestamp. Levels: DEBUG, INFO, WARNING, ERROR."""
    if level == "DEBUG" and not _get_debug_mode():
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {"DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m", "ERROR": "\033[31m"}
    reset = "\033[0m"

    if sys.stdout.isatty():
        out = f"[{timestamp}] {colors.get(level, '')}{level:8}{reset} {message}"
    else:
        out = f"[{timestamp}] {level:8} {message}"

    print(out, file=sys.stderr if level in ("WARNING", "ERROR") else sys.stdout)

    # Trigger LED on warning/error
    if _led_controller and level in ("WARNING", "ERROR"):
        from led_controller import LEDState

        state = LEDState.ERROR if level == "ERROR" else LEDState.WARNING
        _led_controller.set_state(state)


def safe_cleanup(cleanup_func: Callable) -> bool:
    """Execute cleanup function with error handling."""
    try:
        cleanup_func()
        return True
    except Exception as e:
        log("ERROR", f"Cleanup error in {cleanup_func.__name__}: {e}")
        return False


def format_duration(seconds: float) -> str:
    """Format seconds as '1h 23m 45s'."""
    if seconds < 0:
        return "0s"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


def format_file_size(bytes_size: float) -> str:
    """Format bytes as '12.3 MB'."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"
