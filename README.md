# ESP32 Wi-Fi Setup Portal

## Overview

This module provides a complete Wi-Fi provisioning system for the ESP32 without requiring the installer to modify any firmware or source code.

When the ESP32 is powered for the first time, or when no valid Wi-Fi credentials exist, it automatically creates its own Wi-Fi Access Point. The installer connects to this temporary network using a phone or laptop, opens a web page, selects the building Wi-Fi network, enters the password, and the ESP32 stores the credentials permanently.

Once configured, the ESP32 automatically reconnects to the saved Wi-Fi network every time it powers on.

---

# Objectives

The Wi-Fi Setup Portal was designed with the following goals:

- No code editing required
- No USB cable required after installation
- No Thonny required by the installer
- Works from any phone or computer
- Automatically remembers Wi-Fi credentials
- Simple installation process
- Reusable across all ESP32 projects

---

# Features

## Automatic Setup Mode

When the ESP32 cannot connect to a saved Wi-Fi network, it automatically enters Setup Mode.

It creates an Access Point.

Example:

```
SSID:
SBTY-Access-Control-Setup

Password:
setup1234
```

---

## Web Configuration Portal

After connecting to the Access Point, the installer opens

```
http://192.168.4.1
```

A configuration webpage is displayed where the installer can:

- View nearby Wi-Fi networks
- Select a network
- Enter the Wi-Fi password
- Connect the ESP32 to the router

---

## Wi-Fi Network Scanning

The portal scans nearby wireless networks and displays them in a dropdown list.

Each network displays:

- SSID
- Signal strength (RSSI)

Example:

```
Home WiFi (-42 dBm)

Office WiFi (-58 dBm)

Guest Network (-71 dBm)
```

---

## Automatic Credential Storage

Once the ESP32 successfully connects to the router, the credentials are saved to flash memory.

File:

```
wifi_config.json
```

Example:

```json
{
    "ssid": "Home WiFi",
    "password": "mypassword"
}
```

These credentials are automatically reused after every restart.

---

## Automatic Reconnection

Every time the ESP32 boots:

```
Read wifi_config.json

↓

Attempt Wi-Fi connection

↓

If successful

↓

Launch normal application
```

No user interaction is required.

---

## Administration Page

After successfully connecting, the ESP32 displays an Administration page.

The page currently displays:

- Device Name
- Connection Status
- Connected Wi-Fi
- Device IP Address
- Signal Strength

Future versions will also include:

- Door configuration
- User management
- Firmware updates
- Diagnostics
- Event logs

---

# Project Structure

```
main.py

wifi_manager.py

wifi_storage.py

wifi_portal.py

templates/

    index.html

    connecting.html

    success.html

    failed.html

    admin.html
```

---

# Module Responsibilities

## main.py

Responsible for startup.

Responsibilities:

- Load saved credentials
- Attempt automatic Wi-Fi connection
- Start Setup Portal if connection fails
- Launch the access-control application

---

## wifi_manager.py

Responsible for Wi-Fi hardware operations.

Responsibilities:

- Access Point mode
- Station mode
- Wi-Fi scanning
- Router connection
- Connection status
- IP address retrieval

---

## wifi_storage.py

Responsible for storing Wi-Fi credentials.

Responsibilities:

- Save credentials
- Load credentials
- Delete credentials

Current storage:

```
wifi_config.json
```

---

## wifi_portal.py

Responsible for the embedded web server.

Responsibilities:

- HTTP server
- Page routing
- Form handling
- Template rendering
- Wi-Fi provisioning
- Administration page

---

# HTML Templates

## index.html

Main Wi-Fi setup page.

Features:

- Device information
- Nearby Wi-Fi list
- Password entry
- Connect button

---

## connecting.html

Displayed while the ESP32 attempts the Wi-Fi connection.

Shows:

- Spinner
- Selected SSID
- Connection progress

---

## success.html

Displayed after a successful connection.

Shows:

- Connected SSID
- Device IP address

---

## failed.html

Displayed when the connection fails.

Shows:

- Failure reason
- Troubleshooting tips
- Retry button

---

## admin.html

Administration dashboard.

Displays:

- Device status
- Connected network
- IP address
- Signal strength

---

# Installation Workflow

```
Power ESP32

↓

ESP32 starts Setup Access Point

↓

Installer connects to

SBTY-Access-Control-Setup

↓

Open

http://192.168.4.1

↓

ESP32 scans nearby Wi-Fi

↓

Installer selects Wi-Fi

↓

Installer enters password

↓

ESP32 connects

↓

Credentials saved

↓

Success page displayed

↓

Normal operation
```

---

# Startup Workflow

```
ESP32 Power On

↓

Load wifi_config.json

↓

Credentials found?

 ├── No
 │
 │   Start Setup Portal
 │
 └── Yes
      │
      Attempt Wi-Fi connection
      │
      Connected?
      │
      ├── Yes
      │      │
      │      Launch application
      │
      └── No
             │
             Start Setup Portal
```

---

# HTTP Routes

Current routes:

```
GET /

Wi-Fi setup page
```

```
POST /connect

Attempt Wi-Fi connection
```

```
GET /status

Connection status
```

```
GET /admin

Administration page
```

```
GET /rescan

Rescan nearby Wi-Fi
```

```
POST /restart

Restart ESP32
```

```
POST /forget-wifi

Delete saved Wi-Fi credentials
```

---

# Current Status

## Completed

✅ ESP32 Access Point

✅ Embedded HTTP server

✅ Wi-Fi network scanning

✅ Wi-Fi selection page

✅ Password submission

✅ Wi-Fi connection

✅ Credential storage

✅ Automatic reconnection

✅ Device Administration page

---

