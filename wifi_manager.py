# wifi_manager.py

import network
import time


# Default LAN hostname for DHCP / mDNS (.local).
# Override via hostname.json / the admin page editor.
DEFAULT_HOSTNAME = "esaatech-access"


class WiFiManager:

    def __init__(self, hostname=None):
        if hostname is None:
            try:
                from wifi_storage import load_hostname
                hostname = load_hostname()
            except Exception:
                hostname = DEFAULT_HOSTNAME

        self.hostname = self._sanitize_hostname(hostname)
        self.station = network.WLAN(network.STA_IF)
        # Create the AP interface only when setup mode needs it.
        # Holding both interfaces from boot costs Wi-Fi heap.
        self.access_point = None
        self.apply_hostname()

    # -------------------------------------------------

    def _get_access_point(self):
        if self.access_point is None:
            self.access_point = network.WLAN(network.AP_IF)

        return self.access_point

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
        ssid="Esaatech-Setup",
        password="setup1234"
    ):
        import gc

        # AP+STA together needs a lot of IDF heap. Turn the
        # station completely off before starting setup AP so
        # boards without spare RAM do not hit WiFi OOM.
        if self.station.active():
            try:
                if self.station.isconnected():
                    self.station.disconnect()
                    time.sleep_ms(200)
            except OSError:
                pass

            self.station.active(False)
            time.sleep_ms(300)

        access_point = self._get_access_point()

        if access_point.active():
            access_point.active(False)
            time.sleep_ms(200)

        gc.collect()

        access_point.active(True)

        access_point.config(
            essid=ssid,
            password=password,
            authmode=network.AUTH_WPA2_PSK
        )

        while not access_point.active():
            time.sleep_ms(100)

        return access_point.ifconfig()

    def stop_access_point(self):
        if self.access_point is None:
            return

        self.access_point.active(False)

    def scan_networks(self):
        import gc

        gc.collect()
        self.station.active(True)
        time.sleep_ms(200)

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
        import gc

        # Hostname must be applied before the station connects
        # so DHCP and mDNS pick it up.
        self.apply_hostname()

        # Make sure setup AP is not holding Wi-Fi memory.
        if self.access_point is not None and self.access_point.active():
            self.access_point.active(False)
            time.sleep_ms(200)

        gc.collect()

        # Clean radio restart before joining the router.
        if self.station.active():
            try:
                if self.station.isconnected():
                    self.station.disconnect()
                    time.sleep_ms(200)
            except OSError:
                pass

            self.station.active(False)
            time.sleep_ms(300)

        gc.collect()
        self.station.active(True)
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
        if not self.station.active():
            return

        try:
            if self.station.isconnected():
                self.station.disconnect()
                time.sleep_ms(300)
        except OSError:
            pass

        # Fully release station Wi-Fi memory.
        self.station.active(False)
        time.sleep_ms(200)

    def is_connected(self):
        return self.station.active() and self.station.isconnected()

    def get_ip_address(self):
        if not self.is_connected():
            return None

        return self.station.ifconfig()[0]
