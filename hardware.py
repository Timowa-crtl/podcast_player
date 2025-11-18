#!/usr/bin/env python3
"""
Hardware control module for GPIO switch input.
Supports 12-position rotary switch for podcast selection and
3-position mode switch for play/pause/music-mode.
"""

import time
from enum import Enum
from typing import Optional, Tuple

from utils import Logger

logger = Logger()

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available - hardware control disabled")


class SwitchState(Enum):
    PODCAST_SELECT = "podcast_select"
    PAUSED = "paused"
    PLAYING = "playing"
    MUSIC_MODE = "music_mode"


# GPIO pin definitions (BCM)
POSITION_PINS = [4, 18, 22, 23, 24, 25, 5, 6, 12, 13, 16, 20]
PIN_PLAY = 17
PIN_MUSIC = 27

# Rotary switch debounce
SAMPLE_MS = 50
STABLE_READS = 5
TRANSITION_TIMEOUT_MS = 1000


class HardwareController:
    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE
        self.last_podcast_index = 1
        self._stable_count = 0
        self._last_sample = None
        self._last_confirm = None
        self._last_confirm_time = 0.0

        if self.gpio_available:
            self._setup_gpio()
        else:
            logger.info("Hardware controller running in simulation mode")

    def _setup_gpio(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN_PLAY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(PIN_MUSIC, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            for p in POSITION_PINS:
                GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info("GPIO initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            self.gpio_available = False

    def _read_rotary_raw(self) -> int:
        """Read raw rotary switch position (1-12, 0=no contact, -1=multiple)."""
        values = [GPIO.input(p) for p in POSITION_PINS]
        lows = [i for i, v in enumerate(values) if v == GPIO.LOW]
        
        if len(lows) == 1:
            return lows[0] + 1  # Return 1-12
        if len(lows) == 0:
            return 0  # No contact (between positions)
        return -1  # Multiple contacts (error)

    def read_state(self) -> Tuple[SwitchState, Optional[int]]:
        """Read both switches and return current state."""
        if not self.gpio_available:
            return (SwitchState.PAUSED, None)

        try:
            # Read 3-position mode switch
            pin_play = GPIO.input(PIN_PLAY)
            pin_music = GPIO.input(PIN_MUSIC)

            # Determine mode
            if pin_play == GPIO.LOW and pin_music == GPIO.HIGH:
                mode = SwitchState.PLAYING
            elif pin_play == GPIO.HIGH and pin_music == GPIO.LOW:
                mode = SwitchState.MUSIC_MODE
            elif pin_play == GPIO.HIGH and pin_music == GPIO.HIGH:
                mode = SwitchState.PAUSED
            else:
                logger.warning("Unexpected mode switch state (both LOW)")
                mode = SwitchState.PAUSED

            # Read rotary switch with debouncing
            raw = self._read_rotary_raw()
            now = time.time()

            # Debounce logic
            if raw == self._last_sample:
                self._stable_count += 1
            else:
                self._stable_count = 1
                self._last_sample = raw

            # Confirm stable reading
            if self._stable_count >= STABLE_READS and raw > 0:
                # Valid position detected
                if self._last_confirm != raw or (now - self._last_confirm_time > TRANSITION_TIMEOUT_MS / 1000):
                    self._last_confirm = raw
                    self._last_confirm_time = now
                    self.last_podcast_index = raw
                    logger.debug(f"Rotary switch confirmed: position {raw}")

            # Return current state
            return (mode, self.last_podcast_index)

        except Exception as e:
            logger.error(f"Error reading GPIO: {e}")
            return (SwitchState.PAUSED, None)

    def is_available(self) -> bool:
        return self.gpio_available

    def cleanup(self):
        if self.gpio_available:
            try:
                GPIO.cleanup()
                logger.debug("GPIO cleanup complete")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")


class SwitchTester:
    @staticmethod
    def run_test():
        print("=" * 60)
        print("Switch Wiring Test")
        print("=" * 60)

        controller = HardwareController()

        if not controller.is_available():
            print("❌ GPIO not available on this system")
            return

        print("✅ GPIO initialized")
        print("\nRotary switch positions (1–12) → podcast select")
        print("3-position mode switch → play/pause/music")
        print("\nPress Ctrl+C to exit\n")

        last_state = None
        last_value = None

        try:
            while True:
                state, value = controller.read_state()
                
                # Show changes
                if state != last_state or value != last_value:
                    print(f"Mode: {state.value:15} | Podcast: {value if value else 'N/A'}")
                    last_state = state
                    last_value = value
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\nTest complete")
        finally:
            controller.cleanup()


if __name__ == "__main__":
    SwitchTester.run_test()
