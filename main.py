# main.py
#
# Standalone ESP32 networking application.
#
# Responsibilities:
# - Connect using saved Wi-Fi credentials.
# - Start setup mode when no valid credentials exist.
# - Host a permanent LAN admin page while connected.
# - Keep a persistent MQTT client session while connected (Task 24).
# - Poll FC-51 proximity on GPIO 4 (Task 27; MQTT publish next).
# - Monitor a dedicated setup button.
# - Display Wi-Fi status using the onboard LED.
#
# LED behaviour:
# - Blinking: Wi-Fi disconnected or setup mode
# - Solid: Wi-Fi connected
#
# Important MicroPython note:
# Heavy modules (wifi_portal / admin_server) are imported lazily
# AFTER Wi-Fi connects. Loading them at boot steals IDF heap and
# can make station connect time out.

import gc
import machine
import time

from wifi_manager import WiFiManager
from wifi_storage import load_credentials, load_setup_ap_config
from setup_button import SetupButton
from status_led import StatusLED
from proximity_sensor import ProximitySensor


# Soft-reboot flag used when the setup button is pressed while
# the permanent admin server has been running. A clean restart
# frees Wi-Fi / IDF heap so the setup Access Point can start.
FORCE_SETUP_FLAG = "force_setup.flag"


# -------------------------------------------------
# Create lightweight objects first (before Wi-Fi)
# -------------------------------------------------

wifi = WiFiManager()
setup_button = SetupButton()
status_led = StatusLED()
proximity = ProximitySensor()

# Created only after Wi-Fi is up (or when setup needs it).
admin_server = None
mqtt_session = None
_proximity_mqtt_synced = False


def get_admin_server():
    """
    Lazily create the permanent admin server.

    Importing admin_server also pulls in wifi_portal and
    admin_auth, which use a lot of RAM.
    """

    global admin_server

    if admin_server is None:
        gc.collect()
        from admin_server import AdminServer

        admin_server = AdminServer(wifi)
        print("Admin server module loaded.")

    return admin_server


def get_mqtt_session():
    """
    Lazily create the MQTT session (Task 24).

    Skips quietly when mqtt_config.json is missing.
    """

    global mqtt_session

    if mqtt_session is None:
        gc.collect()
        from mqtt_client import MqttSession

        mqtt_session = MqttSession()
        print("MQTT session module loaded.")

    return mqtt_session


def stop_mqtt_session():
    global mqtt_session

    if mqtt_session is not None:
        mqtt_session.stop()



# -------------------------------------------------
# Setup-mode reboot helpers
# -------------------------------------------------

def force_setup_requested():
    try:
        with open(FORCE_SETUP_FLAG, "r"):
            pass
    except OSError:
        return False

    try:
        import os
        os.remove(FORCE_SETUP_FLAG)
    except OSError:
        pass

    return True


def request_setup_reboot():
    """
    Stops the admin server and reboots into setup mode.

    This avoids WiFi Out of Memory when switching from a
    long-running station + admin page into Access Point mode.
    """

    print("Preparing clean restart into Wi-Fi setup mode...")

    stop_mqtt_session()

    server = admin_server

    if server is not None:
        server.stop()

    wifi.disconnect()
    gc.collect()

    try:
        with open(FORCE_SETUP_FLAG, "w") as file:
            file.write("1")
    except OSError as error:
        print("Could not write setup flag:", repr(error))
        return False

    time.sleep_ms(250)
    machine.reset()
    return True


# -------------------------------------------------
# Connect using saved credentials
# -------------------------------------------------

def connect_saved_wifi():
    """
    Attempts to connect using credentials stored in
    wifi_config.json.

    Returns True when the connection succeeds.
    """

    credentials = load_credentials()

    if not credentials:
        print("No saved Wi-Fi credentials found.")
        return False

    ssid = credentials.get("ssid")
    password = credentials.get("password", "")

    if not ssid:
        print("Saved Wi-Fi configuration is invalid.")
        return False

    print("Saved Wi-Fi credentials found.")
    print("Trying saved network:", ssid)

    status_led.blink()
    gc.collect()

    try:
        result = wifi.connect(
            ssid,
            password,
            timeout_seconds=20
        )

    except Exception as error:
        print("Saved Wi-Fi connection error:", repr(error))
        return False

    if result.get("success"):
        print("Wi-Fi connected successfully.")
        print("Network:", ssid)
        print("IP address:", result.get("ip_address"))
        print("Local address:", wifi.get_local_url())

        status_led.solid()
        return True

    print("Saved Wi-Fi connection failed.")
    print(
        "Reason:",
        result.get("message", "Unknown connection error")
    )

    return False


