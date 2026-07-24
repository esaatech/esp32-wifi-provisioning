# wifi_storage.py

import json

WIFI_CONFIG_FILE = "wifi_config.json"
SETUP_AP_CONFIG_FILE = "setup_ap.json"

DEFAULT_SETUP_AP_SSID = "SBTY-Access-Control-Setup"
DEFAULT_SETUP_AP_PASSWORD = "setup1234"


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
