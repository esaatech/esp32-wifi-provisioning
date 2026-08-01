(() => {
  const initial = window.__ESAATECH_INITIAL__ || {};
  const cards = [...document.querySelectorAll(".switch-card")];
  const mqttPill = document.getElementById("mqttPill");
  const mqttLabel = document.getElementById("mqttLabel");
  const proxPanel = document.getElementById("proximityPanel");
  const proxStatus = document.getElementById("proxStatus");
  const proxDetail = document.getElementById("proxDetail");
  const updatedAt = document.getElementById("updatedAt");

  const pending = new Map();

  function applyState(state) {
    if (!state) return;

    const connected = !!state.mqtt_connected;
    mqttPill.dataset.connected = connected ? "true" : "false";
    mqttLabel.textContent = connected ? "MQTT connected" : "MQTT disconnected";

    const gpio = state.gpio || {};
    for (const card of cards) {
      const pin = card.dataset.pin;
      const input = card.querySelector('[data-role="input"]');
      const label = card.querySelector('[data-role="state"]');
      const value = gpio[pin];

      if (pending.has(pin)) {
        // Wait for device confirmation of our own command.
        continue;
      }

      if (value === "ON" || value === "OFF") {
        input.checked = value === "ON";
        label.textContent = value;
      } else {
        input.checked = false;
        label.textContent = "—";
      }
    }

    const prox = state.proximity;
    const human = state.proximity_label || "Waiting for sensor…";
    proxPanel.dataset.status = prox || "unknown";
    proxStatus.textContent = human;
    if (prox && state.proximity_seq != null) {
      proxDetail.textContent = `${prox} seq=${state.proximity_seq}`;
    } else if (prox) {
      proxDetail.textContent = prox;
    } else {
      proxDetail.textContent = "FC-51 on GPIO 4 · event telemetry";
    }

    if (state.updated_at) {
      const d = new Date(state.updated_at * 1000);
      updatedAt.textContent = `Updated ${d.toLocaleTimeString()}`;
    }
  }

  async function sendCommand(pin, on) {
    const card = cards.find((c) => c.dataset.pin === String(pin));
    if (!card) return;
    const label = card.querySelector('[data-role="state"]');
    card.dataset.busy = "true";
    pending.set(String(pin), on ? "ON" : "OFF");
    label.textContent = on ? "ON…" : "OFF…";

    try {
      const res = await fetch(`/api/gpio/${pin}/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ on }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
    } catch (error) {
      pending.delete(String(pin));
      alert(`Command failed: ${error.message}`);
      applyState(await fetch("/api/state").then((r) => r.json()));
    } finally {
      card.dataset.busy = "false";
    }
  }

  for (const card of cards) {
    const input = card.querySelector('[data-role="input"]');
    input.addEventListener("change", () => {
      sendCommand(card.dataset.pin, input.checked);
    });
  }

  function onEvent(event) {
    if (event.type === "gpio" && event.pin != null) {
      const pin = String(event.pin);
      const expected = pending.get(pin);
      if (expected && event.value === expected) {
        pending.delete(pin);
      } else if (expected && event.value !== expected) {
        // Device reported something else; clear pending and trust device.
        pending.delete(pin);
      }
    }
    if (event.state) {
      applyState(event.state);
    } else if (event.type === "mqtt") {
      applyState({
        ...(window.__ESAATECH_INITIAL__ || {}),
        mqtt_connected: event.connected,
      });
    }
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.addEventListener("open", () => {
      // Keepalive so some proxies don't idle-close.
      setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 25000);
    });
    ws.addEventListener("message", (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch (_) {
        /* ignore */
      }
    });
    ws.addEventListener("close", () => {
      mqttLabel.textContent = "Reconnecting…";
      mqttPill.dataset.connected = "false";
      setTimeout(connectWs, 1500);
    });
  }

  applyState(initial);
  connectWs();
})();
