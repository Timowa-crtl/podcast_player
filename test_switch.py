#!/usr/bin/env python3
"""
Hardware switch test utility.
Tests the 3-position switch wiring and GPIO configuration.
"""

from hardware import SwitchTester

if __name__ == "__main__":
    SwitchTester.run_test()
