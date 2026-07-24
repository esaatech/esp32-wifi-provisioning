# wifi_manager.py

import network
import time


# LAN hostname advertised over DHCP and mDNS.
# The admin page is reachable at http://sbty-access.local/
# when mDNS is supported on the client.
DEFAULT_HOSTNAME = "sbty-access"


class WiFiManager:

    def __init__(self, hostname=DEFAULT_HOSTNAME):
        self.hostname = self._sanitize_hostname(hostname)
        self.station = network.WLAN(network.STA_IF)
        self.access_point = network.WLAN(network.AP_IF)
        self.apply_hostname()

    # -------------------------------------------------

    def _sanitize_hostname(self, hostname):
        name = (hostname or DEFAULT_HOSTNAME).strip().lower()

        cleaned = []

        for character in name:
            if (
                ("a" <= character <= "z")
                or ("0" <= character <= "9")
                or character == "-"
            ):
                cleaned.append(character)

        name = "".join(cleaned).strip("-")

        if not name:
            name = DEFAULT_HOSTNAME

        return name[:32]

    # -------------------------------------------------

    def apply_hostname(self, hostname=None):
        """
        Sets the device hostname used for DHCP and mDNS.

        Must be called before connecting to Wi-Fi so the
        name is included in the DHCP request and mDNS
        responder startup.
        """

        if hostname is not None:
            self.hostname = self._sanitize_hostname(hostname)

        try:
            network.hostname(self.hostname)
            print("Device hostname set to:", self.hostname)
        except Exception as error:
            print("Could not set hostname:", repr(error))

        return self.hostname

    # -------------------------------------------------

    def get_hostname(self):
        try:
            current = network.hostname()

            if current:
                return current
        except Exception:
            pass

        return self.hostname

    # -------------------------------------------------

    def get_mdns_name(self):
        return self.get_hostname() + ".local"

    # -------------------------------------------------

    def get_local_url(self):
        return "http://{}/".format(self.get_mdns_name())

    # -------------------------------------------------

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
        # Hostname must be applied before the station connects
        # so DHCP and mDNS pick it up.
        self.apply_hostname()

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
            "ip_address": self.station.ifconfig()[0],
            "hostname": self.get_hostname(),
            "local_url": self.get_local_url()
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
