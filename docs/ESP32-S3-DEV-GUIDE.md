# ESP32-S3 N16R8 — Developer Guide (Esaatech)

A practical guide for the **ESP32-S3** board used in this project, compared with the **classic ESP32** you used before, including USB ports, pins, memory, and what it’s good (and not good) for.

> Note on naming: your previous board was a **classic ESP32** (DevKit / WROOM-32 style with a USB‑UART chip), not an ESP32‑S2. The **S2** is a different single‑core chip with USB but no Bluetooth. This guide compares **classic ESP32 → ESP32‑S3**.

---

## 1. What you have now

| Item | Value |
|------|--------|
| Module family | **ESP32-S3** (dual‑core Xtensa LX7 @ up to 240 MHz) |
| Ordering code meaning | **N16R8** = **16 MB flash** + **8 MB Octal (OPI) PSRAM** |
| Firmware we flashed | MicroPython `ESP32_GENERIC_S3-SPIRAM_OCT` v1.28.0 |
| Typical free heap (with PSRAM) | ~**8 MB** (`gc.mem_free()`), vs ~**100–220 KB** on classic ESP32 |
| Wi‑Fi | 2.4 GHz |
| Bluetooth | **BLE 5** (no Classic Bluetooth audio like old ESP32 A2DP) |
| Project defaults | Hostname `esaatech-access.local`, setup AP `Esaatech-Setup` |

**N16R8 decoded**

- **N16** → 16 MB flash (store firmware + files)
- **R8** → 8 MB PSRAM (extra RAM for buffers, web pages, camera frames, small ML)

---

## 2. The two USB ports (the confusing part)

Your S3 DevKit has **two USB‑C connectors**. They are **not** the same.

### Port names (what macOS shows)

| Physical port (typical) | Role | Example device name on Mac | Chip behind it |
|-------------------------|------|----------------------------|----------------|
| **Left / “USB”** | **Native USB** (USB‑OTG / CDC) | `/dev/cu.usbmodem1101` or `usbmodem1234561` — often labeled **Espressif Device** | ESP32‑S3 itself (GPIO **19/20**) |
| **Right / “UART” / “COM”** | **USB‑UART bridge** | `/dev/cu.usbmodem5C4C2078021` (CH343‑style) or sometimes `usbserial-…` | Separate serial chip → ESP32 UART0 (GPIO **43 TX / 44 RX**) |

Exact left/right depends on how the board is oriented; use the silkscreen (**USB** vs **UART**) if present. Match by **device name** in Thonny / `mpremote connect list`.

### What each port is good for

| Task | Prefer | Why |
|------|--------|-----|
| Flash MicroPython `.bin` with esptool | **UART (right)** | Talks to the ROM bootloader reliably |
| Day‑to‑day Thonny / serial logs | **UART (right)** | Soft reset usually keeps the link |
| Upload `.py` with `mpremote` | Either | Both work once MicroPython is installed |
| Soft reset / Restart / setup‑button reboot while Thonny is open | **UART (right)** | Native USB **drops** → Thonny `Device not configured` |

### Why Thonny “broke” on Restart (but the board was fine)

- **Classic ESP32:** one USB‑UART chip stays plugged in during `machine.reset()` → Thonny often stays connected.
- **S3 native USB:** the ESP32 itself is the USB device → reset tears the USB link down → Thonny reports `ConnectionError: Device not configured`.
- That is **expected on native USB**, not a firmware bug. Use the **UART** port for debugging resets, or disconnect Thonny and test over Wi‑Fi.

### Quick workflow for this project

1. **Flash firmware** → UART port (+ BOOT/RST if needed).
2. **Develop / watch reboots** → UART + Thonny.
3. **Field / admin testing** → no Thonny required; use Wi‑Fi admin page.

---

## 3. Benefits over the classic ESP32

| Area | Classic ESP32 (old board) | ESP32‑S3 N16R8 (this board) |
|------|---------------------------|-----------------------------|
| CPU | Dual‑core LX6 @ 240 MHz | Dual‑core **LX7** @ 240 MHz (newer, more efficient) |
| RAM for apps | Mostly ~**520 KB** SRAM; heap often ~**100 KB** free after Wi‑Fi | **8 MB PSRAM** + internal SRAM → huge headroom for admin pages / buffers |
| Flash | Often **4 MB** | **16 MB** |
| USB | External CH340/CP2102 only | **Native USB** + often a second UART USB |
| Bluetooth | Classic + BLE | **BLE 5** only (no Classic BT) |
| AI helpers | None | **Vector / NN instructions** (helps small ML, not magic) |
| GPIO | Fewer usable pins after flash | More pins, but **Octal PSRAM steals 26–37** |
| Wi‑Fi admin UX | Worked, but tight on memory / timeouts | Much more comfortable with large HTML + auth |

**For *this* networking project:** the big win is **memory + stability** (admin page, login, hostname editor, fewer Wi‑Fi OOM issues when switching AP ↔ station).

---

## 4. Audio, video, and AI — can this S3 do it?

### Short answer

| Workload | ESP32‑S3 N16R8 | Verdict |
|----------|----------------|---------|
| **Light audio** (I2S mic, short buffers, wake‑word‑class TFLite) | Yes, with care | Good enough to start |
| **Video / camera** (OV2640 JPEG, small streams) | Yes, PSRAM helps | Good for prototypes, not HD video product |
| **On‑device AI** (tiny models, face detect demos) | Partial | Better than classic ESP32; still tiny‑ML only |
| **Heavy AV / big AI** (video encode, LLMs, desktop‑class vision) | No | Need a bigger platform |

