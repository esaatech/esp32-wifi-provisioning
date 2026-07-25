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

Future networking versions will also include:

- Firmware updates
- Diagnostics
- Configuration backup / restore
- Stronger transport security (HTTPS where hardware allows)

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
- Start the permanent LAN admin server when connected

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

Administration home page — like a router's main status page.

Core network section (always present, product-independent):

- Device status
- Connected network
- IP address
- Signal strength
- Restart / forget Wi-Fi (device network tools)

Other ESP32 products can reuse this networking hub and add their own
feature pages as separate links. This repository stays focused on
Wi-Fi provisioning, LAN admin, and device network tools.

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

✅ Embedded HTTP server (setup / AP mode)

✅ Wi-Fi network scanning

✅ Wi-Fi selection page

✅ Password submission

✅ Wi-Fi connection

✅ Credential storage

✅ Automatic reconnection

✅ Setup button recovery mode (GPIO 27)

✅ Status LED indicator (GPIO 2: blink / solid)

✅ Setup-mode administration page (while on the AP)

## In Progress / Next

✅ Permanent local admin page on building Wi-Fi (Task 5)

✅ Stable device address / hostname (Task 6)

✅ Administrator login (Task 7)

⬜ Configuration protection and data integrity (Task 15)

⬜ Secure communications (Task 16)

⬜ Firmware updates (Task 17)

⬜ Watchdog and failure recovery (Task 18)

⬜ Production provisioning (Task 19)

⬜ Production validation (Task 20)

---

# Planned Improvements

## Next Build: Permanent Local Admin Page (Task 5)

Goal: after the ESP32 joins the building network, keep a management website
available on the device IP so installers and admins can configure the device
from a phone or laptop on the same LAN — without USB, Thonny, or the cloud.

Think of it like a **router admin home page**:

1. **Network core (always there)** — connection status, SSID, IP, signal,
   restart, change/forget Wi-Fi, setup AP settings.
2. **Reusable shell** — other ESP32 products can link their own feature
   pages from this hub later; those product features live in separate
   projects, not in this networking repository.

Example network hub:

```
http://sbty-access.local/    ← network status home (router-like)
  → Restart / Forget Wi-Fi
  → Setup AP settings
  → Administrator account
```

### Runtime model

```
Boot
  → connect saved Wi-Fi (or run setup portal)
  → if connected: start admin server at http://<device-ip>/
  → main loop:
        poll setup button
        poll Wi-Fi / LED
        serve admin HTTP requests (non-blocking)
```

Setup mode (AP + provisioning) stays separate from normal mode
(station Wi-Fi + permanent admin).

### Phase A — network hub (Task 5)

1. Add a dedicated module (for example `admin_server.py`) for STA-mode HTTP only.
2. Reuse `templates/admin.html` and existing status helpers from `wifi_portal.py`.
3. From `main.py`, after a successful connection:
   - print the device IP
   - start the admin server with a socket timeout so the button / LED loop is not blocked
4. Initial routes (network only):
   - `GET /` or `GET /admin` — device and network status (the hub)
   - `POST /restart` — reboot the ESP32
   - `POST /forget-wifi` — delete credentials and return to setup
5. Keep the hub focused on networking tools (status, restart, forget Wi-Fi,
   setup AP settings, administrator account).
6. Stop the admin server when entering setup mode; start it again after a
   successful reconnect.

### Why this shape

| Choice | Reason |
|--------|--------|
| Network hub first (router-like) | Every ESP32 product needs status + Wi-Fi tools |
| Separate admin server (not stuck in setup portal) | Setup portal exits after provisioning; admin must live in normal mode |
| Non-blocking `accept()` | Setup button and status LED keep running |
| Config as web forms → JSON on flash | Works offline; no cloud required |

### Out of scope for Task 5 (later Asana tasks)

- ~~Stable hostname such as `sbty-access.local` → Task 6~~ (done)
- ~~Administrator login / sessions → Task 7~~ (done)
- Product-specific feature pages (users, readers, doors, etc.) → separate projects

### Acceptance checks

- [x] Phone on the same building Wi-Fi can open `http://<device-ip>/`
- [x] Home page shows network status (device, SSID, IP, signal)
- [x] Home page is structured as a hub that can later link to product pages
- [x] Main loop still responds to the setup button and status LED
- [x] Admin server stops during setup AP mode and resumes after reconnect

---

## Next Build: Stable Device Address (Task 6)

Goal: make the permanent admin page easy to find after restarts, without
hunting for a changing DHCP IP address.

### What the firmware does

1. Sets the LAN hostname to `sbty-access` **before** connecting to Wi-Fi.
2. Advertises that name over:
   - DHCP (so the router may show `sbty-access` in its client list)
   - mDNS (so many phones/laptops can open `http://sbty-access.local/`)
