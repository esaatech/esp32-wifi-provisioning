"""
setup_button.py

Monitors the dedicated Wi-Fi setup button.

Hardware
--------
Classic ESP32 DevKit:
    GPIO27 ---- Push Button ---- GND

ESP32-S3 (Octal PSRAM / N16R8):
    GPIO27 is reserved for flash/PSRAM and cannot be used.
    Use GPIO4 instead:

    GPIO4 ---- Push Button ---- GND

The ESP32 internal pull-up resistor is used.

Normal state:
    HIGH

Pressed:
    LOW
"""

from machine import Pin
import time
import sys


# -------------------------------------------------
# Configuration
# -------------------------------------------------

def _default_setup_button_pin():
    machine_name = ""

    try:
        machine_name = str(sys.implementation._machine)
    except Exception:
        pass

    # GPIO 26-37 are reserved on ESP32-S3 with flash/PSRAM.
    if "S3" in machine_name or "s3" in machine_name:
        return 4

    return 27


SETUP_BUTTON_PIN = _default_setup_button_pin()
HOLD_TIME_MS = 5000


# -------------------------------------------------
# Setup Button
# -------------------------------------------------

class SetupButton:

    def __init__(self):

        self.button = Pin(
            SETUP_BUTTON_PIN,
            Pin.IN,
            Pin.PULL_UP
        )

    # ---------------------------------------------

    def is_pressed(self):
        """
        Returns True while the button is physically
        being pressed.
        """

        return self.button.value() == 0

    # ---------------------------------------------

    def wait_for_long_press(self):
        """
        Returns True if the button remains pressed
        continuously for HOLD_TIME_MS.

        Returns False if the user releases it early.
        """

        if not self.is_pressed():
            return False

        print("Setup button pressed.")

        start = time.ticks_ms()

        while self.is_pressed():

            elapsed = time.ticks_diff(
                time.ticks_ms(),
                start
            )

            if elapsed >= HOLD_TIME_MS:

                print("Long press detected.")

                return True

            time.sleep_ms(50)

        print("Button released before timeout.")

        return False