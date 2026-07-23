"""
setup_button.py

Monitors the dedicated Wi-Fi setup button.

Hardware
--------
GPIO27 ---- Push Button ---- GND

The ESP32 internal pull-up resistor is used.

Normal state:
    HIGH

Pressed:
    LOW
"""

from machine import Pin
import time


# -------------------------------------------------
# Configuration
# -------------------------------------------------

SETUP_BUTTON_PIN = 27
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