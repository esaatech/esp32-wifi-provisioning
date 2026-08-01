# mqtt_client.py
#
# Persistent MQTT session for EMQX Cloud (Tasks 24–27).
#
# - TLS on port 8883 with CA verification + SNI
# - Unique client ID from the chip unique_id
# - Subscribe to one command topic per test GPIO (16 / 42 / 47)
# - Accept ON / OFF payloads and drive the shared TestOutputs pins
# - Publish retained state on .../gpio/<pin>/state after changes and reconnect
# - Publish FC-51 proximity telemetry on .../telemetry/proximity (Task 27)
# - Keep-alive pings and automatic reconnect with backoff
# - NTP time sync before TLS (ESP32 RTC starts at epoch; certs fail otherwise)

import gc
import time

import machine
from ubinascii import hexlify

from wifi_storage import load_mqtt_config
from test_outputs import TEST_PINS, get_shared_test_outputs


def _parse_on_off(payload):
    """
    Returns True/False for valid commands, or None if invalid.

    Plaintext only: ON / OFF (also 1/0, true/false).
    Whitespace is trimmed; braces are not accepted.
    """

    text = (payload or "").strip().upper()

    if text in ("ON", "1", "TRUE"):
        return True

    if text in ("OFF", "0", "FALSE"):
        return False

    return None


def _pin_from_command_topic(topic_text, client_id):
    """
    Expect: devices/<client_id>/gpio/<pin>/command
    """

    prefix = "devices/{}/gpio/".format(client_id)
    suffix = "/command"

    if not topic_text.startswith(prefix) or not topic_text.endswith(suffix):
        return None

    middle = topic_text[len(prefix) : -len(suffix)]

    try:
        pin_number = int(middle)
    except ValueError:
        return None

    if pin_number not in TEST_PINS:
        return None

    return pin_number


def _state_topic(client_id, pin_number):
    return "devices/{}/gpio/{}/state".format(client_id, pin_number)


def _proximity_topic(client_id):
    return "devices/{}/telemetry/proximity".format(client_id)


