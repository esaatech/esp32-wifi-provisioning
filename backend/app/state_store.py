"""
In-memory mirror of the last known device state from MQTT.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from .config import GPIO_PINS


class DeviceStateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.mqtt_connected = False
        self.gpio: Dict[int, Optional[bool]] = {pin: None for pin in GPIO_PINS}
        self.proximity: Optional[str] = None  # CLEAR / DETECTED
        self.proximity_seq: Optional[int] = None
        self.updated_at: Optional[float] = None

    def set_mqtt_connected(self, connected: bool) -> None:
        with self._lock:
            self.mqtt_connected = connected
            self.updated_at = time.time()

    def set_gpio(self, pin: int, on: bool) -> Dict[str, Any]:
        with self._lock:
            self.gpio[pin] = bool(on)
            self.updated_at = time.time()
            return self._snapshot_unlocked()

    def set_proximity(self, label: str, seq: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            self.proximity = label.upper()
            if seq is not None:
                self.proximity_seq = seq
            self.updated_at = time.time()
            return self._snapshot_unlocked()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> Dict[str, Any]:
        return {
            "mqtt_connected": self.mqtt_connected,
            "gpio": {
                str(pin): (
                    None if value is None else ("ON" if value else "OFF")
                )
                for pin, value in self.gpio.items()
            },
            "proximity": self.proximity,
            "proximity_seq": self.proximity_seq,
            "proximity_label": _proximity_human(self.proximity),
            "updated_at": self.updated_at,
        }


def _proximity_human(label: Optional[str]) -> str:
    if label == "DETECTED":
        return "Object nearby"
    if label == "CLEAR":
        return "Nothing in range"
    return "Waiting for sensor…"


store = DeviceStateStore()