The S3 is a **strong IoT / edge‑UI / camera‑demo** chip, not a media PC or GPU.

### If you need a clearer upgrade path

| Goal | Better next step |
|------|------------------|
| Serious **voice UI** (mics + speaker + DSP demos) | **ESP32‑S3‑BOX / BOX‑3** or Espressif **Korvo** audio kits |
| Camera + display product demos | S3 with camera connector boards, or **ESP32‑P4** + wireless companion |
| Heavier **HMI / video / AI compute** | **ESP32‑P4** (faster CPU, better multimedia; often **no built‑in Wi‑Fi** — pair with C6/S3) |
| Real Linux AV / AI | **Raspberry Pi 4/5**, Jetson‑class, etc. |

**Practical note for Esaatech:** keep **S3 N16R8** for networking / access control / sensors / light camera. Plan a **P4 or Pi** line if the product roadmap needs serious video or AI.

---

## 5. Pins: classic ESP32 vs this S3

### Pins this project already uses

| Function | Classic ESP32 | ESP32‑S3 (this repo) | Why it changed |
|----------|---------------|----------------------|----------------|
| Setup button | **GPIO 27** → button → GND | **GPIO 38** → button → GND | On S3 + Octal PSRAM, **GPIO 26–37** are reserved for flash/PSRAM. **27 is unusable.** |
| Status LED | **GPIO 2** (often onboard blue) | **GPIO 2** (valid; many S3 kits have **no** simple blue LED — use external LED) | Same number, different board wiring |
| Soft timers | `Timer(-1)` often OK | Prefer **`Timer(0)`** (or 0–3) | Newer S3 MicroPython rejects `Timer(-1)` |

### Right‑side header (near UART USB) — useful map

Typical DevKitC‑1 style (confirm silkscreen on *your* board):

| Label on board | Notes for N16R8 |
|----------------|-----------------|
| **TX (43), RX (44)** | UART0 → Thonny on UART USB — leave alone while debugging |
| **1, 2** | Free GPIOs / ADC; **2** = our status LED |
| **42, 41, 40, 39** | **Best free digital I/O** on this side |
| **38** | **Setup button** (also RGB LED on some v1.1 boards) |
| **37, 36, 35** | **Do not use** — Octal flash/PSRAM |
| **0, 45** | Boot / strapping — avoid for normal I/O |
| **48, 47, 21** | Usable extras (48 may be RGB on older kits) |
| **20, 19** | Native USB D+/D− — don’t steal if using left USB |
| **3V3, GND** | Power for sensors |

### Recommended “future breadboard” pins

**I2C (no fixed SDA/SCL labels on S3 — you choose):**

- Easy default: **SDA = GPIO 8**, **SCL = GPIO 9**
- Or right‑side: **SDA = 41**, **SCL = 42**

**Safe extras:** 4, 5, 6, 7, 15, 16, 17, 18, 21, 39–42, 47–48  

**Avoid:** 19–20 (USB), 26–37 (memory), 0/45/46 (strapping), 43–44 (UART0)

### Classic ESP32 habits that break on S3

1. **“GPIO 27 is free”** → false on N16R8.  
2. **One USB port for everything** → two ports; pick by task.  
3. **`Timer(-1)`** → use `Timer(0)`.  
4. **Expect Thonny to survive soft reset on native USB** → use UART USB instead.  
5. Generic MicroPython S3 build **without** `SPIRAM_OCT` → PSRAM stays off (~200 KB heap). Always use the **Octal‑SPIRAM** firmware for N16R8.

---

## 6. Firmware and tools cheat sheet

```bash
# List ports
mpremote connect list

# Upload (example: UART port)
mpremote connect /dev/cu.usbmodem5C4C2078021 cp wifi_portal.py :
mpremote connect /dev/cu.usbmodem5C4C2078021 reset
```

**Flash Octal PSRAM firmware (once):**

- Download: MicroPython **ESP32_GENERIC_S3** → **Firmware (Support for Octal‑SPIRAM)**
- Prefer **UART** port; if connect fails, hold **BOOT**, tap **RST**, release **BOOT**, then flash.

**Admin URLs (defaults):**

- `http://esaatech-access.local/` (editable in admin → pencil on Local address)
- IP fallback, e.g. `http://192.168.x.x/`

**Default admin password:** `admin1234` (change after first login)

---

## 7. Mental model (one paragraph)

Your **classic ESP32** was a single‑USB, memory‑tight Wi‑Fi MCU that was fine for a setup portal. The **ESP32‑S3 N16R8** is the same *kind* of device (Wi‑Fi IoT), but with **much more RAM/flash**, **BLE 5**, **native USB**, and **light AI/camera headroom**. Treat the **UART USB** as your “old ESP32 serial port,” and the **native USB** as a bonus that disconnects on reset. For heavy audio/video/AI products, plan a **BOX / P4 / Pi** upgrade later — don’t expect the S3 DevKit to replace them.

---

## 8. Related project files

| File | S3‑relevant note |
|------|------------------|
| `setup_button.py` | Auto‑selects GPIO **38** on S3, **27** on classic |
| `status_led.py` | GPIO **2**, `Timer(0)` |
| `wifi_manager.py` / `wifi_storage.py` | Hostname default `esaatech-access` |
| `templates/admin_station.html` | Edit‑hostname dialog |

---

*Document written for Esaatech networking work on the ESP32‑S3 N16R8. Orient USB left/right using board silkscreen + macOS device names if your PCB printing differs.*
