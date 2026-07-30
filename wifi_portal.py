# wifi_portal.py
#
# ESP32 Wi-Fi provisioning portal for MicroPython.
#
# Expected project structure:
#
# /
# ├── main.py
# ├── wifi_manager.py
# ├── wifi_storage.py
# ├── wifi_portal.py
# └── templates/
#     ├── index.html
#     ├── connecting.html
#     ├── success.html
#     ├── failed.html
#     └── admin.html
#
# Required WiFiManager methods:
#
# wifi_manager.scan_networks()
# wifi_manager.connect(ssid, password, timeout_seconds=15)
# wifi_manager.is_connected()
# wifi_manager.get_ip_address()
#
# Required wifi_storage functions:
#
# save_credentials(ssid, password)
# delete_credentials()


import socket
import time
import machine
import network

from wifi_storage import (
    save_credentials,
    delete_credentials,
    load_credentials,
    load_setup_ap_config,
    load_product_config,
)

print("LOADED WIFI PORTAL VERSION 2")
# ---------------------------------------------------------
# Portal configuration
# ---------------------------------------------------------

DEVICE_NAME = "Esaatech Access Controller"
PORTAL_IP = "192.168.4.1"
SERVER_PORT = 80

TEMPLATE_FOLDER = "templates"

INDEX_TEMPLATE = TEMPLATE_FOLDER + "/index.html"
CONNECTING_TEMPLATE = TEMPLATE_FOLDER + "/connecting.html"
SUCCESS_TEMPLATE = TEMPLATE_FOLDER + "/success.html"
FAILED_TEMPLATE = TEMPLATE_FOLDER + "/failed.html"
ADMIN_TEMPLATE = TEMPLATE_FOLDER + "/admin.html"
ADMIN_STATION_TEMPLATE = TEMPLATE_FOLDER + "/admin_station.html"
DASHBOARD_TEMPLATE = TEMPLATE_FOLDER + "/dashboard.html"
LOGIN_TEMPLATE = TEMPLATE_FOLDER + "/login.html"
TEST_TEMPLATE = TEMPLATE_FOLDER + "/test.html"


# ---------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------

def html_escape(value):
    """
    Protects HTML pages from special characters contained
    inside SSIDs or status messages.
    """

    if value is None:
        return ""

    value = str(value)

    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def url_decode(value):
    """
    Decodes form values such as:

    My+WiFi       -> My WiFi
    Joel%27s+WiFi -> Joel's WiFi
    """

    if value is None:
        return ""

    value = value.replace("+", " ")

    output = bytearray()
    index = 0

    while index < len(value):
        character = value[index]

        if character == "%" and index + 2 < len(value):
            hexadecimal = value[index + 1:index + 3]

            try:
                output.append(int(hexadecimal, 16))
                index += 3
                continue
            except ValueError:
                pass

        output.extend(character.encode("utf-8"))
        index += 1

    try:
        return output.decode("utf-8")
    except UnicodeError:
        return output.decode("utf-8", "ignore")


def parse_form_data(body):
    """
    Converts a browser form body into a dictionary.

    Example:

    ssid=Home+WiFi&password=secret

    becomes:

    {
        "ssid": "Home WiFi",
        "password": "secret"
    }
    """

    values = {}

    if not body:
        return values

    for pair in body.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
        else:
            key = pair
            value = ""

        key = url_decode(key)
        value = url_decode(value)

        values[key] = value

    return values


# ---------------------------------------------------------
# Template utilities
# ---------------------------------------------------------

_TEMPLATE_CACHE = {}


def load_template(filename):
    """
    Loads an HTML template from the ESP32 filesystem.

    Templates are cached in RAM after the first read so
    repeated admin/login responses do not hit flash every time.
    """

    cached = _TEMPLATE_CACHE.get(filename)

    if cached is not None:
        return cached

    try:
        with open(filename, "r") as file:
            html = file.read()

        _TEMPLATE_CACHE[filename] = html
        return html

    except OSError as error:
        print("Template loading error:", filename, repr(error))

        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Template Error</title>
</head>
<body>
    <h1>Template Error</h1>
    <p>The ESP32 could not load:</p>
    <p><strong>{}</strong></p>
