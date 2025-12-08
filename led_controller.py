"""
LED indicator module for podcast player.
Controls red and green LEDs to show player status.
"""

import random
import time
from enum import Enum
from threading import Thread, Event

from utils import Logger

logger = Logger()

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available - LED indicators disabled")


class LEDState(Enum):
    """LED state indicators."""
    OFF = "off"
    PLAYING = "playing"
    PAUSED = "paused"
    REFRESHING = "refreshing"
    DOWNLOADING = "downloading"
    ERROR = "error"
    WARNING = "warning"
    MUSIC_MODE = "music_mode"


# GPIO pins (BCM)
LED_PIN_RED = 26
LED_PIN_GREEN = 19


class LEDController:
    """
    Controls LED indicators for podcast player status.
    """

    def __init__(self):
        """Initialize LED controller."""
        self._current_state = LEDState.OFF
        self._stop_event = Event()
        self._thread = None
        self._gpio_initialized = False

        if GPIO_AVAILABLE:
            self._init_gpio()
        else:
            logger.debug("LED controller in simulation mode")

    def _init_gpio(self):
        """Initialize GPIO pins."""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(LED_PIN_RED, GPIO.OUT)
            GPIO.setup(LED_PIN_GREEN, GPIO.OUT)
            self._set_leds(False, False)
            self._gpio_initialized = True
            logger.debug("LED controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LED GPIO: {e}")
            self._gpio_initialized = False

    def startup_test(self):
        """Blink both LEDs 3 times at startup."""
        if not self._gpio_initialized:
            return

        logger.info("LED startup test...")
        for _ in range(3):
            self._set_leds(True, True)
            time.sleep(0.2)
            self._set_leds(False, False)
            time.sleep(0.2)
        logger.debug("LED startup test complete")

    def set_state(self, state: LEDState):
        """
        Set LED state.

        Args:
            state: Desired LED state
        """
        if not self._gpio_initialized:
            return

        # Stop any running animation
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
            self._thread = None

        self._current_state = state
        self._stop_event.clear()

        if state == LEDState.PLAYING:
            self._set_leds(False, True)  # Green solid

        elif state in (LEDState.PAUSED, LEDState.OFF):
            self._set_leds(False, False)  # All off

        elif state in (LEDState.REFRESHING, LEDState.DOWNLOADING):
            # Green blink slow
            self._thread = Thread(target=self._blink, args=(LED_PIN_GREEN, 1.0), daemon=True)
            self._thread.start()

        elif state == LEDState.ERROR:
            # Red blink 5x
            self._thread = Thread(target=self._blink_n, args=(LED_PIN_RED, 5, 0.5), daemon=True)
            self._thread.start()

        elif state == LEDState.WARNING:
            # Red blink 3x
            self._thread = Thread(target=self._blink_n, args=(LED_PIN_RED, 3, 0.3), daemon=True)
            self._thread.start()

        elif state == LEDState.MUSIC_MODE:
            # Cool lightshow!
            self._thread = Thread(target=self._lightshow, daemon=True)
            self._thread.start()

    def _set_leds(self, red: bool, green: bool):
        """Set LED states directly."""
        if not self._gpio_initialized:
            return
        try:
            GPIO.output(LED_PIN_RED, red)
            GPIO.output(LED_PIN_GREEN, green)
        except Exception as e:
            logger.error(f"Error setting LED state: {e}")

    def _blink(self, pin: int, interval: float):
        """Blink LED continuously."""
        while not self._stop_event.is_set():
            try:
                GPIO.output(pin, True)
            except:
                break
            if self._stop_event.wait(interval / 2):
                break
            try:
                GPIO.output(pin, False)
            except:
                break
            if self._stop_event.wait(interval / 2):
                break

    def _blink_n(self, pin: int, count: int, interval: float):
        """Blink LED n times then turn off."""
        for _ in range(count):
            if self._stop_event.is_set():
                break
            try:
                GPIO.output(pin, True)
            except:
                break
            time.sleep(interval / 2)
            if self._stop_event.is_set():
                break
            try:
                GPIO.output(pin, False)
            except:
                break
            time.sleep(interval / 2)
        # Turn off LED
        if self._gpio_initialized:
            try:
                self._set_leds(False, False)
            except:
                pass

    def _lightshow(self):
        """
        Cool lightshow for music mode!
        Runs until stop_event is set.
        """
        patterns = [
            self._pattern_alternate,
            self._pattern_chase,
            self._pattern_random,
            self._pattern_pulse,
        ]

        pattern_idx = 0
        cycles_per_pattern = 10

        while not self._stop_event.is_set():
            # Run current pattern for a few cycles
            pattern_func = patterns[pattern_idx]
            for _ in range(cycles_per_pattern):
                if self._stop_event.is_set():
                    break
                pattern_func()

            # Switch to next pattern
            pattern_idx = (pattern_idx + 1) % len(patterns)

        # Turn off LEDs when done
        if self._gpio_initialized:
            try:
                self._set_leds(False, False)
            except:
                pass

    def _pattern_alternate(self):
        """Alternating red and green."""
        if self._stop_event.is_set():
            return
        self._set_leds(True, False)  # Red
        if self._stop_event.wait(0.15):
            return
        self._set_leds(False, True)  # Green
        if self._stop_event.wait(0.15):
            return

    def _pattern_chase(self):
        """Chase pattern - both on, both off, repeat."""
        if self._stop_event.is_set():
            return
        self._set_leds(True, True)  # Both on
        if self._stop_event.wait(0.1):
            return
        self._set_leds(False, False)  # Both off
        if self._stop_event.wait(0.1):
            return
        self._set_leds(True, False)  # Red only
        if self._stop_event.wait(0.1):
            return
        self._set_leds(False, True)  # Green only
        if self._stop_event.wait(0.1):
            return

    def _pattern_random(self):
        """Random LED states."""
        if self._stop_event.is_set():
            return
        red = random.choice([True, False])
        green = random.choice([True, False])
        self._set_leds(red, green)
        self._stop_event.wait(0.08)

    def _pattern_pulse(self):
        """Quick pulse both LEDs."""
        if self._stop_event.is_set():
            return
        # Quick flash
        for _ in range(3):
            if self._stop_event.is_set():
                return
            self._set_leds(True, True)
            if self._stop_event.wait(0.05):
                return
            self._set_leds(False, False)
            if self._stop_event.wait(0.05):
                return
        # Pause
        self._stop_event.wait(0.2)

    def cleanup(self):
        """Clean up LED resources."""
        # Stop any running threads immediately
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

        if self._gpio_initialized:
            try:
                # Turn off LEDs first
                self._set_leds(False, False)
                # Then cleanup GPIO pins
                GPIO.cleanup([LED_PIN_RED, LED_PIN_GREEN])
                self._gpio_initialized = False
                logger.debug("LED cleanup complete")
            except Exception as e:
                # Don't log error if GPIO was already cleaned up
                if "mode" not in str(e).lower():
                    logger.error(f"Error during LED cleanup: {e}")


if __name__ == "__main__":
    """Test LED functionality."""
    print("LED Test Mode")
    print("=" * 60)

    led = LEDController()

    if not led._gpio_initialized:
        print("❌ GPIO not available on this system")
        exit(1)

    try:
        led.startup_test()
        time.sleep(1)

        tests = [
            (LEDState.PLAYING, 2, "Green solid - Playing"),
            (LEDState.PAUSED, 2, "All off - Paused"),
            (LEDState.REFRESHING, 4, "Green blink - Refreshing"),
            (LEDState.WARNING, 3, "Red blink 3x - Warning"),
            (LEDState.ERROR, 4, "Red blink 5x - Error"),
            (LEDState.MUSIC_MODE, 8, "Lightshow - Music Mode"),
            (LEDState.OFF, 1, "All off"),
        ]

        for state, duration, desc in tests:
            print(f"Testing: {desc}")
            led.set_state(state)
            time.sleep(duration)

        print("\nTest complete!")

    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        led.cleanup()
