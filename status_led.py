"""
status_led.py

Controls the ESP32 networking status LED.

GPIO 2 onboard LED:

    Blinking  = Wi-Fi disconnected or setup mode
    Solid ON  = Wi-Fi connected
    OFF       = LED disabled
"""

from machine import Pin, Timer


LED_PIN = 2
ACTIVE_HIGH = True
BLINK_INTERVAL_MS = 500


class StatusLED:

    def __init__(self):
        self.led = Pin(
            LED_PIN,
            Pin.OUT,
            value=self._off_value()
        )

        self.timer = Timer(-1)
        self.is_blinking = False

    # -------------------------------------------------

    def _on_value(self):
        return 1 if ACTIVE_HIGH else 0

    # -------------------------------------------------

    def _off_value(self):
        return 0 if ACTIVE_HIGH else 1

    # -------------------------------------------------

    def _timer_callback(self, timer):
        """
        Called automatically by the ESP32 timer.

        Keep timer callbacks very small and simple.
        """

        self.led.value(
            self._off_value()
            if self.led.value() == self._on_value()
            else self._on_value()
        )

    # -------------------------------------------------

    def blink(self, interval_ms=BLINK_INTERVAL_MS):
        """
        Starts continuous blinking.

        The timer allows the LED to keep blinking even
        while another part of the application is blocking.
        """

        self.timer.deinit()

        self.is_blinking = True
        self.led.value(self._off_value())

        self.timer.init(
            period=interval_ms,
            mode=Timer.PERIODIC,
            callback=self._timer_callback
        )

    # -------------------------------------------------

    def solid(self):
        """
        Stops blinking and keeps the LED steadily ON.
        """

        self.timer.deinit()
        self.is_blinking = False
        self.led.value(self._on_value())

    # -------------------------------------------------

    def off(self):
        """
        Stops blinking and turns the LED OFF.
        """

        self.timer.deinit()
        self.is_blinking = False
        self.led.value(self._off_value())