3. Keeps showing the current IP on the admin page as a fallback.
4. Prints both URLs in the serial log after connect.

### How to open the admin page

Preferred:

```
http://sbty-access.local/
```

Fallback (always works on the same LAN if you know the IP):

```
http://192.168.x.x/
```

Notes:

- `.local` names use mDNS. They work on most macOS, Linux, and many
  Android/iOS clients on the same Wi-Fi. Some Windows PCs need Bonjour
  or may need the IP fallback.
- Hostname is applied at connection time. After changing firmware that
  sets the hostname, reboot or reconnect Wi-Fi once.

### Recommended install step: DHCP reservation

For production installs, lock the ESP32 to one IP on the building router.
That is the most reliable way to keep the admin page findable even when
mDNS is blocked.

1. Connect the ESP32 to the building Wi-Fi and open the admin page.
2. Note:
   - Device IP address
   - Connected Wi-Fi name
3. On the router admin page, open **DHCP / LAN / Address Reservation**
   (wording varies by brand).
4. Create a reservation for this ESP32:
   - Use the device MAC address if the router shows it
   - Or reserve by the current hostname `sbty-access` / current IP
5. Save the reservation and reboot the ESP32 once.
6. Confirm the same IP returns after restart.
7. Label the device with:
   - `http://sbty-access.local/`
   - reserved IP, for example `http://192.168.1.50/`

### Acceptance checks

- [x] Device hostname is `sbty-access`
- [x] Admin page shows `http://sbty-access.local/` and the IP fallback
- [x] Serial log prints both the local URL and the IP URL
- [x] DHCP reservation steps are documented for installers

---

## Completed: Administrator Login (Task 7)

Goal: protect the permanent LAN admin page so only an administrator can
change device settings.

### Behavior

- Visiting `http://sbty-access.local/` (or the device IP) redirects to
  `/login` until signed in.
- Default first-boot password: `admin1234` (change it from the admin page).
- Password is stored as a salted SHA-256 hash in `admin_auth.json`.
- Successful login creates a session cookie (`sbty_session`).
- Sessions expire after 10 minutes of inactivity.
- Logout clears the session.
- After 5 failed logins, the device locks for 60 seconds.
- Setup Access Point mode (`192.168.4.1`) stays open for first-time install.
- After a successful Wi-Fi setup, **Open device administration** links to
  the live mDNS URL (for example `http://sbty-access.local/`), with the
  IP kept as fallback.

### Files added / used

- `admin_auth.py` — password hashing, sessions, lockout helpers
- `templates/login.html` — login page
- `templates/admin_station.html` — lighter permanent admin page (station mode)

### ESP32 memory notes

Classic ESP32 boards have limited RAM shared by MicroPython and Wi-Fi.
Task 7 therefore:

- Loads `admin_server` / `wifi_portal` **after** Wi-Fi connects (lazy import)
- Soft-reboots into setup mode when the setup button is held (clean Wi-Fi heap)
- Serves one admin client at a time with a blocking socket send path

Admin page loads are usable on classic ESP32; ESP32-S3 (more RAM) is a
smoother drop-in upgrade path for the same MicroPython design. A Raspberry
Pi would be faster for a rich hub UI but needs a port, not this firmware.

### Acceptance checks

- [x] Protected pages require login
- [x] Incorrect passwords are rejected
- [x] Successful login creates a session
- [x] Logout and inactivity timeout work
- [x] Repeated failed attempts trigger temporary lockout

---

## Phase 2 (setup UX)

- Automatic Captive Portal
- Auto-open configuration page
- Better error handling
- Password visibility toggle
- Loading progress updates
- Dark mode

---

## Phase 3 (admin features beyond Task 5)

- Change Wi-Fi from the permanent admin page
- Firmware updates
- Configuration backup / restore
- Diagnostics and health status

---

## Phase 4 (security)

- Administrator login → Task 7 (done)
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

## Administrator Login (Task 7)

- [x] Unauthenticated visit redirects to `/login`
- [x] Default password `admin1234` works on first boot
- [x] Wrong password is rejected
- [x] Successful login opens the permanent admin hub
- [x] Logout returns to `/login`
- [x] Setup AP portal remains usable without admin login
- [x] Success page admin link uses the mDNS URL

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

This networking system is a standalone subsystem. It does not depend on
product-specific hardware such as card readers, relays, or user databases.

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
- `admin_server.py` — *(planned)* permanent LAN admin website while connected to building Wi-Fi.

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
11. After a successful connection, a permanent admin page stays available on the LAN.
12. Preferred admin URL: `http://sbty-access.local/` (device IP remains the fallback).

## Optional LED Integration

The setup portal accepts an optional status LED:

```python
run_setup_server(wifi_manager, status_led=None)