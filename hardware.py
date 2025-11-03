"""
Hardware control module for GPIO switch input.
Provides abstraction layer for hardware control with fallback for non-Pi systems.
"""

from enum import Enum
from typing import Optional
from utils import Logger

logger = Logger()

# Try to import RPi.GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available - hardware control disabled")


class SwitchState(Enum):
    """Enumeration of possible switch states."""
    PODCAST_1 = "podcast_1"
    PODCAST_2 = "podcast_2"
    PAUSED = "paused"


class HardwareController:
    """
    Hardware controller for GPIO switch input.
    Provides safe abstraction with fallback for non-Pi systems.
    """
    
    # GPIO pin definitions (BCM numbering)
    PIN_PODCAST_1 = 17  # Physical pin 11
    PIN_PODCAST_2 = 27  # Physical pin 13
    
    def __init__(self):
        """Initialize hardware controller."""
        self.gpio_available = GPIO_AVAILABLE
        
        if self.gpio_available:
            self._setup_gpio()
        else:
            logger.info("Hardware controller running in simulation mode")
    
    def _setup_gpio(self):
        """Initialize GPIO pins for switch input."""
        try:
            # Use BCM pin numbering
            GPIO.setmode(GPIO.BCM)
            
            # Setup input pins with pull-up resistors
            GPIO.setup(self.PIN_PODCAST_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.PIN_PODCAST_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            logger.info("GPIO initialized successfully")
            logger.debug(f"Pin {self.PIN_PODCAST_1} (GPIO17) configured with pull-up")
            logger.debug(f"Pin {self.PIN_PODCAST_2} (GPIO27) configured with pull-up")
            
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            self.gpio_available = False
    
    def read_state(self) -> SwitchState:
        """
        Read current switch state.
        
        Returns:
            Current switch state
        """
        if not self.gpio_available:
            return SwitchState.PAUSED
        
        try:
            # Read pin states (0=LOW/connected to ground, 1=HIGH/pulled up)
            pin1 = GPIO.input(self.PIN_PODCAST_1)
            pin2 = GPIO.input(self.PIN_PODCAST_2)
            
            # Decode switch position
            # Switch pulls one pin LOW when in position 1 or 2
            if pin1 == 0 and pin2 == 1:
                return SwitchState.PODCAST_1
            elif pin1 == 1 and pin2 == 0:
                return SwitchState.PODCAST_2
            elif pin1 == 1 and pin2 == 1:
                return SwitchState.PAUSED
            else:
                # Both pins LOW - shouldn't happen with proper switch
                logger.warning(f"Invalid switch state: GPIO17={pin1}, GPIO27={pin2}")
                return SwitchState.PAUSED
                
        except Exception as e:
            logger.error(f"Error reading GPIO: {e}")
            return SwitchState.PAUSED
    
    def is_available(self) -> bool:
        """
        Check if hardware control is available.
        
        Returns:
            True if GPIO is available and initialized
        """
        return self.gpio_available
    
    def cleanup(self):
        """Clean up GPIO resources."""
        if self.gpio_available:
            try:
                GPIO.cleanup()
                logger.debug("GPIO cleanup complete")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")


class SwitchTester:
    """Utility class for testing switch wiring."""
    
    @staticmethod
    def run_test():
        """Run interactive switch test."""
        print("=" * 60)
        print("Switch Wiring Test")
        print("=" * 60)
        
        controller = HardwareController()
        
        if not controller.is_available():
            print("❌ GPIO not available on this system")
            return
        
        print("✅ GPIO initialized")
        print("\nSwitch wiring:")
        print("  Pin 1 → RPi Pin 11 (GPIO17)")
        print("  Pin 2 → RPi Pin 9  (GND)")
        print("  Pin 3 → RPi Pin 13 (GPIO27)")
        print("\nPress Ctrl+C to exit\n")
        
        last_state = None
        
        try:
            while True:
                state = controller.read_state()
                
                if state != last_state:
                    print(f"Switch position: {state.value}")
                    
                    if GPIO_AVAILABLE:
                        pin1 = GPIO.input(controller.PIN_PODCAST_1)
                        pin2 = GPIO.input(controller.PIN_PODCAST_2)
                        print(f"  GPIO17={pin1}, GPIO27={pin2}")
                    
                    last_state = state
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nTest complete")
        finally:
            controller.cleanup()


if __name__ == "__main__":
    # Run switch test if module is executed directly
    import time
    SwitchTester.run_test()
