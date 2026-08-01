# admin_server.py
#
# Permanent LAN admin website for MicroPython ESP32.
#
# Runs only while the device is connected to building Wi-Fi.
# Protected by administrator login (Task 7).

import socket
import time
import machine

from wifi_storage import (
    delete_credentials,
    save_setup_ap_config,
    save_hostname,
    save_product_config,
    load_product_config,
)
from wifi_portal import (
    render_admin_page,
    render_dashboard_page,
    render_test_page,
    render_login_page,
    receive_request,
    parse_request_line,
    get_request_body,
    parse_form_data,
    send_response,
    send_redirect,
    send_not_found,
)
from admin_auth import (
    AdminAuth,
    SESSION_COOKIE,
    get_cookie,
    session_cookie_header,
    clear_session_cookie_header,
)


ADMIN_PORT = 80
ACCEPT_TIMEOUT_SECONDS = 0.05
CLIENT_TIMEOUT_SECONDS = 10
# One client at a time — parallel sockets were leaving half-dead
# connections that timed out during the admin page send.
MAX_CLIENTS_PER_POLL = 1

_IGNORED_SOCKET_ERRNOS = (
    104,  # ECONNRESET
    116,  # ETIMEDOUT
    107,  # ENOTCONN
    103,  # ECONNABORTED
    128,  # ENOTCONN on some ports
)

PUBLIC_PATHS = (
    "/login",
    "/favicon.ico",
)


def _is_benign_socket_error(error):
    errno = getattr(error, "errno", None)

    if errno is None and error.args:
        errno = error.args[0]

    return errno in _IGNORED_SOCKET_ERRNOS