</body>
</html>
""".format(html_escape(filename))


def render_template(filename, replacements=None):
    """
    Replaces placeholders such as:

    {{SSID}}
    {{IP_ADDRESS}}
    {{MESSAGE}}
    """

    html = load_template(filename)

    if replacements is None:
        replacements = {}

    for key, value in replacements.items():
        placeholder = "{{" + key + "}}"

        if value is None:
            value = ""

        html = html.replace(placeholder, str(value))

    return html


def build_message_html(message):
    """
    Builds the message block used on index.html.
    """

    if not message:
        return ""

    return '<div class="message">{}</div>'.format(
        html_escape(message)
    )


def build_network_options(networks):
    """
    Creates the <option> elements placed inside the
    Wi-Fi network dropdown.
    """

    if not networks:
        return (
            '<option value="">'
            'No nearby Wi-Fi networks found'
            '</option>'
        )

    options = ""

    for network_info in networks:
        ssid = network_info.get("ssid", "")
        signal = network_info.get("signal", 0)

        if not ssid:
            continue

        safe_ssid = html_escape(ssid)

        options += (
            '<option value="{ssid}">'
            '{ssid} ({signal} dBm)'
            '</option>'
        ).format(
            ssid=safe_ssid,
            signal=signal
        )

    if not options:
        options = (
            '<option value="">'
            'No nearby Wi-Fi networks found'
            '</option>'
        )

    return options


def render_index_page(networks, message=""):
    return render_template(
        INDEX_TEMPLATE,
        {
            "DEVICE_NAME": html_escape(DEVICE_NAME),
            "NETWORK_OPTIONS": build_network_options(networks),
            "MESSAGE": build_message_html(message)
        }
    )


def render_connecting_page(ssid):
    return render_template(
        CONNECTING_TEMPLATE,
        {
            "SSID": html_escape(ssid)
        }
    )


def render_success_page(ssid, ip_address, local_url=""):
    # Cache-bust query so browsers do not reuse a failed/stale admin page.
    bust = time.ticks_ms()
    mdns_url = (local_url or "").rstrip("/")
    ip_url = "http://{}".format(ip_address) if ip_address else ""

    if mdns_url:
        mdns_url = "{}/login?v={}".format(mdns_url, bust)
    if ip_url:
        ip_url = "{}/login?v={}".format(ip_url, bust)

    return render_template(
        SUCCESS_TEMPLATE,
        {
            "SSID": html_escape(ssid),
            "IP_ADDRESS": html_escape(ip_address),
            "LOCAL_URL": html_escape(mdns_url),
            "IP_URL": html_escape(ip_url),
        }
    )


def render_failed_page(ssid, message):
    return render_template(
        FAILED_TEMPLATE,
        {
            "SSID": html_escape(ssid),
            "MESSAGE": html_escape(message)
        }
    )


def get_signal_strength(wifi_manager):
    """
    Returns the current router signal strength when supported.
    """

    try:
        if not wifi_manager.is_connected():
            return "Not connected"

        rssi = wifi_manager.station.status("rssi")

        return "{} dBm".format(rssi)

    except Exception:
        return "Unavailable"


def get_connected_ssid(wifi_manager):
    """
    Returns the current connected Wi-Fi network name.

    Prefer the saved credentials file. Calling
    station.config("essid") can block for a long time on some
    ESP32 MicroPython builds.
    """

    try:
        credentials = load_credentials()

        if credentials:
            ssid = credentials.get("ssid")

            if ssid:
                return ssid
    except Exception:
        pass

    try:
        config = wifi_manager.station.config("essid")

        if config:
            return config

    except Exception:
        pass

    return "Unknown"


def render_dashboard_page(wifi_manager):
    """
    Permanent LAN dashboard (product surface).

    Optional Test link appears when Admin enables test mode.
    """

    connected = wifi_manager.is_connected()
    product = load_product_config()

    if connected:
        connection_status = "Online"
        status_pill_class = ""
        ip_address = wifi_manager.get_ip_address() or "Unavailable"
    else:
        connection_status = "Offline"
        status_pill_class = "off"
        ip_address = "Unavailable"

    test_link_html = ""

    if product.get("test_mode"):
        test_link_html = (
            '<a class="test-link" href="/test">'
            "Open test outputs →"
            "</a>"
        )

    return render_template(
        DASHBOARD_TEMPLATE,
        {
            "DEVICE_NAME": html_escape(DEVICE_NAME),
            "CONNECTION_STATUS": html_escape(connection_status),
            "STATUS_PILL_CLASS": status_pill_class,
            "MDNS_NAME": html_escape(wifi_manager.get_mdns_name()),
            "IP_ADDRESS": html_escape(ip_address),
            "TEST_LINK_HTML": test_link_html,
        }
    )


def render_test_page(test_outputs, message=""):
    """
    GPIO test page for pins 16, 42, and 47.
    """

    controls = []

    for item in test_outputs.snapshot():
        pin = item["pin"]
        on = item["on"]
        state_label = "ON" if on else "OFF"
        state_class = "on" if on else ""

        controls.append(
            '<div class="pin-row">'
            '<div>'
            '<span class="pin-label">GPIO {pin}</span>'
            '<span class="pin-state {state_class}">State: {state}</span>'
            "</div>"
            '<div class="actions">'
            '<form method="POST" action="/test" style="display:inline">'
            '<input type="hidden" name="pin" value="{pin}">'
            '<input type="hidden" name="state" value="on">'
            '<button class="button on" type="submit">On</button>'
            "</form>"
            '<form method="POST" action="/test" style="display:inline">'
            '<input type="hidden" name="pin" value="{pin}">'
            '<input type="hidden" name="state" value="off">'
            '<button class="button off" type="submit">Off</button>'
            "</form>"
            "</div>"
            "</div>".format(
                pin=pin,
                state=state_label,
                state_class=state_class,
            )
        )

    return render_template(
        TEST_TEMPLATE,
        {
            "MESSAGE_HTML": build_message_html(message),
            "PIN_CONTROLS": "".join(controls),
        }
    )


def render_admin_page(wifi_manager, mode="setup", message=""):
    """
    Renders the administration home page.

    mode:
        "setup"   - shown while on the setup Access Point
        "station" - permanent LAN hub while on building Wi-Fi
    """

    connected = wifi_manager.is_connected()

    if connected:
        connection_status = "Connected"
        ssid = get_connected_ssid(wifi_manager)
        ip_address = wifi_manager.get_ip_address() or "Unavailable"
        # Skip live RSSI during page render; it can stall the
        # HTTP response on some boards.
        signal_strength = "Available"
        mdns_name = wifi_manager.get_mdns_name()
        local_url = wifi_manager.get_local_url()

    else:
        connection_status = "Not connected"
        ssid = "None"
        ip_address = "Unavailable"
        signal_strength = "Unavailable"
        mdns_name = wifi_manager.get_mdns_name()
        local_url = wifi_manager.get_local_url()

    if mode == "station":
        setup_ap = load_setup_ap_config()
        product = load_product_config()
        test_mode_on = ' checked' if product.get("test_mode") else ""
        test_mode_off = "" if product.get("test_mode") else " checked"

        print("Rendering station admin page...")

        page = render_template(
            ADMIN_STATION_TEMPLATE,
            {
                "DEVICE_NAME": html_escape(DEVICE_NAME),
                "CONNECTION_STATUS": html_escape(connection_status),
                "SSID": html_escape(ssid),
                "IP_ADDRESS": html_escape(ip_address),
                "SIGNAL_STRENGTH": html_escape(signal_strength),
                "MDNS_NAME": html_escape(mdns_name),
                "HOSTNAME": html_escape(
                    wifi_manager.get_hostname()
                ),
                "LOCAL_URL": html_escape(local_url),
                "AP_SSID": html_escape(setup_ap["ssid"]),
                "AP_PASSWORD": html_escape(setup_ap["password"]),
                "TEST_MODE_ON": test_mode_on,
                "TEST_MODE_OFF": test_mode_off,
                "MESSAGE_HTML": build_message_html(message)
            }
        )

        print("Station admin page ready:", len(page), "chars")
        return page

    setup_ap = load_setup_ap_config()
    setup_ap_ssid = setup_ap["ssid"]

    wifi_tools = (
        '<a class="button primary" href="/">Change Wi-Fi Network</a>'
        '<a class="button secondary" href="/rescan">Scan Nearby Networks</a>'
    )
    setup_ap_tools = (
        '<section class="card"><h2>Setup Access Point</h2>'
        '<div class="row"><span class="label">Setup AP name</span>'
        '<span class="value">{}</span></div>'
        '<p style="color:#64748b;line-height:1.5;margin:12px 0 0;">'
        'Change the setup AP name and password from the permanent '
        'admin page after joining building Wi-Fi.</p></section>'
    ).format(html_escape(setup_ap_ssid))

    return render_template(
        ADMIN_TEMPLATE,
        {
            "DEVICE_NAME": html_escape(DEVICE_NAME),
            "CONNECTION_STATUS": html_escape(connection_status),
            "SSID": html_escape(ssid),
            "IP_ADDRESS": html_escape(ip_address),
            "SIGNAL_STRENGTH": html_escape(signal_strength),
            "MDNS_NAME": html_escape(mdns_name),
            "LOCAL_URL": html_escape(local_url),
            "WIFI_TOOLS": wifi_tools,
            "SETUP_AP_TOOLS": setup_ap_tools,
            "ACCOUNT_TOOLS": "",
            "PRODUCT_LINKS": "",
            "MESSAGE_HTML": build_message_html(message)
        }
    )


def render_login_page(message=""):
    return render_template(
        LOGIN_TEMPLATE,
        {
            "DEVICE_NAME": html_escape(DEVICE_NAME),
            "MESSAGE_HTML": build_message_html(message)
        }
    )


# ---------------------------------------------------------
# HTTP response functions
# ---------------------------------------------------------

def send_all(client, data):
    """
    Sends all bytes to the browser.

    Important ESP32 note:
    Non-blocking sockets (timeout=0) were causing OSError(116)
    spin loops that sent 0 bytes for ~10 seconds on the second
    admin page load. Use a blocking socket with a short timeout
    and retry only while progress is possible.
    """

    if not data:
        return 0

    data_length = len(data)

    try:
        client.settimeout(3)
    except Exception:
        pass

    # Prefer write() when available — MicroPython streams loop
    # until all bytes are queued or an error occurs.
    write = getattr(client, "write", None)

    if write is not None:
        try:
            written = write(data)

            if written is None:
                return data_length

            if written >= data_length:
                return written
        except OSError as error:
            print("socket.write failed:", repr(error), "- falling back")

    total_sent = 0
    stall_count = 0

    while total_sent < data_length:
        chunk = data[total_sent:total_sent + 512]

        try:
            sent = client.send(chunk)
        except OSError as error:
            errno = getattr(error, "errno", None)

            if errno is None and error.args:
                errno = error.args[0]

            # Temporary Wi-Fi buffer full / timeout — wait and retry.
            if errno in (11, 35, 116) and stall_count < 30:
                stall_count += 1
                time.sleep_ms(50)
                continue

            print(
                "Send error after",
                total_sent,
                "of",
                data_length,
                "bytes:",
                repr(error)
            )
            raise

        if sent is None:
            sent = 0

        if sent <= 0:
            stall_count += 1

            if stall_count >= 30:
                print(
                    "Send stalled after",
                    total_sent,
                    "of",
                    data_length,
                    "bytes"
                )
                raise OSError(116)

            time.sleep_ms(50)
            continue

        total_sent += sent
        stall_count = 0

    return total_sent


def send_response(
    client,
    body,
    status="200 OK",
    content_type="text/html; charset=utf-8",
    extra_headers=None
):
    """
    Sends a complete HTTP response.
    """

    import gc

    if isinstance(body, str):
        body = body.encode("utf-8")

    extra = ""

    if extra_headers:
        for header in extra_headers:
            extra += header + "\r\n"

    headers = (
        "HTTP/1.1 {}\r\n"
        "Content-Type: {}\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
        "Pragma: no-cache\r\n"
        "Expires: 0\r\n"
        "{}"
        "\r\n"
    ).format(
        status,
        content_type,
        len(body),
        extra
    )

    header_bytes = headers.encode("utf-8")
    gc.collect()

    print("Sending", len(header_bytes) + len(body), "bytes...")
    header_count = send_all(client, header_bytes)
    body_count = send_all(client, body)

    print(
        "Sent HTTP response:",
        header_count + body_count,
        "bytes"
    )


def send_redirect(client, location="/", extra_headers=None):
    """
    Redirects the browser to another route.
    """

    body = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <meta
        http-equiv="refresh"
        content="0;url={location}"
    >
    <title>Redirecting</title>
</head>
<body>
    <p>Redirecting...</p>
    <a href="{location}">Continue</a>
</body>
</html>
""".format(
        location=html_escape(location)
    )

    body_bytes = body.encode("utf-8")

    extra = ""

    if extra_headers:
        for header in extra_headers:
            extra += header + "\r\n"

    headers = (
        "HTTP/1.1 302 Found\r\n"
        "Location: {}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
        "Pragma: no-cache\r\n"
        "Expires: 0\r\n"
        "{}"
        "\r\n"
    ).format(
        location,
        len(body_bytes),
        extra
    )

    send_all(client, headers.encode("utf-8"))
    send_all(client, body_bytes)


