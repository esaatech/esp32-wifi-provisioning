# wifi_manager.py

import network
import time


class WiFiManager:

    def __init__(self):
        self.station = network.WLAN(network.STA_IF)
        self.access_point = network.WLAN(network.AP_IF)

    def start_access_point(
        self,
        ssid="SBTY-Access-Control-Setup",
        password="setup1234"
    ):
        self.access_point.active(True)

        self.access_point.config(
            essid=ssid,
            password=password,
            authmode=network.AUTH_WPA2_PSK
        )

        while not self.access_point.active():
            time.sleep_ms(100)

        return self.access_point.ifconfig()

    def stop_access_point(self):
        self.access_point.active(False)

    def scan_networks(self):
        self.station.active(True)

        results = self.station.scan()
        networks = []

        seen = set()

        for result in results:
            ssid_bytes = result[0]
            signal_strength = result[3]
            security = result[4]

            try:
                ssid = ssid_bytes.decode("utf-8")
            except UnicodeError:
                continue

            if not ssid or ssid in seen:
                continue

            seen.add(ssid)

            networks.append({
                "ssid": ssid,
                "signal": signal_strength,
                "security": security
            })

        networks.sort(
            key=lambda network_info: network_info["signal"],
            reverse=True
        )

        return networks

    def connect(self, ssid, password, timeout_seconds=15):
        self.station.active(True)

        if self.station.isconnected():
            self.station.disconnect()
            time.sleep_ms(500)

        self.station.connect(ssid, password)

        start_time = time.time()

        while not self.station.isconnected():
            if time.time() - start_time >= timeout_seconds:
                return {
                    "success": False,
                    "message": "Connection timed out."
                }

            time.sleep_ms(250)

        return {
            "success": True,
            "message": "Connected successfully.",
            "ip_address": self.station.ifconfig()[0]
        }

    def disconnect(self):
        if self.station.active() and self.station.isconnected():
            self.station.disconnect()
            time.sleep_ms(300)

    def is_connected(self):
        return self.station.isconnected()

    def get_ip_address(self):
        if not self.station.isconnected():
            return None

        return self.station.ifconfig()[0]