class AdminServer:
    """
    Non-blocking HTTP hub for network status and device actions.
    """

    def __init__(self, wifi_manager, port=ADMIN_PORT):
        self.wifi_manager = wifi_manager
        self.port = port
        self.server = None
        self._pending_action = None
        self._wifi_lost_count = 0
        self.auth = AdminAuth()
        self.test_outputs = None

    # -------------------------------------------------

    def _get_test_outputs(self):
        from test_outputs import get_shared_test_outputs

        self.test_outputs = get_shared_test_outputs()
        return self.test_outputs

    # -------------------------------------------------

    def is_running(self):
        return self.server is not None

    # -------------------------------------------------

    def start(self):
        if self.server is not None:
            return

        if not self.wifi_manager.is_connected():
            print("Admin server not started: Wi-Fi is disconnected.")
            return

        address = socket.getaddrinfo("0.0.0.0", self.port)[0][-1]

        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(address)
        server.listen(5)
        server.settimeout(ACCEPT_TIMEOUT_SECONDS)

        self.server = server

        ip_address = self.wifi_manager.get_ip_address()

        print("Dashboard available at:")
        print("  {}".format(self.wifi_manager.get_local_url()))
        print("  http://{}/".format(ip_address))
        print("Admin settings at /admin (login required).")

    # -------------------------------------------------

    def stop(self):
        if self.server is None:
            return

        try:
            self.server.close()
        except Exception as error:
            print("Admin server close error:", repr(error))

        self.server = None
        print("Permanent admin server stopped.")

    # -------------------------------------------------

    def _is_authenticated(self, request):
        token = get_cookie(request, SESSION_COOKIE)
        return self.auth.validate_session(token)

    # -------------------------------------------------

    def poll(self):
        if self.server is None:
            return

        if not self.wifi_manager.is_connected():
            self._wifi_lost_count += 1

            if self._wifi_lost_count >= 5:
                self.stop()

            return

        self._wifi_lost_count = 0

        for _ in range(MAX_CLIENTS_PER_POLL):
            handled = self._handle_one_client()

            if not handled:
                break

            action = self._pending_action
            self._pending_action = None

            if action == "restart":
                print("Restarting ESP32 in 2 seconds...")
                time.sleep(2)
                machine.reset()

    # -------------------------------------------------

    def _handle_one_client(self):
        client = None

        try:
            try:
                client, remote_address = self.server.accept()
            except OSError:
                return False

            try:
                client.settimeout(CLIENT_TIMEOUT_SECONDS)
            except Exception:
                pass

            print("Admin request from:", remote_address)

            request = receive_request(client)

            if not request:
                return True

            method, path = parse_request_line(request)

            print("Admin HTTP request:", method, path)

            if method is None or path is None:
                send_response(
                    client,
                    "<h1>Invalid request</h1>",
                    status="400 Bad Request"
                )
                return True

            if method == "GET" and path == "/favicon.ico":
                send_response(
                    client,
                    b"",
                    status="204 No Content",
                    content_type="image/x-icon"
                )
                return True

            # -----------------------------------------
            # Login / logout (public + session control)
            # -----------------------------------------

            if method == "GET" and path == "/login":
                if self._is_authenticated(request):
                    send_redirect(client, "/")
                else:
                    send_response(client, render_login_page())
                return True

            if method == "POST" and path == "/login":
                body = get_request_body(request)
                form = parse_form_data(body)
                password = form.get("password", "")

                ok, message, token = self.auth.login(password)

                if ok:
                    print("Admin login successful.")
                    send_redirect(
                        client,
                        "/",
                        extra_headers=[session_cookie_header(token)]
                    )
                else:
                    print("Admin login failed:", message)
                    send_response(
                        client,
                        render_login_page(message)
                    )
                return True

            if method == "POST" and path == "/logout":
                token = get_cookie(request, SESSION_COOKIE)
                self.auth.destroy_session(token)
                send_redirect(
                    client,
                    "/login",
                    extra_headers=[clear_session_cookie_header()]
                )
                return True

            # -----------------------------------------
            # Everything else requires a valid session
            # -----------------------------------------

            if path not in PUBLIC_PATHS:
                if not self._is_authenticated(request):
                    send_redirect(client, "/login")
                    return True

            if method == "GET" and path == "/":
                import gc
                gc.collect()
                print("Building dashboard page...")
                page = render_dashboard_page(self.wifi_manager)
                send_response(client, page)
                print("Dashboard page sent.")

            elif method == "GET" and path == "/admin":
                import gc
                gc.collect()
                print("Building admin page...")
                page = render_admin_page(
                    self.wifi_manager,
                    mode="station"
                )
                print("Sending admin page...")
                send_response(client, page)
                print("Admin page sent.")

            elif method == "GET" and path == "/test":
                if not load_product_config().get("test_mode"):
                    send_redirect(client, "/")
                    return True

                page = render_test_page(self._get_test_outputs())
                send_response(client, page)

            elif method == "POST" and path == "/test":
                if not load_product_config().get("test_mode"):
                    send_redirect(client, "/")
                    return True

                body = get_request_body(request)
                form = parse_form_data(body)
                pin = form.get("pin", "").strip()
                state = form.get("state", "").strip().lower()

                try:
                    on = state in ("on", "1", "true")
                    self._get_test_outputs().set_output(pin, on)
                    message = "GPIO {} set {}.".format(
                        pin,
                        "ON" if on else "OFF"
                    )
                    page = render_test_page(
                        self._get_test_outputs(),
                        message=message
                    )
                    send_response(client, page)

                except ValueError as error:
                    page = render_test_page(
                        self._get_test_outputs(),
                        message=str(error)
                    )
                    send_response(client, page)

                except Exception as error:
                    print("Test output error:", repr(error))
                    page = render_test_page(
                        self._get_test_outputs(),
                        message="Could not change that pin."
                    )
                    send_response(
                        client,
                        page,
                        status="500 Internal Server Error"
                    )

            elif method == "POST" and path == "/product":
                body = get_request_body(request)
                form = parse_form_data(body)
                test_mode = form.get("test_mode", "off").strip().lower()
                enabled = test_mode in ("on", "1", "true")

                try:
                    save_product_config(enabled)
                    print("Test mode saved:", enabled)
                    message = (
                        "Test outputs enabled. Open the dashboard "
                        "for the Test link."
                        if enabled
                        else "Test outputs disabled."
                    )
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message=message
                    )
                    send_response(client, page)

                except Exception as error:
                    print("Could not save product config:", repr(error))
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message="Could not save test setting."
                    )
                    send_response(
                        client,
                        page,
                        status="500 Internal Server Error"
                    )

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

            elif method == "POST" and path == "/hostname":
                body = get_request_body(request)
                form = parse_form_data(body)
                hostname = form.get("hostname", "").strip()

                try:
                    saved = save_hostname(hostname)
                    self.wifi_manager.apply_hostname(saved)
                    print("Hostname saved:", saved)

                    send_response(
                        client,
                        _simple_page(
                            "Local Address Updated",
                            "Saved as http://{}.local/. "
                            "The device is restarting so the "
                            "new name takes effect.".format(saved)
                        )
                    )
                    self._pending_action = "restart"

                except ValueError as error:
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message=str(error)
                    )
                    send_response(client, page)

                except Exception as error:
                    print("Could not save hostname:", repr(error))
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message="Could not save local address."
                    )
                    send_response(
                        client,
                        page,
                        status="500 Internal Server Error"
                    )

            elif method == "POST" and path == "/change-password":
                body = get_request_body(request)
                form = parse_form_data(body)

                current_password = form.get("current_password", "")
                new_password = form.get("new_password", "")
                confirm_password = form.get("confirm_password", "")

                try:
                    if not self.auth.verify_password(current_password):
                        raise ValueError(
                            "Current password is incorrect."
                        )

                    if new_password != confirm_password:
                        raise ValueError(
                            "New password confirmation does not match."
                        )

                    self.auth.set_password(new_password)
                    print("Admin password changed.")

                    send_redirect(
                        client,
                        "/login",
                        extra_headers=[clear_session_cookie_header()]
                    )

                except ValueError as error:
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message=str(error)
                    )
                    send_response(client, page)

                except Exception as error:
                    print(
                        "Could not change admin password:",
                        repr(error)
                    )
                    page = render_admin_page(
                        self.wifi_manager,
                        mode="station",
                        message="Could not change admin password."
                    )
                    send_response(
                        client,
                        page,
                        status="500 Internal Server Error"
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

        return True


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