def send_not_found(client):
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Page Not Found</title>
</head>
<body>
    <h1>Page Not Found</h1>
    <p>The requested page does not exist.</p>
    <a href="/">Return to Wi-Fi setup</a>
</body>
</html>
"""

    send_response(
        client,
        html,
        status="404 Not Found"
    )


# ---------------------------------------------------------
# HTTP request functions
# ---------------------------------------------------------

def receive_request(client):
    """
    Reads both HTTP headers and the complete POST body.
    """

    request = b""

    # Keep this aligned with the admin server client timeout so
    # large pages are not cut off mid-transfer after reading.
    try:
        client.settimeout(15)
    except Exception:
        pass

    # Read until all HTTP headers have arrived.
    while b"\r\n\r\n" not in request:
        chunk = client.recv(512)

        if not chunk:
            break

        request += chunk

        if len(request) > 8192:
            raise ValueError("HTTP request is too large")

    header_end = request.find(b"\r\n\r\n")

    if header_end == -1:
        return request.decode("utf-8", "ignore")

    header_bytes = request[:header_end]
    body = request[header_end + 4:]

    headers = header_bytes.decode("utf-8", "ignore")

    content_length = 0

    for line in headers.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(
                    line.split(":", 1)[1].strip()
                )
            except ValueError:
                content_length = 0

    # Read the rest of the POST form if it did not arrive
    # in the first socket packet.
    while len(body) < content_length:
        chunk = client.recv(512)

        if not chunk:
            break

        body += chunk

        if len(body) > 8192:
            raise ValueError("HTTP request body is too large")

    return (
        headers
        + "\r\n\r\n"
        + body.decode("utf-8", "ignore")
    )


def parse_request_line(request):
    """
    Returns:

    method, path

    Example:

    GET / HTTP/1.1

    becomes:

    "GET", "/"
    """

    if not request:
        return None, None

    request_line = request.split("\r\n", 1)[0]
    parts = request_line.split(" ")

    if len(parts) < 2:
        return None, None

    method = parts[0].upper()
    path = parts[1]

    # Remove URL query parameters.
    if "?" in path:
        path = path.split("?", 1)[0]

    return method, path


def get_request_body(request):
    if "\r\n\r\n" not in request:
        return ""

    return request.split("\r\n\r\n", 1)[1]


# ---------------------------------------------------------
# Captive portal helpers
# ---------------------------------------------------------

def is_captive_portal_path(path):
    """
    Phones may request these URLs to determine whether the
    Wi-Fi network has internet access.

    Redirecting them to "/" helps the ESP32 setup page appear.
    """

    captive_paths = (
        "/generate_204",
        "/gen_204",
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/connecttest.txt",
        "/ncsi.txt",
        "/redirect",
        "/canonical.html",
        "/success.txt",
        "/favicon.ico"
    )

    return path in captive_paths


# ---------------------------------------------------------
# Wi-Fi connection operation
# ---------------------------------------------------------

def attempt_wifi_connection(
    wifi_manager,
    ssid,
    password,
    portal_state,
    status_led=None
):
    """
    Attempts the router connection after the connecting page
    has already been sent and the browser socket has closed.
    """

    print("Attempting connection to:", ssid)

    portal_state["status"] = "connecting"
    portal_state["ssid"] = ssid
    portal_state["message"] = ""
    portal_state["ip_address"] = ""

    try:
        result = wifi_manager.connect(
            ssid,
            password,
            timeout_seconds=15
        )

        if result.get("success"):
            ip_address = result.get("ip_address", "")

            save_credentials(ssid, password)

            portal_state["status"] = "success"
            portal_state["ip_address"] = ip_address
            portal_state["local_url"] = result.get(
                "local_url",
                wifi_manager.get_local_url()
            )
            portal_state["message"] = "Connection successful."

            # Connected again: stop blinking and go solid.
            if status_led is not None:
                status_led.solid()

            print("Wi-Fi connection successful")
            print("Router network:", ssid)
            print("ESP32 IP address:", ip_address)
            print("Local address:", portal_state["local_url"])

        else:
            message = result.get(
                "message",
                "The ESP32 could not connect to the network."
            )

            portal_state["status"] = "failed"
            portal_state["message"] = message

            if status_led is not None:
                status_led.blink()

            print("Wi-Fi connection failed:", message)

    except Exception as error:
        portal_state["status"] = "failed"
        portal_state["message"] = (
            "Connection error: " + str(error)
        )

        if status_led is not None:
            status_led.blink()

        print("Wi-Fi connection exception:", repr(error))


# ---------------------------------------------------------
# Main portal server
# ---------------------------------------------------------
def run_setup_server(wifi_manager, status_led=None):
    """
    Starts the ESP32 Wi-Fi setup portal.

    The server:
    - displays nearby Wi-Fi networks;
    - accepts the selected SSID and password;
    - attempts the Wi-Fi connection;
    - displays success or failure;
    - supports rescanning, restart, and forgetting Wi-Fi.
    """

    portal_state = {
        "status": "idle",
        "ssid": "",
        "message": "",
        "ip_address": "",
        "local_url": "",
        "success_at": None,
        "success_page_sent_at": None
    }

    # -------------------------------------------------
    # Initial Wi-Fi scan
    # -------------------------------------------------

    print("Scanning nearby Wi-Fi networks...")

    try:
        cached_networks = wifi_manager.scan_networks()

    except Exception as error:
        print("Initial Wi-Fi scan error:", repr(error))
        cached_networks = []

    print(
        "Found {} Wi-Fi networks".format(
            len(cached_networks)
        )
    )

    # -------------------------------------------------
    # Create HTTP server
    # -------------------------------------------------

    address = socket.getaddrinfo(
        "0.0.0.0",
        SERVER_PORT
    )[0][-1]

    server = socket.socket()

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind(address)
    server.listen(2)

    # Non-blocking accept so the portal can exit after
    # a successful connection and return to main.py.
    server.settimeout(1)

    print(
        "Setup portal running at http://{}".format(
            PORTAL_IP
        )
    )

    # -------------------------------------------------
    # Main server loop
    # -------------------------------------------------

    while True:
        client = None
        post_connection_action = None

        # After provisioning succeeds, return control so
        # main.py can monitor the setup button again.
        if portal_state["status"] == "success":
            now = time.ticks_ms()
            page_sent_at = portal_state["success_page_sent_at"]
            success_at = portal_state["success_at"]

            page_done = (
                page_sent_at is not None
                and time.ticks_diff(now, page_sent_at) >= 2000
            )
            timed_out = (
                success_at is not None
                and time.ticks_diff(now, success_at) >= 15000
            )

            if page_done or timed_out:
                print(
                    "Setup complete. Returning to normal operation."
                )

                # Ensure the status LED is solid once the
                # ESP32 is back on the building Wi-Fi.
                if status_led is not None:
                    if wifi_manager.is_connected():
                        status_led.solid()
                    else:
                        status_led.blink()

                try:
                    wifi_manager.stop_access_point()
                except Exception as error:
                    print(
                        "Could not stop access point:",
                        repr(error)
                    )

                try:
                    server.close()
                except Exception:
                    pass

                return

        try:
            try:
                client, remote_address = server.accept()
            except OSError:
                # Accept timed out; loop again to check
                # whether provisioning has finished.
                pass
            else:
                print()
                print("----------------------------------------")
                print("Browser connected from:", remote_address)

                request = receive_request(client)

                # MicroPython cannot use continue/break inside try/finally.
                if not request:
                    print("Empty HTTP request")

                else:
                    method, path = parse_request_line(request)

                    print("HTTP request:", method, path)

                    if method is None or path is None:
                        print("Invalid HTTP request")

                        send_response(
                            client,
                            "<h1>Invalid request</h1>",
                            status="400 Bad Request"
                        )

                    # -------------------------------------------------
                    # Captive portal and favicon requests
                    # -------------------------------------------------

                    elif is_captive_portal_path(path):
                        print("Captive portal request redirected:", path)

                        send_redirect(client, "/")

                    # -------------------------------------------------
                    # Main Wi-Fi setup page
                    # -------------------------------------------------

                    elif method == "GET" and path == "/":
                        print(
                            "Displaying {} cached Wi-Fi networks".format(
                                len(cached_networks)
                            )
                        )

                        page = render_index_page(cached_networks)

                        send_response(client, page)

                        print("Setup page delivered")

                    # -------------------------------------------------
                    # Installer submitted Wi-Fi credentials
                    # -------------------------------------------------

                    elif method == "POST" and path == "/connect":
                        body = get_request_body(request)

                        print("POST body length:", len(body))

                        form = parse_form_data(body)

                        ssid = form.get("ssid", "").strip()
                        password = form.get("password", "")

                        print("Installer selected SSID:", repr(ssid))
                        print("Password received:", bool(password))
                        print("Password length:", len(password))

                        if not ssid:
                            print("No SSID was selected")

                            page = render_index_page(
                                cached_networks,
                                "Please select a Wi-Fi network."
                            )

                            send_response(client, page)

                        else:
                            portal_state["status"] = "connecting"
                            portal_state["ssid"] = ssid
                            portal_state["message"] = ""
                            portal_state["ip_address"] = ""

                            page = render_connecting_page(ssid)

                            send_response(client, page)

                            print("Connecting page delivered")
                            print(
                                "Wi-Fi connection will begin after "
                                "the browser socket closes"
                            )

                            # Do not use continue here.
                            # The action must run after the finally block.
                            post_connection_action = {
                                "action": "connect",
                                "ssid": ssid,
                                "password": password
                            }

                    # -------------------------------------------------
                    # Browser checks connection status
                    # -------------------------------------------------

                    elif method == "GET" and path == "/status":
                        status = portal_state["status"]

                        print("Current portal status:", status)

                        if status == "success":
                            print("Sending successful connection page")

                            page = render_success_page(
                                portal_state["ssid"],
                                portal_state["ip_address"],
                                portal_state.get(
                                    "local_url",
                                    wifi_manager.get_local_url()
                                )
                            )

                            portal_state["success_page_sent_at"] = (
                                time.ticks_ms()
                            )

                        elif status == "failed":
                            print("Sending failed connection page")

                            page = render_failed_page(
                                portal_state["ssid"],
                                portal_state["message"]
                            )

                        else:
                            print("Connection still in progress")

                            page = render_connecting_page(
                                portal_state["ssid"]
                            )

                        send_response(client, page)

                    # -------------------------------------------------
                    # Rescan nearby Wi-Fi networks
                    # -------------------------------------------------

                    elif method == "GET" and path == "/rescan":
                        print("Wi-Fi rescan requested")

                        scanning_page = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <meta
        http-equiv="refresh"
        content="5;url=/"
    >

    <title>Scanning Wi-Fi</title>
</head>

<body>
    <h1>Scanning nearby Wi-Fi networks</h1>
    <p>Please wait a few seconds.</p>
</body>
</html>
"""

                        send_response(client, scanning_page)

                        print("Scanning page delivered")

                        # Do not use continue here.
                        post_connection_action = {
                            "action": "rescan"
                        }

                    # -------------------------------------------------
                    # Administration page
                    # -------------------------------------------------

                    elif method == "GET" and path == "/admin":
                        print("Administration page requested")

                        page = render_admin_page(wifi_manager)

                        send_response(client, page)

                    # -------------------------------------------------
                    # Restart device
                    # -------------------------------------------------

                    elif method == "POST" and path == "/restart":
                        print("Device restart requested")

                        restart_page = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Restarting</title>
