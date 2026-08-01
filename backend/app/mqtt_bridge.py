"""
Background MQTT client bridging EMQX ↔ FastAPI (Task 28).

Runs paho-mqtt in a daemon thread so FastAPI stays responsive.
Incoming state/telemetry updates the shared store and notifies
WebSocket listeners via an asyncio-safe callback.
"""

from __future__ import annotations

import logging
import os
import re
import ssl
import threading
import uuid
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from .config import GPIO_PINS, Settings
from .state_store import store

logger = logging.getLogger("esaatech.mqtt")

_STATE_RE = re.compile(r"^devices/[^/]+/gpio/(\d+)/state$")
_PROX_RE = re.compile(r"^devices/[^/]+/telemetry/proximity$")


def _unique_client_id(base: str) -> str:
    """
    EMQX disconnects the older session when two clients share an ID.
    Append pid + short suffix so reload / second uvicorn don't fight.
    """
    base = (base or "esaatech-backend").strip() or "esaatech-backend"
    return f"{base}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


class MqttBridge:
    def __init__(
        self,
        settings: Settings,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.settings = settings
        self.on_event = on_event
        self._client: Optional[mqtt.Client] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        if not self.settings.mqtt_password:
            logger.error("MQTT password missing — set MQTT_PASSWORD or mqtt_config.json")
            return

        ca = self.settings.ca_path
        if not ca.is_file():
            logger.error("MQTT CA file not found: %s", ca)
            return

        self._stop.clear()
        client_id = _unique_client_id(self.settings.mqtt_client_id)
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.username_pw_set(
            self.settings.mqtt_username,
            self.settings.mqtt_password,
        )

        # Trust EMQX CA plus the system store (Python is stricter than MicroPython).
        tls_context = ssl.create_default_context()
        tls_context.load_verify_locations(cafile=str(ca))
        tls_context.check_hostname = True
        tls_context.verify_mode = ssl.CERT_REQUIRED
        client.tls_set_context(tls_context)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

        self._client = client
        self._thread = threading.Thread(
            target=self._run,
            name="mqtt-bridge",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "MQTT bridge starting → %s:%s as %s",
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            client_id,
        )

    def stop(self) -> None:
        self._stop.set()
        client = self._client
        if client is not None:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception as error:
                logger.warning("MQTT stop error: %s", error)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._client = None
        store.set_mqtt_connected(False)

    def publish_gpio_command(self, pin: int, on: bool) -> None:
        if pin not in GPIO_PINS:
            raise ValueError(f"Pin {pin} is not a controlled GPIO")
        client = self._client
        if client is None or not store.mqtt_connected:
            raise RuntimeError("MQTT is not connected")
        topic = self.settings.command_topic(pin)
        payload = "ON" if on else "OFF"
        info = client.publish(topic, payload, qos=0, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed rc={info.rc}")
        logger.info("Published %s → %s", payload, topic)

    def _run(self) -> None:
        assert self._client is not None
        try:
            self._client.connect(
                self.settings.mqtt_host,
                self.settings.mqtt_port,
                keepalive=self.settings.mqtt_keepalive,
            )
            self._client.loop_forever(retry_first_connection=True)
        except Exception as error:
            logger.exception("MQTT loop ended: %s", error)
            store.set_mqtt_connected(False)
            self._emit({"type": "mqtt", "connected": False})

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        ok = reason_code == 0 or getattr(reason_code, "value", reason_code) == 0
        if not ok:
            logger.error("MQTT connect refused: %s", reason_code)
            store.set_mqtt_connected(False)
            self._emit({"type": "mqtt", "connected": False})
            return

        client.subscribe(self.settings.state_filter(), qos=0)
        client.subscribe(self.settings.proximity_topic(), qos=0)
        store.set_mqtt_connected(True)
        logger.info(
            "MQTT connected; subscribed to state + proximity for %s",
            self.settings.device_id,
        )
        self._emit({"type": "mqtt", "connected": True, "state": store.snapshot()})

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        store.set_mqtt_connected(False)
        logger.warning("MQTT disconnected: %s", reason_code)
        self._emit({"type": "mqtt", "connected": False})

    def _on_message(self, client, userdata, message):
        topic = message.topic
        try:
            payload = message.payload.decode("utf-8").strip()
        except Exception:
            payload = repr(message.payload)

        state_match = _STATE_RE.match(topic)
        if state_match:
            pin = int(state_match.group(1))
            if pin not in GPIO_PINS:
                return
            text = payload.upper()
            if text not in ("ON", "OFF"):
                logger.warning("Ignored GPIO state payload: %s", payload)
                return
            snapshot = store.set_gpio(pin, text == "ON")
            self._emit(
                {
                    "type": "gpio",
                    "pin": pin,
                    "value": text,
                    "state": snapshot,
                }
            )
            return

        if _PROX_RE.match(topic):
            label, seq = _parse_proximity(payload)
            if label is None:
                logger.warning("Ignored proximity payload: %s", payload)
                return
            snapshot = store.set_proximity(label, seq)
            self._emit(
                {
                    "type": "proximity",
                    "value": label,
                    "seq": seq,
                    "state": snapshot,
                }
            )

    def _emit(self, event: dict) -> None:
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception as error:
                logger.warning("Event callback failed: %s", error)


def _parse_proximity(payload: str):
    text = payload.strip().upper()
    # "DETECTED seq=2" or plain "CLEAR"
    parts = text.split()
    if not parts:
        return None, None
    label = parts[0]
    if label not in ("CLEAR", "DETECTED"):
        return None, None
    seq = None
    for part in parts[1:]:
        if part.startswith("SEQ="):
            try:
                seq = int(part.split("=", 1)[1])
            except ValueError:
                seq = None
    return label, seq
