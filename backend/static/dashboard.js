(() => {
  const initial = window.__ESAATECH_INITIAL__ || {};
  const cards = [...document.querySelectorAll(".switch-card")];
  const mqttPill = document.getElementById("mqttPill");
  const mqttLabel = document.getElementById("mqttLabel");
  const proxPanel = document.getElementById("proximityPanel");
  const proxStatus = document.getElementById("proxStatus");
  const proxDetail = document.getElementById("proxDetail");
  const updatedAt = document.getElementById("updatedAt");
  const soundToggle = document.getElementById("soundToggle");

  const pending = new Map();
  const SOUND_KEY = "esaatech.proximitySound";

  let soundOn = localStorage.getItem(SOUND_KEY) === "1";
  let proximity = initial.proximity || null;
  let audioCtx = null;
  let humOsc = null;
  let humGain = null;
  let humLfo = null;
  let humming = false;

  function syncSoundButton() {
    soundToggle.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundToggle.textContent = soundOn ? "Sound on" : "Sound off";
  }

  async function unlockAudio() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return false;
      audioCtx = new Ctx();
    }
    if (audioCtx.state === "suspended") {
      try {
        await audioCtx.resume();
      } catch (_) {
        return false;
      }
    }
    return audioCtx.state === "running";
  }

  function stopHum() {
    if (!humming) return;
    humming = false;
    try {
      if (humGain && audioCtx) {
        const now = audioCtx.currentTime;
        humGain.gain.cancelScheduledValues(now);
        humGain.gain.setValueAtTime(humGain.gain.value, now);
        humGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
      }
    } catch (_) {
      /* ignore */
    }
    const osc = humOsc;
    const lfo = humLfo;
    humOsc = null;
    humGain = null;
    humLfo = null;
    window.setTimeout(() => {
      try {
        if (osc) osc.stop();
      } catch (_) {
        /* ignore */
      }
      try {
        if (lfo) lfo.stop();
      } catch (_) {
        /* ignore */
      }
    }, 140);
  }

  async function startHum() {
    if (!soundOn || proximity !== "DETECTED" || humming) return;
    const ok = await unlockAudio();
    if (!ok || !audioCtx) return;

    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    const lfo = audioCtx.createOscillator();
    const lfoGain = audioCtx.createGain();

    // Soft low hum with a tiny wobble so it feels alive, not a pure beep.
    osc.type = "sine";
    osc.frequency.value = 118;
    lfo.type = "sine";
    lfo.frequency.value = 2.2;
    lfoGain.gain.value = 6;
    lfo.connect(lfoGain);
    lfoGain.connect(osc.frequency);

    gain.gain.value = 0.0001;
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    gain.gain.exponentialRampToValueAtTime(0.045, now + 0.18);

    osc.start();
    lfo.start();

    humOsc = osc;
    humGain = gain;
    humLfo = lfo;
    humming = true;
  }

  function syncProximitySound() {
    if (soundOn && proximity === "DETECTED") {
      startHum();
    } else {
      stopHum();
    }
  }

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

    proximity = state.proximity || null;
    const human = state.proximity_label || "Waiting for sensor…";
    proxPanel.dataset.status = proximity || "unknown";
    proxStatus.textContent = human;
    if (proximity && state.proximity_seq != null) {
      proxDetail.textContent = `${proximity} seq=${state.proximity_seq}`;
    } else if (proximity) {
      proxDetail.textContent = proximity;
    } else {
      proxDetail.textContent = "FC-51 on GPIO 4 · event telemetry";
    }

    syncProximitySound();

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

  soundToggle.addEventListener("click", async () => {
    soundOn = !soundOn;
    localStorage.setItem(SOUND_KEY, soundOn ? "1" : "0");
    syncSoundButton();
    if (soundOn) {
      await unlockAudio();
      syncProximitySound();
    } else {
      stopHum();
    }
  });

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

  syncSoundButton();
  applyState(initial);
  connectWs();
})();
