# wifi_storage.py

import json

WIFI_CONFIG_FILE = "wifi_config.json"
SETUP_AP_CONFIG_FILE = "setup_ap.json"
HOSTNAME_CONFIG_FILE = "hostname.json"
PRODUCT_CONFIG_FILE = "product.json"

DEFAULT_SETUP_AP_SSID = "Esaatech-Setup"
DEFAULT_SETUP_AP_PASSWORD = "setup1234"
DEFAULT_HOSTNAME = "esaatech-access"


def save_credentials(ssid, password):
    config = {
        "ssid": ssid,
        "password": password
    }

    with open(WIFI_CONFIG_FILE, "w") as file:
        json.dump(config, file)


def load_credentials():
    try:
        with open(WIFI_CONFIG_FILE, "r") as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def delete_credentials():
    try:
        import os
        os.remove(WIFI_CONFIG_FILE)
    except OSError:
        pass


def load_setup_ap_config():
    """
    Returns the setup Access Point name and password.

    Falls back to defaults when nothing is saved yet.
    """

    try:
        with open(SETUP_AP_CONFIG_FILE, "r") as file:
            config = json.load(file)

        ssid = (config.get("ssid") or "").strip()
        password = config.get("password") or ""

        if not ssid:
            ssid = DEFAULT_SETUP_AP_SSID

        if len(password) < 8:
            password = DEFAULT_SETUP_AP_PASSWORD

        return {
            "ssid": ssid,
            "password": password
        }

    except (OSError, ValueError):
        return {
            "ssid": DEFAULT_SETUP_AP_SSID,
            "password": DEFAULT_SETUP_AP_PASSWORD
        }


def save_setup_ap_config(ssid, password):
    """
    Saves the setup Access Point name and password.

    WPA2 requires a password of at least 8 characters.
    """

    ssid = (ssid or "").strip()
    password = password or ""

    if not ssid:
        raise ValueError("Setup AP name is required.")

    if len(ssid) > 32:
        raise ValueError("Setup AP name must be 32 characters or fewer.")

    if len(password) < 8:
        raise ValueError(
            "Setup AP password must be at least 8 characters."
        )

    if len(password) > 63:
        raise ValueError(
            "Setup AP password must be 63 characters or fewer."
        )

    config = {
        "ssid": ssid,
        "password": password
    }

    with open(SETUP_AP_CONFIG_FILE, "w") as file:
        json.dump(config, file)

    return config


def _sanitize_hostname(hostname):
    name = (hostname or "").strip().lower()

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
        raise ValueError(
            "Local name is required. Use letters, numbers, and hyphens."
        )

    if len(name) > 32:
        raise ValueError("Local name must be 32 characters or fewer.")

    return name


def load_hostname():
    """
    Returns the saved LAN hostname (without .local).
    """

    try:
        with open(HOSTNAME_CONFIG_FILE, "r") as file:
            config = json.load(file)

        return _sanitize_hostname(config.get("hostname"))

    except (OSError, ValueError):
        return DEFAULT_HOSTNAME


def save_hostname(hostname):
    """
    Saves the LAN hostname used for DHCP / mDNS (.local).
    """

    name = _sanitize_hostname(hostname)

    config = {
        "hostname": name
    }

    with open(HOSTNAME_CONFIG_FILE, "w") as file:
        json.dump(config, file)

    return name


def load_product_config():
    """
    Product UI flags for the networking template.

    test_mode: when True, dashboard shows a link to /test
    for GPIO output experiments (Task 21).
    """

    try:
        with open(PRODUCT_CONFIG_FILE, "r") as file:
            config = json.load(file)

        return {
            "test_mode": bool(config.get("test_mode", False))
        }

    except (OSError, ValueError):
        return {
            "test_mode": False
        }


def save_product_config(test_mode):
    config = {
        "test_mode": bool(test_mode)
    }

    with open(PRODUCT_CONFIG_FILE, "w") as file:
        json.dump(config, file)

    return config
