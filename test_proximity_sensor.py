"""
Live FC-51 test on GPIO 4.

Upload, then run:
    mpremote connect <port> run test_proximity_sensor.py

Wave a hand in front of the sensor. Expect CLEAR ↔ DETECTED.
"""

from proximity_sensor import ProximitySensor
import time

sensor = ProximitySensor()

print("FC-51 proximity test (GPIO 4)")
print("raw=0 DETECTED, raw=1 CLEAR")
print("Wave hand in front of the sensor.")
print("----------------------------")
print("start:", sensor.raw(), sensor.state_label())

while True:
    changed, label = sensor.poll_change()
    if changed:
        print("CHANGE", sensor.raw(), label)
    time.sleep_ms(50)
