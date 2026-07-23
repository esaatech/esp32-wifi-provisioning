# wifi_storage.py

import json

WIFI_CONFIG_FILE = "wifi_config.json"


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