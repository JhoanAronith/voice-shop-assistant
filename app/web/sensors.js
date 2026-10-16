// Phone sensors: shake to record, GPS for the nearest branch, ambient light for the theme.
// Browsers only deliver sensor data while this page is open in the foreground.
(() => {
  const button = document.getElementById("sensors");
  const micButton = document.getElementById("mic");
  const status = document.getElementById("sensor-status");

  const SHAKE_JOLT = 14; // m/s² of acceleration without gravity that counts as one jolt
  const SHAKE_JOLTS = 3; // jolts needed inside SHAKE_WINDOW_MS
  const SHAKE_WINDOW_MS = 1000;
  const SHAKE_COOLDOWN_MS = 2500;
  const SEND_EVERY_MS = 5000;
  const DARK_BELOW_LUX = 15;
  const LIGHT_ABOVE_LUX = 40;

  const deviceId = (() => {
    try {
      let id = localStorage.getItem("device");
      if (!id) localStorage.setItem("device", (id = crypto.randomUUID().slice(0, 8)));
      return id;
    } catch {
      return "web";
    }
  })();

  let active = false;
  let position = null;
  let lux = null;
  let peakAccel = 0;
  let peakGyro = 0;
  let jolts = [];
  let lastShake = 0;
  let watchId = null;
  let lightSensor = null;
  let timer = null;
  let readings = 0;

  const say = (text) => window.toast?.(text);

  function render() {
    button.classList.toggle("on", active);
    button.setAttribute("aria-pressed", String(active));
    if (!active) {
      status.textContent = "";
      return;
    }
    const parts = [position ? "GPS" : "sin GPS"];
    parts.push(lux === null ? "sin luz" : `${Math.round(lux)} lx`);
    status.textContent = parts.join(" · ");
  }

  function send(extra = {}) {
    const body = {
      device_id: deviceId,
      accel: peakAccel || null,
      gyro: peakGyro || null,
      lux,
      ...(position && { lat: position.lat, lon: position.lon, accuracy: position.accuracy }),
      ...extra,
    };
    peakAccel = 0;
    peakGyro = 0;
    readings += 1;
    fetch("/api/iot/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => {});
  }

  function onMotion(event) {
    const now = Date.now();
    const free = event.acceleration;
    const g = event.accelerationIncludingGravity;
    const accel = free && free.x !== null
      ? Math.hypot(free.x, free.y, free.z)
      : g ? Math.abs(Math.hypot(g.x, g.y, g.z) - 9.81) : 0;
    peakAccel = Math.max(peakAccel, accel);

    const rate = event.rotationRate;
    if (rate) peakGyro = Math.max(peakGyro, Math.hypot(rate.alpha || 0, rate.beta || 0, rate.gamma || 0));

    if (accel < SHAKE_JOLT) return;
    if (jolts.length && now - jolts[jolts.length - 1] < 120) return; // same jolt, next sample
    jolts = jolts.filter((t) => now - t < SHAKE_WINDOW_MS);
    jolts.push(now);

    if (jolts.length >= SHAKE_JOLTS && now - lastShake > SHAKE_COOLDOWN_MS) {
      lastShake = now;
      jolts = [];
      navigator.vibrate?.(60);
      send({ event: "shake" });
      micButton.click(); // starts recording, or stops it if already recording
    }
  }

  function setTheme() {
    if (lux === null) return;
    const root = document.documentElement;
    if (lux < DARK_BELOW_LUX) root.dataset.theme = "dark";
    else if (lux > LIGHT_ABOVE_LUX) root.dataset.theme = "light";
  }

  function startLight() {
    if (!("AmbientLightSensor" in window)) return false;
    try {
      lightSensor = new AmbientLightSensor({ frequency: 1 });
      lightSensor.onreading = () => {
        lux = lightSensor.illuminance;
        setTheme();
        render();
      };
      lightSensor.onerror = () => {};
      lightSensor.start();
      return true;
    } catch {
      return false;
    }
  }

  function startGps() {
    if (!navigator.geolocation) return;
    watchId = navigator.geolocation.watchPosition(
      ({ coords }) => {
        position = { lat: coords.latitude, lon: coords.longitude, accuracy: coords.accuracy };
        render();
      },
      () => say("Sin acceso a la ubicación"),
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 }
    );
  }

  async function start() {
    if (!window.isSecureContext) {
      say("Los sensores requieren HTTPS: abre la app por el túnel");
      return;
    }
    if (typeof DeviceMotionEvent !== "undefined" && DeviceMotionEvent.requestPermission) {
      // iOS asks for motion access explicitly, and only from a tap.
      if ((await DeviceMotionEvent.requestPermission()) !== "granted") {
        say("Sin acceso al movimiento");
        return;
      }
    }
    window.addEventListener("devicemotion", onMotion);
    startGps();
    const light = startLight();
    active = true;
    timer = setInterval(() => send(), SEND_EVERY_MS);
    send();
    render();
    say(light ? "Sensores activados" : "Sensores activados (sin sensor de luz: activa el flag de Chrome)");
  }

  function stop() {
    window.removeEventListener("devicemotion", onMotion);
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    lightSensor?.stop();
    clearInterval(timer);
    lightSensor = null;
    watchId = null;
    active = false;
    position = null;
    lux = null;
    document.documentElement.dataset.theme = localStorage.getItem("theme") || "auto";
    render();
  }

  button.onclick = () => (active ? stop() : start());

  window.iot = {
    position: () => (position ? { lat: position.lat, lon: position.lon } : {}),
  };
})();
