# admin_server.py
#
# Permanent LAN admin website for MicroPython ESP32.
#
# Runs only while the device is connected to building Wi-Fi.
# Uses a short socket timeout so main.py can keep polling the
# setup button and status LED.

import socket
import time
import machine

from wifi_storage import delete_credentials, save_setup_ap_config
from wifi_portal import (
    render_admin_page,
    receive_request,
    parse_request_line,
    get_request_body,
    parse_form_data,
    send_response,
    send_not_found,
)


ADMIN_PORT = 80
ACCEPT_TIMEOUT_SECONDS = 0.05
CLIENT_TIMEOUT_SECONDS = 3

# Common when the browser cancels a tab, prefetches, or drops
# the socket early. Not fatal for the admin server.
_IGNORED_SOCKET_ERRNOS = (
    104,  # ECONNRESET
    116,  # ETIMEDOUT
    107,  # ENOTCONN
    103,  # ECONNABORTED
    128,  # ENOTCONN on some ports
)


def _is_benign_socket_error(error):
    errno = getattr(error, "errno", None)

    if errno is None and error.args:
        errno = error.args[0]

    return errno in _IGNORED_SOCKET_ERRNOS


class AdminServer:
    """
    Non-blocking HTTP hub for network status and device actions.

    Product-specific pages (access control, sensors, etc.) will be
    linked from the home page in later tasks.
    """

    def __init__(self, wifi_manager, port=ADMIN_PORT):
        self.wifi_manager = wifi_manager
        self.port = port
        self.server = None
        self._pending_action = None
        self._wifi_lost_count = 0

    # -------------------------------------------------

    def is_running(self):
        return self.server is not None

    # -------------------------------------------------

    def start(self):
        """
        Starts listening on the station IP.
        """

        if self.server is not None:
            return

        if not self.wifi_manager.is_connected():
            print("Admin server not started: Wi-Fi is disconnected.")
            return

        address = socket.getaddrinfo("0.0.0.0", self.port)[0][-1]

        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(address)
        server.listen(2)
        server.settimeout(ACCEPT_TIMEOUT_SECONDS)

        self.server = server

        ip_address = self.wifi_manager.get_ip_address()

        print("Permanent admin page available at:")
        print("  {}".format(self.wifi_manager.get_local_url()))
        print("  http://{}/".format(ip_address))

    # -------------------------------------------------

    def stop(self):
        """
        Closes the admin listener (for example before setup mode).
        """

        if self.server is None:
            return

        try:
            self.server.close()
        except Exception as error:
            print("Admin server close error:", repr(error))

        self.server = None
        print("Permanent admin server stopped.")

    # -------------------------------------------------

    def poll(self):
        """
        Handles at most one pending HTTP request.

        Safe to call repeatedly from the main loop.
        """

        if self.server is None:
            return

        # Ignore brief Wi-Fi glitches so one failed poll does not
        # tear down the admin listener.
        if not self.wifi_manager.is_connected():
            self._wifi_lost_count += 1

            if self._wifi_lost_count >= 5:
                self.stop()

            return

        self._wifi_lost_count = 0

        client = None

        try:
            try:
                client, remote_address = self.server.accept()
            except OSError:
                return

            try:
                client.settimeout(CLIENT_TIMEOUT_SECONDS)
            except Exception:
                pass

            print("Admin request from:", remote_address)

            request = receive_request(client)

            if not request:
                # Browser opened then closed (common with probes).
                return

            method, path = parse_request_line(request)

            print("Admin HTTP request:", method, path)

            if method is None or path is None:
                send_response(
                    client,
                    "<h1>Invalid request</h1>",
                    status="400 Bad Request"
                )
                return

            # Browsers often request this automatically.
            if method == "GET" and path == "/favicon.ico":
                send_response(
                    client,
                    b"",
                    status="204 No Content",
                    content_type="image/x-icon"
                )
                return

            if method == "GET" and path in ("/", "/admin"):
                page = render_admin_page(
                    self.wifi_manager,
                    mode="station"
                )
                send_response(client, page)

            elif method == "POST" and path == "/setup-ap":
                body = get_request_body(request)
                form = parse_form_data(body)

                ap_ssid = form.get("ssid", "").strip()
                ap_password = form.get("password", "")

                try:
                    save_setup_ap_config(ap_ssid, ap_password)
                    print("Setup AP settings saved:", ap_ssid)
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message="Setup Access Point settings saved."
                    )
                    send_response(client, page)

                except ValueError as error:
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message=str(error)
                    )
                    send_response(client, page)

                except Exception as error:
                    print(
                        "Could not save setup AP settings:",
                        repr(error)
                    )
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message="Could not save setup AP settings."
                    )
                    send_response(
                        client,
                        page,
                        status="500 Internal Server Error"
                    )

            elif method == "GET" and path == "/access":
                send_response(
                    client,
                    """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Access / Users</title>
</head>
<body>
    <h1>Access / Users</h1>
    <p>
        User and UID management will be added in a later task.
    </p>
    <p><a href="/">Back to admin</a></p>
</body>
</html>
"""
                )

            elif method == "POST" and path == "/restart":
                send_response(
                    client,
                    _simple_page(
                        "Restarting",
                        "The ESP32 is restarting."
                    )
                )
                self._pending_action = "restart"

            elif method == "POST" and path == "/forget-wifi":
                try:
                    delete_credentials()
                    send_response(
                        client,
                        _simple_page(
                            "Wi-Fi Removed",
                            "Saved Wi-Fi credentials were deleted. "
                            "The device will restart in setup mode."
                        )
                    )
                    self._pending_action = "restart"
                except Exception as error:
                    print(
                        "Could not delete credentials:",
                        repr(error)
                    )
                    send_response(
                        client,
                        _simple_page(
                            "Error",
                            "The saved Wi-Fi could not be removed."
                        ),
                        status="500 Internal Server Error"
                    )

            else:
                print("Unknown admin route:", method, path)
                send_not_found(client)

        except OSError as error:
            if _is_benign_socket_error(error):
                print("Admin client disconnected:", repr(error))
            else:
                print("Admin server error:", repr(error))

        except Exception as error:
            print("Admin server error:", repr(error))

            if client is not None:
                try:
                    send_response(
                        client,
                        "<h1>ESP32 Server Error</h1>",
                        status="500 Internal Server Error"
                    )
                except Exception:
                    pass

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

        action = self._pending_action
        self._pending_action = None

        if action == "restart":
            print("Restarting ESP32 in 2 seconds...")
            time.sleep(2)
            machine.reset()


def _simple_page(title, message):
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    <p>{message}</p>
</body>
</html>
""".format(
        title=title,
        message=message
    )
