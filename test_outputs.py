"""
test_outputs.py

GPIO outputs used by the optional Test page (Task 21) and
MQTT remote control (Tasks 25–26).

Pins (ESP32-S3 breadboard wiring):
    GPIO 16, 42, 47  — LED, buzzer, or other active-high loads

These are separate from the status LED (GPIO 2).
"""

from machine import Pin


TEST_PINS = (16, 42, 47)

_shared_outputs = None


def get_shared_test_outputs():
    """
    One shared pin controller for HTTP /test and MQTT commands.
    """

    global _shared_outputs

    if _shared_outputs is None:
        _shared_outputs = TestOutputs()
        print("Test outputs ready on pins:", _shared_outputs.allowed_pins())

    return _shared_outputs


class TestOutputs:
    """
    Simple digital outputs for the LAN test dashboard and MQTT.

    on_change(pin, on) is optional and used to publish MQTT state
    whenever a pin changes (HTTP or MQTT).
    """

    def __init__(self, pins=TEST_PINS):
        self.pins = {}
        self.state = {}
        self.on_change = None

        for pin_number in pins:
            self.pins[pin_number] = Pin(pin_number, Pin.OUT, value=0)
            self.state[pin_number] = False

    def allowed_pins(self):
        return tuple(self.pins.keys())

    def set_output(self, pin_number, on):
        pin_number = int(pin_number)

        if pin_number not in self.pins:
            raise ValueError("Pin {} is not a test output.".format(pin_number))

        value = 1 if on else 0
        self.pins[pin_number].value(value)
        self.state[pin_number] = bool(on)

        if self.on_change is not None:
            try:
                self.on_change(pin_number, self.state[pin_number])
            except Exception as error:
                print("Test outputs on_change error:", repr(error))

        return self.state[pin_number]

    def get_output(self, pin_number):
        pin_number = int(pin_number)

        if pin_number not in self.pins:
            raise ValueError("Pin {} is not a test output.".format(pin_number))

        return self.state[pin_number]

    def snapshot(self):
        items = []

        for pin_number in sorted(self.pins.keys()):
            items.append(
                {
                    "pin": pin_number,
                    "on": self.state[pin_number],
                }
            )

        return items
