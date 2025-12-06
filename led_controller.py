import time
import logging
from enum import Enum
from threading import Thread, Event

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available - LED indicators disabled")

class LEDState(Enum):
    OFF = "off"
    PLAYING = "playing"
    PAUSED = "paused"
    REFRESHING = "refreshing"
    DOWNLOADING = "downloading"
    ERROR = "error"
    WARNING = "warning"

# GPIO pins (BCM)
LED_PIN_RED = 26
LED_PIN_GREEN = 19

class LEDController:
    def __init__(self):
        self._current_state = LEDState.OFF
        self._stop_event = Event()
        self._thread = None
        
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(LED_PIN_RED, GPIO.OUT)
            GPIO.setup(LED_PIN_GREEN, GPIO.OUT)
            self._set_leds(False, False)
    
    def set_state(self, state: LEDState):
        if not GPIO_AVAILABLE:
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        
        self._current_state = state
        self._stop_event.clear()
        
        if state == LEDState.PLAYING:
            self._set_leds(False, True)
        elif state in (LEDState.PAUSED, LEDState.OFF):
            self._set_leds(False, False)
        elif state in (LEDState.REFRESHING, LEDState.DOWNLOADING):
            self._thread = Thread(target=self._blink, args=(LED_PIN_GREEN, 1.0))
            self._thread.start()
        elif state == LEDState.ERROR:
            self._thread = Thread(target=self._blink_n, args=(LED_PIN_RED, 5, 0.5))
            self._thread.start()
        elif state == LEDState.WARNING:
            self._thread = Thread(target=self._blink_n, args=(LED_PIN_RED, 3, 0.3))
            self._thread.start()
    
    def test_mode(self):
        """Showcase all LED patterns."""
        if not GPIO_AVAILABLE:
            logger.info("Test mode: GPIO not available")
            return
        
        logger.info("LED Test Mode - Starting")
        
        states = [
            (LEDState.PLAYING, 2, "Green solid"),
            (LEDState.PAUSED, 2, "All off"),
            (LEDState.REFRESHING, 4, "Green blink slow"),
            (LEDState.WARNING, 3, "Red blink 3x medium"),
            (LEDState.ERROR, 4, "Red blink 5x slow"),
            (LEDState.OFF, 1, "All off"),
        ]
        
        for state, duration, desc in states:
            logger.info(f"Test: {desc}")
            self.set_state(state)
            time.sleep(duration)
        
        logger.info("LED Test Mode - Complete")
    
    def _set_leds(self, red: bool, green: bool):
        GPIO.output(LED_PIN_RED, red)
        GPIO.output(LED_PIN_GREEN, green)
    
    def _blink(self, pin: int, interval: float):
        while not self._stop_event.is_set():
            GPIO.output(pin, True)
            if self._stop_event.wait(interval / 2):
                break
            GPIO.output(pin, False)
            if self._stop_event.wait(interval / 2):
                break
    
    def _blink_n(self, pin: int, count: int, interval: float):
        for _ in range(count):
            GPIO.output(pin, True)
            time.sleep(interval / 2)
            GPIO.output(pin, False)
            time.sleep(interval / 2)
    
    def cleanup(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        if GPIO_AVAILABLE:
            self._set_leds(False, False)
            GPIO.cleanup([LED_PIN_RED, LED_PIN_GREEN])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    led = LEDController()
    try:
        led.test_mode()
    finally:
        led.cleanup()
