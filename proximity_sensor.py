"""
proximity_sensor.py

FC-51 infrared obstacle / proximity sensor (Task 27).

Hardware (ESP32-S3 breadboard):
    FC-51 VCC  -> 3V3
    FC-51 GND  -> GND
    FC-51 OUT  -> GPIO 4

The module OUT pin is digital:
    HIGH (1) — no obstacle (CLEAR)
    LOW  (0) — obstacle in range (DETECTED)

Detection distance is set with the onboard potentiometer
(roughly 2–30 cm). No ADC is required.
"""

from machine import Pin


PROXIMITY_PIN = 4


class ProximitySensor:
    """
    Digital FC-51 reader with simple change detection.
    """

    def __init__(self, pin=PROXIMITY_PIN):
        self.pin = Pin(int(pin), Pin.IN)
        self._last_raw = self.pin.value()

    def raw(self):
        """Return the current OUT pin value (0 or 1)."""
        return self.pin.value()

    def is_detected(self):
        """True when an obstacle is in range (OUT is LOW)."""
        return self.raw() == 0

    def state_label(self):
        """Human-readable CLEAR / DETECTED."""
        return "DETECTED" if self.is_detected() else "CLEAR"

    def poll_change(self):
        """
        Return a (changed, label) tuple.

        changed is True only when OUT flips HIGH↔LOW since
        the last call — useful for event-driven MQTT publish.
        """
        raw = self.raw()
        changed = raw != self._last_raw
        if changed:
            self._last_raw = raw
        return changed, ("DETECTED" if raw == 0 else "CLEAR")