class MqttSession:
    """
    Non-blocking MQTT client meant for the main station loop.
    """

    def __init__(self):
        self._client = None
        self._connected = False
        self._config = None
        self._client_id = None
        self._gpio_topics = []
        self._last_ping_ms = 0
        self._next_retry_ms = 0
        self._backoff_ms = 1000
        self._enabled = False
        self._time_synced = False
        self._outputs = None
        self._proximity_seq = 0

        self.reload_config()

    def reload_config(self):
        config = load_mqtt_config()
        self._config = config
        self._enabled = config is not None

        if not self._enabled:
            print("MQTT: no mqtt_config.json (or disabled) — skipping.")
            return False

        self._client_id = self._build_client_id()
        self._gpio_topics = [
            "devices/{}/gpio/{}/command".format(self._client_id, pin)
            for pin in TEST_PINS
        ]

        print("MQTT: configured for", config["host"])
        print("MQTT: client id", self._client_id)
        for topic in self._gpio_topics:
            print("MQTT: command topic", topic)
        for pin in TEST_PINS:
            print("MQTT: state topic", _state_topic(self._client_id, pin))
        print("MQTT: telemetry topic", _proximity_topic(self._client_id))

        # Bind shared GPIO early so /test toggles can publish once MQTT is up.
        self._get_outputs()
        return True

    def _build_client_id(self):
        chip = hexlify(machine.unique_id()).decode()
        return "esaatech-{}".format(chip)

    def _get_outputs(self):
        if self._outputs is None:
            self._outputs = get_shared_test_outputs()
            # HTTP /test and MQTT commands both report through this hook.
            self._outputs.on_change = self._on_gpio_changed
        return self._outputs

    def _on_gpio_changed(self, pin_number, on):
        self.publish_gpio_state(pin_number)

    def is_connected(self):
        return self._connected

    def publish_gpio_state(self, pin_number):
        """
        Publish retained ON/OFF for one pin (Task 26).
        """

        if not self._connected or self._client is None or self._client_id is None:
            return False

        try:
            on = self._get_outputs().get_output(pin_number)
        except ValueError:
            return False

        topic = _state_topic(self._client_id, pin_number)
        payload = "ON" if on else "OFF"

        try:
            self._client.publish(topic, payload, retain=True)
            print("MQTT state", topic, "=>", payload)
            return True
        except Exception as error:
            print("MQTT: state publish failed:", repr(error))
            return False

    def publish_all_gpio_states(self):
        for pin_number in TEST_PINS:
            self.publish_gpio_state(pin_number)

    def publish_proximity(self, label):
        """
        Publish FC-51 proximity telemetry (Task 27).

        Event-driven: call only when CLEAR ↔ DETECTED changes,
        and once after MQTT connect for retained last-known state.

        Payload example: "DETECTED seq=3"
        """

        if not self._connected or self._client is None or self._client_id is None:
            return False

        label = (label or "").strip().upper()
        if label not in ("CLEAR", "DETECTED"):
            return False

        self._proximity_seq += 1
        topic = _proximity_topic(self._client_id)
        payload = "{} seq={}".format(label, self._proximity_seq)

        try:
            self._client.publish(topic, payload, retain=True)
            print("MQTT telemetry", topic, "=>", payload)
            return True
        except Exception as error:
            print("MQTT: proximity publish failed:", repr(error))
            return False

    def stop(self):
        """
        Tear down the MQTT socket cleanly (e.g. Wi-Fi lost / setup reboot).
        """

        client = self._client
        self._client = None
        self._connected = False
        self._last_ping_ms = 0
        self._next_retry_ms = 0
        self._backoff_ms = 1000

        if client is None:
            return

        try:
            client.disconnect()
        except Exception as error:
            print("MQTT: disconnect error:", repr(error))

        print("MQTT: stopped.")

    def poll(self):
        """
        Call frequently from the main loop while Wi-Fi is connected.
        """

        if not self._enabled:
            return

        now = time.ticks_ms()

        if not self._connected:
            if time.ticks_diff(now, self._next_retry_ms) < 0:
                return
            self._connect()
            return

        try:
            self._client.check_msg()
            self._maybe_ping(now)
        except Exception as error:
            print("MQTT: session error:", repr(error))
            self._handle_drop()

    def _maybe_ping(self, now):
        keepalive = self._config["keepalive"]
        interval_ms = max(5000, (keepalive * 1000) // 2)

        if self._last_ping_ms == 0:
            self._last_ping_ms = now
            return

        if time.ticks_diff(now, self._last_ping_ms) < interval_ms:
            return

        self._client.ping()
        self._last_ping_ms = now

    def _on_message(self, topic, msg):
        try:
            topic_text = topic.decode() if isinstance(topic, bytes) else topic
        except Exception:
            topic_text = repr(topic)

        try:
            payload = msg.decode() if isinstance(msg, bytes) else str(msg)
        except Exception:
            payload = repr(msg)

        print("MQTT: message on", topic_text, "=>", payload)

        pin_number = _pin_from_command_topic(topic_text, self._client_id)
        if pin_number is None:
            print("MQTT: ignored (not a known GPIO command topic)")
            return

        on = _parse_on_off(payload)
        if on is None:
            print("MQTT: invalid payload for GPIO", pin_number, "(use ON or OFF)")
            return

        try:
            self._get_outputs().set_output(pin_number, on)
            print(
                "MQTT GPIO {}: {}".format(
                    pin_number, "ON" if on else "OFF"
                )
            )
        except Exception as error:
            print("MQTT: GPIO set failed:", repr(error))

    def _ensure_time(self):
        """
        TLS certificate checks need a sane RTC clock.
        Fresh boards boot near 2000-01-01 and reject modern certs.
        """

        if self._time_synced:
            return True

        try:
            import ntptime

            print("MQTT: syncing time via NTP...")
            ntptime.host = "pool.ntp.org"
            ntptime.settime()
            now = time.localtime()
            print(
                "MQTT: UTC time",
                "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                    now[0], now[1], now[2], now[3], now[4], now[5]
                ),
            )
            self._time_synced = True
            return True

        except Exception as error:
            print("MQTT: NTP sync failed:", repr(error))
            return False

    def _connect(self):
        config = self._config
        if config is None:
            return

        if not self._ensure_time():
            self._schedule_retry()
            return

        print("MQTT: connecting to", config["host"], "port", config["port"])
        gc.collect()

        try:
            with open(config["ca_file"], "rb") as file:
                cadata = file.read()
        except OSError as error:
            print(
                "MQTT: missing CA file",
                config["ca_file"],
                ":",
                repr(error),
            )
            self._schedule_retry()
            return

        try:
            import ssl
            from umqtt.simple import MQTTClient

            ssl_params = {
                "cert_reqs": ssl.CERT_REQUIRED,
                "cadata": cadata,
                "server_hostname": config["host"],
            }

            client = MQTTClient(
                client_id=self._client_id,
                server=config["host"],
                port=config["port"],
                user=config["username"],
                password=config["password"],
                keepalive=config["keepalive"],
                ssl=True,
                ssl_params=ssl_params,
            )
            client.set_callback(self._on_message)
            client.connect(clean_session=True, timeout=20)

            for topic in self._gpio_topics:
                client.subscribe(topic)

            self._client = client
            self._connected = True
            self._last_ping_ms = time.ticks_ms()
            self._backoff_ms = 1000

            # Shared GPIO + HTTP change hook, then report current state.
            self._get_outputs()
            self.publish_all_gpio_states()

            print("MQTT: connected.")
            print("MQTT: subscribed to GPIO command topics", TEST_PINS)
            print("MQTT: published retained GPIO states")

        except Exception as error:
            print("MQTT: connect failed:", repr(error))
            self._client = None
            self._connected = False
            self._schedule_retry()

    def _handle_drop(self):
        self.stop()
        self._schedule_retry()

    def _schedule_retry(self):
        delay = self._backoff_ms
        self._next_retry_ms = time.ticks_add(time.ticks_ms(), delay)
        print("MQTT: retry in", delay, "ms")

        self._backoff_ms = min(delay * 2, 30000)
