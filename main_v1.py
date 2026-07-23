# main.py

from wifi_manager import WiFiManager
from wifi_storage import load_credentials
from wifi_portal import run_setup_server


wifi = WiFiManager()
credentials = load_credentials()

connected = False


# -------------------------------------------------
# Try saved Wi-Fi credentials first
# -------------------------------------------------

if credentials:
    print("Saved Wi-Fi credentials found.")
    print("Trying saved Wi-Fi network...")

    try:
        result = wifi.connect(
            credentials["ssid"],
            credentials["password"],
            timeout_seconds=10
        )

        connected = result.get("success", False)

        if connected:
            print("Wi-Fi connected successfully.")
            print("Network:", credentials["ssid"])
            print("IP address:", result.get("ip_address"))

        else:
            print("Saved Wi-Fi connection failed.")
            print(
                "Reason:",
                result.get("message", "Unknown connection error")
            )

    except Exception as error:
        print("Saved Wi-Fi connection error:", error)
        connected = False

else:
    print("No saved Wi-Fi credentials found.")


# -------------------------------------------------
# Start setup Access Point when not connected
# -------------------------------------------------

if not connected:
    print("Starting Wi-Fi setup mode...")

    try:
        access_point_info = wifi.start_access_point()

        print("Setup network started.")
        print("Connect to: SBTY-Access-Control-Setup")
        print("Open: http://192.168.4.1")
        print("Access Point information:", access_point_info)

        # The portal normally keeps running while the installer
        # configures the Wi-Fi connection.
        run_setup_server(wifi)

    except Exception as error:
        print("Wi-Fi setup mode error:", error)


# -------------------------------------------------
# Start the access-control application
# -------------------------------------------------

if wifi.is_connected():
    connected = True

    print("Starting access-control system...")

    # Uncomment these lines when you are ready to start
    # your existing access-control application.

    # from access_control import run
    # run()

else:
    print("Access-control system not started.")
    print("The ESP32 is not connected to Wi-Fi.")