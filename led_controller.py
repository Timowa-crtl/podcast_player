"""LED status indicators with patterns for different states."""

import random
import time
from enum import Enum
from threading import Thread, Event

from utils import log

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

LED_RED = 26
LED_GREEN = 19


class LEDState(Enum):
    OFF = "off"
    PLAYING = "playing"
    PAUSED = "paused"
    REFRESHING = "refreshing"
    DOWNLOADING = "downloading"
    ERROR = "error"
    WARNING = "warning"
    MUSIC_MODE = "music_mode"


class LEDController:
    """Controls red/green status LEDs."""

    def __init__(self):
        self._stop = Event()
        self._thread = None
        self._initialized = False

        if GPIO_AVAILABLE:
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(LED_RED, GPIO.OUT)
                GPIO.setup(LED_GREEN, GPIO.OUT)
                self._set(False, False)
                self._initialized = True
            except Exception as e:
                log("ERROR", f"LED init failed: {e}")

    def _set(self, red: bool, green: bool):
        if self._initialized:
            try:
                GPIO.output(LED_RED, red)
                GPIO.output(LED_GREEN, green)
            except:
                pass

    def _stop_thread(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        self._stop.clear()

    def startup_test(self):
        """Blink both LEDs 3 times."""
        if not self._initialized:
            return
        log("INFO", "LED startup test...")
        for _ in range(3):
            self._set(True, True)
            time.sleep(0.2)
            self._set(False, False)
            time.sleep(0.2)

    def set_state(self, state: LEDState):
        """Set LED state."""
        if not self._initialized:
            return

        self._stop_thread()

        if state == LEDState.PLAYING:
            self._set(False, True)
        elif state in (LEDState.PAUSED, LEDState.OFF):
            self._set(False, False)
        elif state in (LEDState.REFRESHING, LEDState.DOWNLOADING):
            self._thread = Thread(target=self._blink, args=(LED_GREEN, 1.0), daemon=True)
            self._thread.start()
        elif state == LEDState.ERROR:
            self._thread = Thread(target=self._blink_n, args=(LED_RED, 5, 0.5), daemon=True)
            self._thread.start()
        elif state == LEDState.WARNING:
            self._thread = Thread(target=self._blink_n, args=(LED_RED, 3, 0.3), daemon=True)
            self._thread.start()
        elif state == LEDState.MUSIC_MODE:
            self._thread = Thread(target=self._lightshow, daemon=True)
            self._thread.start()

    def _blink(self, pin: int, interval: float):
        """Continuous blink."""
        if not self._initialized:
            return
        half = interval / 2
        while not self._stop.is_set():
            try:
                GPIO.output(pin, True)
            except:
                break
            if self._stop.wait(half):
                break
            try:
                GPIO.output(pin, False)
            except:
                break
            if self._stop.wait(half):
                break
        self._set(False, False)

    def _blink_n(self, pin: int, count: int, interval: float):
        """Blink n times."""
        if not self._initialized:
            return
        half = interval / 2
        for _ in range(count):
            if self._stop.is_set():
                break
            try:
                GPIO.output(pin, True)
                time.sleep(half)
                GPIO.output(pin, False)
                time.sleep(half)
            except:
                break
        self._set(False, False)

    def _lightshow(self):
        """Music mode lightshow."""
        if not self._initialized:
            return
        patterns = [
            [(True, False), (False, True)],  # alternate
            [(True, True), (False, False), (True, False), (False, True)],  # chase
        ]
        while not self._stop.is_set():
            # Alternate pattern
            for _ in range(10):
                if self._stop.is_set():
                    break
                for r, g in patterns[0]:
                    self._set(r, g)
                    if self._stop.wait(0.15):
                        break
            # Chase pattern
            for _ in range(10):
                if self._stop.is_set():
                    break
                for r, g in patterns[1]:
                    self._set(r, g)
                    if self._stop.wait(0.1):
                        break
            # Random
            for _ in range(20):
                if self._stop.is_set():
                    break
                self._set(random.choice([True, False]), random.choice([True, False]))
                if self._stop.wait(0.08):
                    break
            # Pulse
            for _ in range(3):
                if self._stop.is_set():
                    break
                for _ in range(3):
                    self._set(True, True)
                    if self._stop.wait(0.05):
                        break
                    self._set(False, False)
                    if self._stop.wait(0.05):
                        break
                self._stop.wait(0.2)

        self._set(False, False)

    def cleanup(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        if self._initialized:
            try:
                self._set(False, False)
                GPIO.cleanup([LED_RED, LED_GREEN])
            except:
                pass


if __name__ == "__main__":
    """Test LEDs."""
    print("LED Test")
    led = LEDController()
    if not led._initialized:
        print("GPIO not available")
        exit(1)

    tests = [
        (LEDState.PLAYING, 2, "Green solid"),
        (LEDState.PAUSED, 2, "Off"),
        (LEDState.REFRESHING, 4, "Green blink"),
        (LEDState.WARNING, 3, "Red 3x"),
        (LEDState.ERROR, 4, "Red 5x"),
        (LEDState.MUSIC_MODE, 8, "Lightshow"),
    ]
    try:
        led.startup_test()
        for state, dur, desc in tests:
            print(f"Testing: {desc}")
            led.set_state(state)
            time.sleep(dur)
    except KeyboardInterrupt:
        pass
    finally:
        led.cleanup()
