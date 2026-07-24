# main.py
#
# Standalone ESP32 networking application.
#
# Responsibilities:
# - Connect using saved Wi-Fi credentials.
# - Start setup mode when no valid credentials exist.
# - Host a permanent LAN admin page while connected.
# - Monitor a dedicated setup button.
# - Display Wi-Fi status using the onboard LED.
#
# LED behaviour:
# - Blinking: Wi-Fi disconnected or setup mode
# - Solid: Wi-Fi connected

import time

from wifi_manager import WiFiManager
from wifi_storage import load_credentials, load_setup_ap_config
from wifi_portal import run_setup_server
from setup_button import SetupButton
from status_led import StatusLED
from admin_server import AdminServer


# -------------------------------------------------
# Create application objects
# -------------------------------------------------

wifi = WiFiManager()
setup_button = SetupButton()
status_led = StatusLED()
admin_server = AdminServer(wifi)


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

    # Blink while attempting the connection.
    status_led.blink()

    try:
        result = wifi.connect(
            ssid,
            password,
            timeout_seconds=10
        )

    except Exception as error:
        print("Saved Wi-Fi connection error:", repr(error))
        return False

    if result.get("success"):
        print("Wi-Fi connected successfully.")
        print("Network:", ssid)
        print("IP address:", result.get("ip_address"))

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

    # The LED keeps blinking while the setup portal
    # is running.
    status_led.blink()

    # Free port 80 before the setup portal starts.
    admin_server.stop()

    try:
        # Leave the router so phones can join the setup AP.
        wifi.disconnect()

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

        run_setup_server(wifi, status_led)

    except Exception as error:
        print("Wi-Fi setup mode error:", repr(error))

    # This section runs if the portal returns control
    # to main.py.
    if wifi.is_connected():
        print("Wi-Fi configuration completed.")
        print("ESP32 is connected.")

        status_led.solid()
        admin_server.start()
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

# Start blinking immediately during startup.
status_led.blink()

connected = connect_saved_wifi()

if not connected:
    connected = enter_setup_mode()

if connected:
    admin_server.start()


# -------------------------------------------------
# Normal networking loop
# -------------------------------------------------

print()
print("Networking system running.")
print("Hold the setup button for 5 seconds")
print("to reopen Wi-Fi configuration.")

if wifi.is_connected():
    print(
        "Admin page: http://{}/".format(
            wifi.get_ip_address()
        )
    )

print()

while True:

    # ---------------------------------------------
    # Serve the permanent LAN admin page
    # ---------------------------------------------

    if wifi.is_connected():
        if not admin_server.is_running():
            admin_server.start()

        admin_server.poll()

    elif admin_server.is_running():
        admin_server.stop()

    # ---------------------------------------------
    # Monitor current Wi-Fi status
    # ---------------------------------------------

    if wifi.is_connected():

        if status_led.is_blinking:
            print("Wi-Fi connection detected.")
            status_led.solid()

    else:

        if not status_led.is_blinking:
            print("Wi-Fi connection lost.")
            status_led.blink()

    # ---------------------------------------------
    # Monitor the setup button
    # ---------------------------------------------

    if setup_button.wait_for_long_press():
        print("Setup-button long press confirmed.")

        # Wait for the button to be released so the
        # same press cannot trigger setup twice.
        while setup_button.is_pressed():
            time.sleep_ms(50)

        connected = enter_setup_mode()

    time.sleep_ms(20)