# -------------------------------------------------
# Enter Wi-Fi setup mode
# -------------------------------------------------

def enter_setup_mode():
    """
    Starts the setup Access Point and launches the
    Wi-Fi configuration portal.

    Existing credentials are not deleted. They should
    only be replaced after a successful connection.
    """

    print()
    print("========================================")
    print("ENTERING WI-FI SETUP MODE")
    print("========================================")

    status_led.blink()

    stop_mqtt_session()

    server = admin_server

    if server is not None:
        server.stop()

    gc.collect()

    try:
        wifi.disconnect()
        gc.collect()

        setup_ap = load_setup_ap_config()
        ap_ssid = setup_ap["ssid"]
        ap_password = setup_ap["password"]

        access_point_info = wifi.start_access_point(
            ssid=ap_ssid,
            password=ap_password
        )

        print("Setup Access Point started.")
        print("Connect to:", ap_ssid)
        print("Setup password:", ap_password)
        print("Open: http://192.168.4.1")
        print("Access Point information:", access_point_info)

        # Import portal only when setup mode actually runs.
        gc.collect()
        from wifi_portal import run_setup_server

        run_setup_server(wifi, status_led)

    except Exception as error:
        print("Wi-Fi setup mode error:", repr(error))

    if wifi.is_connected():
        print("Wi-Fi configuration completed.")
        print("ESP32 is connected.")

        status_led.solid()
        get_admin_server().start()
        get_mqtt_session()
        return True

    print("ESP32 is not connected to Wi-Fi.")
    status_led.blink()

    return False


# -------------------------------------------------
# Application startup
# -------------------------------------------------

print()
print("========================================")
print("ESP32 NETWORKING SYSTEM STARTING")
print("========================================")

status_led.blink()
gc.collect()

if force_setup_requested():
    print("Setup requested by button — skipping auto-connect.")
    connected = enter_setup_mode()
else:
    connected = connect_saved_wifi()

    if not connected:
        connected = enter_setup_mode()

if connected:
    get_admin_server().start()
    get_mqtt_session()


# -------------------------------------------------
# Normal networking loop
# -------------------------------------------------

print()
print("Networking system running.")
print("Hold the setup button for 5 seconds")
print("to reopen Wi-Fi configuration.")
print(
    "Proximity FC-51 GPIO 4:",
    proximity.state_label(),
)

if wifi.is_connected():
    print("Admin page:", wifi.get_local_url())
    print(
        "Admin IP fallback: http://{}/".format(
            wifi.get_ip_address()
        )
    )

print()

while True:

    if wifi.is_connected():
        server = get_admin_server()

        if not server.is_running():
            server.start()

        server.poll()
        mqtt = get_mqtt_session()
        mqtt.poll()

        if mqtt.is_connected():
            if not _proximity_mqtt_synced:
                mqtt.publish_proximity(proximity.state_label())
                _proximity_mqtt_synced = True

            changed, label = proximity.poll_change()
            if changed:
                print("Proximity:", label)
                mqtt.publish_proximity(label)
        else:
            _proximity_mqtt_synced = False
            changed, label = proximity.poll_change()
            if changed:
                print("Proximity:", label)

    else:
        _proximity_mqtt_synced = False

        if admin_server is not None and admin_server.is_running():
            admin_server.stop()

        stop_mqtt_session()

        if not status_led.is_blinking:
            print("Wi-Fi connection lost.")
            status_led.blink()

        changed, label = proximity.poll_change()
        if changed:
            print("Proximity:", label)

    if wifi.is_connected():

        if status_led.is_blinking:
            print("Wi-Fi connection detected.")
            status_led.solid()

    if setup_button.wait_for_long_press():
        print("Setup-button long press confirmed.")

        while setup_button.is_pressed():
            time.sleep_ms(50)

        if not request_setup_reboot():
            connected = enter_setup_mode()

    time.sleep_ms(20)
