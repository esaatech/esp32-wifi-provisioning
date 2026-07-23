# test_status_led.py

from status_led import StatusLED
import time


status_led = StatusLED()

print("LED ON")

status_led.on()
time.sleep(2)

print("LED OFF")

status_led.off()
time.sleep(2)

print("LED BLINKING")

while True:
    status_led.update_blink()
    time.sleep_ms(20)