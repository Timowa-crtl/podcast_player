#!/usr/bin/env python3
"""
Simple test script for 3-position switch on Raspberry Pi
Tests GPIO17 (Pin 11) and GPIO27 (Pin 13) with pull-up resistors
"""
import sys
import time

import RPi.GPIO as GPIO

# Pin definitions (BCM numbering)
PIN_PODCAST_1 = 17  # Physical Pin 11
PIN_PODCAST_2 = 27  # Physical Pin 13


def setup_gpio():
    """Initialize GPIO pins"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_PODCAST_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PIN_PODCAST_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("✓ GPIO initialized (BCM mode)")
    print(f"  GPIO17 (Pin 11) - Pull-up enabled")
    print(f"  GPIO27 (Pin 13) - Pull-up enabled")
    print()


def read_switch_state():
    """Read switch position and return state name"""
    pin1 = GPIO.input(PIN_PODCAST_1)  # 1=HIGH, 0=LOW
    pin2 = GPIO.input(PIN_PODCAST_2)

    if pin1 == 0 and pin2 == 1:
        return "PODCAST_1", pin1, pin2
    elif pin1 == 1 and pin2 == 0:
        return "PODCAST_2", pin1, pin2
    elif pin1 == 1 and pin2 == 1:
        return "PAUSED", pin1, pin2
    else:
        return "ERROR (both LOW)", pin1, pin2


def main():
    print("=" * 60)
    print("SWITCH TEST - 3-Position Kippschalter")
    print("=" * 60)
    print()
    print("Wiring check:")
    print("  Switch Pin 1 → RPi Pin 11 (GPIO17)")
    print("  Switch Pin 2 → RPi Pin 9  (GND)")
    print("  Switch Pin 3 → RPi Pin 13 (GPIO27)")
    print()
    print("Expected behavior:")
    print("  Position UP     → PODCAST_1 (GPIO17=0, GPIO27=1)")
    print("  Position CENTER → PAUSED    (GPIO17=1, GPIO27=1)")
    print("  Position DOWN   → PODCAST_2 (GPIO17=1, GPIO27=0)")
    print()
    print("-" * 60)
    print()

    try:
        setup_gpio()
        print("Move your switch and watch the output.")
        print("Press Ctrl+C to exit.")
        print()

        last_state = None

        while True:
            state, pin1, pin2 = read_switch_state()

            # Only print when state changes
            if state != last_state:
                timestamp = time.strftime("%H:%M:%S")
                print(
                    f"[{timestamp}] State: {state:20s} (GPIO17={pin1}, GPIO27={pin2})"
                )

                # Visual indicator
                if state == "PODCAST_1":
                    print("           🎧 → Podcast 1 would play")
                elif state == "PODCAST_2":
                    print("           🎧 → Podcast 2 would play")
                elif state == "PAUSED":
                    print("           ⏸️  → Paused")
                else:
                    print(
                        "           ⚠️  → Check wiring! Both pins LOW is not expected."
                    )

                print()
                last_state = state

            time.sleep(0.1)  # Poll every 100ms

    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("Test completed. Cleaning up GPIO...")
        print("=" * 60)

    finally:
        GPIO.cleanup()
        print("✓ GPIO cleanup done")
        sys.exit(0)


if __name__ == "__main__":
    main()
