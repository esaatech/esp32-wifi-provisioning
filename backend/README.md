# Esaatech IoT Backend (Task 28)

Local FastAPI service that bridges HTTP ↔ EMQX MQTT for the ESP32.

## What it does

- Connects to EMQX over TLS (same broker as the ESP32)
- Subscribes to GPIO state + proximity telemetry
- `POST /api/gpio/{pin}/command` publishes `ON` / `OFF`
- `GET /api/state` returns the latest known device mirror
- Web UI with live switches + proximity status (`/`)

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

Credentials load from:

1. `backend/.env` (see `.env.example`), or
2. repo-root `mqtt_config.json` (local fallback)

Keep the ESP32 running `main.py` so commands and telemetry flow.

**Only run one backend instance.** A second uvicorn (e.g. Cursor on :8000 and
you on :8007) with the same MQTT client id causes connect/disconnect loops.
Client IDs are now uniquified per process; still prefer a single server.
