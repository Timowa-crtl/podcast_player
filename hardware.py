"""GPIO hardware control for rotary switch and mode switch."""

import time
from enum import Enum
from typing import Optional, Tuple

from utils import log

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    log("WARNING", "RPi.GPIO not available - hardware disabled")


class SwitchState(Enum):
    PODCAST_SELECT = "podcast_select"
    PAUSED = "paused"
    PLAYING = "playing"
    MUSIC_MODE = "music_mode"


# GPIO pins (BCM)
POSITION_PINS = [4, 18, 22, 23, 24, 25, 5, 6, 12, 13, 16, 20]
PIN_PLAY = 17
PIN_MUSIC = 27

# Debounce settings
STABLE_READS = 3
DEBOUNCE_TIME = 0.2


class HardwareController:
    """Controls 12-position rotary switch and 3-position mode switch."""

    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE
        self.last_podcast_index = 1
        self._stable_count = 0
        self._last_sample = None
        self._last_confirm = None
        self._last_confirm_time = 0.0

        if self.gpio_available:
            self._setup_gpio()

    def _setup_gpio(self):
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN_PLAY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(PIN_MUSIC, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            for p in POSITION_PINS:
                GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            log("INFO", "GPIO initialized")
        except Exception as e:
            log("ERROR", f"GPIO init failed: {e}")
            self.gpio_available = False

    def _read_rotary(self) -> int:
        """Read rotary position: 1-12, 0=no contact, -1=multiple."""
        lows = [i for i, p in enumerate(POSITION_PINS) if GPIO.input(p) == GPIO.LOW]
        if len(lows) == 1:
            return lows[0] + 1
        return 0 if len(lows) == 0 else -1

    def read_state(self) -> Tuple[SwitchState, Optional[int]]:
        """Read current switch state and podcast index."""
        if not self.gpio_available:
            return (SwitchState.PAUSED, None)

        try:
            # Mode switch
            play_low = GPIO.input(PIN_PLAY) == GPIO.LOW
            music_low = GPIO.input(PIN_MUSIC) == GPIO.LOW

            if play_low and not music_low:
                mode = SwitchState.PLAYING
            elif music_low and not play_low:
                mode = SwitchState.MUSIC_MODE
            else:
                mode = SwitchState.PAUSED

            # Rotary with debounce
            raw = self._read_rotary()
            now = time.time()

            if raw == self._last_sample:
                self._stable_count += 1
            else:
                self._stable_count = 1
                self._last_sample = raw

            if (self._stable_count >= STABLE_READS and raw > 0 and
                self._last_confirm != raw and
                now - self._last_confirm_time >= DEBOUNCE_TIME):
                self._last_confirm = raw
                self._last_confirm_time = now
                self.last_podcast_index = raw

            return (mode, self.last_podcast_index)

        except Exception as e:
            log("ERROR", f"GPIO read error: {e}")
            return (SwitchState.PAUSED, None)

    def is_available(self) -> bool:
        return self.gpio_available

    def cleanup(self):
        if self.gpio_available:
            try:
                GPIO.cleanup()
            except Exception as e:
                log("DEBUG", f"GPIO cleanup: {e}")


if __name__ == "__main__":
    """Test switch wiring."""
    print("Switch Wiring Test (Ctrl+C to exit)")
    ctrl = HardwareController()
    if not ctrl.is_available():
        print("GPIO not available")
        exit(1)

    last = (None, None)
    try:
        while True:
            state, idx = ctrl.read_state()
            if (state, idx) != last:
                print(f"Mode: {state.value:15} | Podcast: {idx or 'N/A'}")
                last = (state, idx)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone")
    finally:
        ctrl.cleanup()