</head>

<body>
    <h1>Restarting Device</h1>
    <p>The ESP32 is restarting.</p>
</body>
</html>
"""

                        send_response(client, restart_page)

                        print("Restart page delivered")

                        # Do not use continue here.
                        post_connection_action = {
                            "action": "restart"
                        }

                    # -------------------------------------------------
                    # Forget saved Wi-Fi credentials
                    # -------------------------------------------------

                    elif method == "POST" and path == "/forget-wifi":
                        print("Forget Wi-Fi requested")

                        try:
                            delete_credentials()

                            print("Saved Wi-Fi credentials deleted")

                            forget_page = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Wi-Fi Removed</title>
</head>

<body>
    <h1>Saved Wi-Fi Removed</h1>

    <p>
        The saved Wi-Fi credentials were deleted.
        The device will now restart in setup mode.
    </p>
</body>
</html>
"""

                            send_response(client, forget_page)

                            print("Forget Wi-Fi page delivered")

                            # Do not use continue here.
                            post_connection_action = {
                                "action": "restart"
                            }

                        except Exception as error:
                            print(
                                "Could not delete credentials:",
                                repr(error)
                            )

                            page = render_failed_page(
                                "",
                                "The saved Wi-Fi could not be removed."
                            )

                            send_response(client, page)

                    # -------------------------------------------------
                    # Unknown route
                    # -------------------------------------------------

                    else:
                        print("Unknown route:", method, path)

                        send_not_found(client)

        except Exception as error:
            print("Portal server error:", repr(error))

            if client is not None:
                try:
                    send_response(
                        client,
                        "<h1>ESP32 Server Error</h1>",
                        status="500 Internal Server Error"
                    )

                except Exception as response_error:
                    print(
                        "Could not send server error page:",
                        repr(response_error)
                    )

        finally:
            if client is not None:
                try:
                    client.close()
                    print("Browser socket closed")

                except Exception as error:
                    print(
                        "Browser socket close error:",
                        repr(error)
                    )

                client = None

        # -------------------------------------------------
        # Perform radio-sensitive actions only after the
        # browser connection has been closed.
        # -------------------------------------------------

        if post_connection_action is not None:
            action = post_connection_action.get("action")

            print("Running post-response action:", action)

            # ---------------------------------------------
            # Attempt Wi-Fi connection
            # ---------------------------------------------

            if action == "connect":
                selected_ssid = post_connection_action["ssid"]
                selected_password = post_connection_action["password"]

                print("----------------------------------------")
                print("Beginning Wi-Fi connection attempt")
                print("Target SSID:", repr(selected_ssid))
                print(
                    "Password provided:",
                    bool(selected_password)
                )
                print(
                    "Password length:",
                    len(selected_password)
                )

                attempt_wifi_connection(
                    wifi_manager,
                    selected_ssid,
                    selected_password,
                    portal_state,
                    status_led
                )

                print(
                    "Connection attempt finished with status:",
                    portal_state["status"]
                )

                if portal_state["status"] == "success":
                    print(
                        "Connected IP address:",
                        portal_state["ip_address"]
                    )
                    portal_state["success_at"] = time.ticks_ms()

                elif portal_state["status"] == "failed":
                    print(
                        "Failure message:",
                        portal_state["message"]
                    )

                print("----------------------------------------")

            # ---------------------------------------------
            # Rescan Wi-Fi networks
            # ---------------------------------------------

            elif action == "rescan":
                print("Rescanning nearby Wi-Fi networks...")

                try:
                    cached_networks = (
                        wifi_manager.scan_networks()
                    )

                    print(
                        "Rescan complete. Found {} networks".format(
                            len(cached_networks)
                        )
                    )

                except Exception as error:
                    print(
                        "Wi-Fi rescan error:",
                        repr(error)
                    )

            # ---------------------------------------------
            # Restart ESP32
            # ---------------------------------------------

            elif action == "restart":
                print("Restarting ESP32 in 2 seconds...")

                time.sleep(2)
                machine.reset()

            else:
                print(
                    "Unknown post-response action:",
                    action
                )