# Planned Improvements

## Phase 2

- Automatic Captive Portal
- Auto-open configuration page
- Better error handling
- Password visibility toggle
- Loading progress updates
- Dark mode

---

## Phase 3

Administration Portal

- Change Wi-Fi
- Device restart
- Firmware updates
- Device information
- Access logs
- User management

---

## Phase 4

Security

- Administrator login
- HTTPS (future hardware permitting)
- Per-device setup password
- Secure credential storage
- Factory reset button
- Configuration timeout

---

# Testing Checklist

## Initial Setup

- [x] ESP32 starts Access Point
- [x] Connect to Setup Wi-Fi
- [x] Open http://192.168.4.1
- [x] Wi-Fi networks displayed
- [x] Select network
- [x] Enter password
- [x] ESP32 connects
- [x] Device IP displayed

---

## Persistent Storage

- [x] wifi_config.json created
- [x] SSID saved
- [x] Password saved

---

## Restart Test

- [x] ESP32 reconnects automatically
- [x] Setup mode skipped when credentials are valid

---

# Outcome

The ESP32 now supports professional Wi-Fi provisioning comparable to commercial IoT devices.

The installer no longer needs:

- Thonny
- USB programming
- Source code modifications
- Firmware rebuilding

Configuration can be completed entirely from a standard web browser, making this module reusable across future ESP32-based products such as access-control systems, smart sensors, lighting controllers, and other IoT devices.




ESP32 Wi-Fi Provisioning and Network Status System

Overview

This project provides a reusable Wi-Fi configuration system for an ESP32 running MicroPython.

Its purpose is to allow an installer or end user to connect the ESP32 to a Wi-Fi network without:

* editing source code;
* opening Thonny or another IDE;
* connecting the ESP32 to a computer through USB;
* manually changing the Wi-Fi credentials inside the firmware.

The ESP32 can create its own temporary Wi-Fi network, host a configuration website, scan nearby Wi-Fi networks, accept new credentials, test them, and save them for future restarts.

The project also includes:

* automatic reconnection using saved credentials;
* a physical setup button for reopening configuration mode;
* a status LED that shows whether the ESP32 is connected;
* an administration page showing current network information.

This networking system is currently being developed as a standalone subsystem. It does not depend on the access-control card reader, relay, LCD, or user database.

⸻

Current Features

The networking subsystem currently supports:

* Connecting to previously saved Wi-Fi credentials.
* Starting setup mode when no valid credentials are available.
* Starting setup mode through a physical button.
* Scanning nearby Wi-Fi networks.
* Displaying the networks in a browser dropdown.
* Accepting an SSID and password from the installer.
* Testing the new connection before saving the credentials.
* Preserving the previous credentials if the new connection fails.
* Saving successful credentials in wifi_config.json.
* Automatically reconnecting after an ESP32 restart.
* Providing visual Wi-Fi status through GPIO 2.
* Providing an administration page.
* Restarting the ESP32 from the portal.
* Deleting saved Wi-Fi credentials from the portal.
* Supporting common captive-portal requests from phones and computers.

⸻

# ESP32 Wi-Fi Provisioning System

## Overview

This project provides a standalone Wi-Fi configuration system for an ESP32 running MicroPython.

The ESP32 can connect to saved Wi-Fi credentials automatically. If no valid credentials are available, it creates a temporary setup network and hosts a configuration portal at:

`http://192.168.4.1`

The installer can select a nearby Wi-Fi network, enter its password, and connect the ESP32 without editing code or using an IDE.

## Main Features

- Automatically connects using saved Wi-Fi credentials.
- Starts a setup Access Point when no connection is available.
- Scans and displays nearby Wi-Fi networks.
- Saves credentials only after a successful connection.
- Preserves existing credentials when a new connection fails.
- Allows Wi-Fi reconfiguration using a button connected to GPIO 27.
- Uses the onboard GPIO 2 LED as a network-status indicator.
- Provides an administration page with connection information.

## Status LED

The onboard LED connected to GPIO 2 indicates the network state:

- **Blinking:** disconnected, connecting, or setup mode active.
- **Solid:** successfully connected to Wi-Fi.

When the setup button is held for five seconds, the LED changes from solid to blinking. This confirms that the ESP32 has entered setup mode.

## Setup Button

A push button is connected between GPIO 27 and GND using the ESP32's internal pull-up resistor.

Holding the button for five seconds starts the Wi-Fi setup portal. Existing credentials are not deleted until replacement credentials have connected successfully.

## Main Files

- `main.py` — controls startup, Wi-Fi connection, setup mode, button monitoring, and LED status.
- `wifi_manager.py` — manages Wi-Fi scanning, router connections, and the setup Access Point.
- `wifi_storage.py` — saves, loads, and deletes credentials in `wifi_config.json`.
- `wifi_portal.py` — runs the setup website and processes Wi-Fi configuration requests.
- `setup_button.py` — detects the five-second setup-button hold.
- `status_led.py` — controls blinking, solid, and off LED states.
- `templates/` — contains the HTML pages used by the setup portal.

## Provisioning Flow

1. The ESP32 starts and loads saved credentials.
2. It attempts to connect to the saved network.
3. While disconnected or connecting, the status LED blinks.
4. When connected, the LED becomes solid.
5. If connection fails, the ESP32 starts its setup Access Point.
6. The installer connects to `SBTY-Access-Control-Setup`.
7. The installer opens `192.168.4.1`.
8. The ESP32 tests the submitted credentials.
9. Successful credentials are saved and the LED becomes solid.
10. Failed credentials are not saved and the LED continues blinking.

## Optional LED Integration

The setup portal accepts an optional status LED:

```python
run_setup_server(wifi_manager, status_led=None)