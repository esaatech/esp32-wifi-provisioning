"""
FastAPI IoT backend — HTTP ↔ MQTT bridge for the Esaatech ESP32 (Task 28).

Run locally:
    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000/
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .config import GPIO_PINS, get_settings
from .mqtt_bridge import MqttBridge
from .state_store import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("esaatech.api")

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_loop: asyncio.AbstractEventLoop | None = None
_ws_clients: Set[WebSocket] = set()
_bridge: MqttBridge | None = None


class GpioCommand(BaseModel):
    on: bool = Field(..., description="True for ON, False for OFF")


def _broadcast_threadsafe(event: dict) -> None:
    loop = _loop
    if loop is None or not loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(_broadcast(event), loop)


async def _broadcast(event: dict) -> None:
    dead: List[WebSocket] = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop, _bridge
    _loop = asyncio.get_running_loop()
    settings = get_settings()
    _bridge = MqttBridge(settings, on_event=_broadcast_threadsafe)
    _bridge.start()
    logger.info("FastAPI IoT backend ready for device %s", settings.device_id)
    try:
        yield
    finally:
        if _bridge is not None:
            _bridge.stop()
        _bridge = None


app = FastAPI(
    title="Esaatech IoT Backend",
    description="Local HTTP ↔ MQTT bridge for ESP32 GPIO + proximity telemetry",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "device_id": settings.device_id,
            "pins": list(GPIO_PINS),
            "initial": store.snapshot(),
        },
    )


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "mqtt_connected": store.mqtt_connected,
        "device_id": get_settings().device_id,
    }


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Latest known GPIO + proximity state from MQTT retains/live updates."""
    return store.snapshot()


@app.post("/api/gpio/{pin}/command")
async def gpio_command(pin: int, body: GpioCommand) -> Dict[str, Any]:
    if pin not in GPIO_PINS:
        raise HTTPException(status_code=404, detail=f"Unknown GPIO pin {pin}")
    if _bridge is None:
        raise HTTPException(status_code=503, detail="MQTT bridge not started")
    try:
        _bridge.publish_gpio_command(pin, body.on)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "ok": True,
        "pin": pin,
        "command": "ON" if body.on else "OFF",
        "note": "Waiting for device state topic confirmation",
        "state": store.snapshot(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    await websocket.send_json({"type": "snapshot", "state": store.snapshot()})
    try:
        while True:
            # Keep the socket open; client may send pings as text.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)
