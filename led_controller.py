"""
LED indicator module for podcast player.
Controls red and green LEDs to show player status.
"""

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
    MUSIC_MODE = "music_mode"  # Added for music mode


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

        if GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(LED_PIN_RED, GPIO.OUT)
                GPIO.setup(LED_PIN_GREEN, GPIO.OUT)
                self._set_leds(False, False)
                logger.debug("LED controller initialized")
            except Exception as e:
                logger.error(f"Failed to initialize LED GPIO: {e}")
        else:
            logger.debug("LED controller in simulation mode")

    def startup_test(self):
        """Blink both LEDs 3 times at startup."""
        if not GPIO_AVAILABLE:
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
        if not GPIO_AVAILABLE:
            return

        # Stop any running animation
        self._stop_event.set()
        if self._thread:
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
            # Alternating red/green blink for music mode (fun light show)
            self._thread = Thread(target=self._alternate_blink, args=(0.3,), daemon=True)
            self._thread.start()

    def _set_leds(self, red: bool, green: bool):
        """Set LED states directly."""
        try:
            GPIO.output(LED_PIN_RED, red)
            GPIO.output(LED_PIN_GREEN, green)
        except Exception as e:
            logger.error(f"Error setting LED state: {e}")

    def _blink(self, pin: int, interval: float):
        """Blink LED continuously."""
        while not self._stop_event.is_set():
            GPIO.output(pin, True)
            if self._stop_event.wait(interval / 2):
                break
            GPIO.output(pin, False)
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
        # Turn off LED directly (don't call set_state from within thread)
        try:
            self._set_leds(False, False)
        except:
            pass  # GPIO may already be cleaned up

    def _alternate_blink(self, interval: float):
        """Alternate between red and green LEDs (music mode light show)."""
        while not self._stop_event.is_set():
            try:
                self._set_leds(True, False)  # Red on
            except:
                break
            if self._stop_event.wait(interval):
                break
            try:
                self._set_leds(False, True)  # Green on
            except:
                break
            if self._stop_event.wait(interval):
                break

    def cleanup(self):
        """Clean up LED resources."""
        # Stop any running threads immediately
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        
        if GPIO_AVAILABLE:
            try:
                # Turn off LEDs first
                self._set_leds(False, False)
                # Then cleanup GPIO pins
                GPIO.cleanup([LED_PIN_RED, LED_PIN_GREEN])
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
    
    if not led._current_state:
        print("GPIO not available")
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
            (LEDState.MUSIC_MODE, 4, "Alternating - Music Mode"),
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
