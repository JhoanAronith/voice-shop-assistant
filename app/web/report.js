const el = (id) => document.getElementById(id);
const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => ENTITIES[c]);
const number = (value) => new Intl.NumberFormat("es-PE").format(value ?? 0);

let days = 14;

/* ---------- theme ---------- */

document.documentElement.dataset.theme = localStorage.getItem("theme") || "auto";

el("theme-toggle").onclick = () => {
  const current = document.documentElement.dataset.theme;
  const dark =
    current === "dark" ||
    (current === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  const next = dark ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
};

/* ---------- KPIs ---------- */

function renderKpis(totals) {
  const tiles = [
    { k: "Conversaciones", v: number(totals.conversations) },
    { k: "Mensajes", v: number(totals.messages) },
    { k: "Mensajes por conversación", v: totals.messages_per_conversation },
    { k: "Consultas por voz", v: number(totals.audio_messages), u: `${totals.audio_minutes} min` },
    { k: "Confianza de clasificación", v: `${Math.round(totals.avg_confidence * 100)}%` },
    { k: "Respuesta media", v: (totals.avg_latency_ms / 1000).toFixed(1), u: "s" },
  ];
  el("kpis").innerHTML = tiles
    .map(
      (tile) =>
        `<div class="kpi"><div class="k">${escape(tile.k)}</div>` +
        `<div class="v">${escape(tile.v)}${tile.u ? `<span class="u">${escape(tile.u)}</span>` : ""}</div></div>`
    )
    .join("");
}

/* ---------- horizontal bars ---------- */

function bars(node, rows, { empty }) {
  if (!rows.length) {
    node.innerHTML = `<p class="empty">${escape(empty)}</p>`;
    return;
  }
  const max = Math.max(...rows.map((row) => row.value), 1);
  node.innerHTML = rows
    .map(
      (row) =>
        `<div class="bar-row">
           <span class="bar-label">${escape(row.label)}${row.tag ? ` <span class="tag-out">${escape(row.tag)}</span>` : ""}</span>
           <span class="bar-value">${escape(row.text)}</span>
           <span class="track"><span class="fill${row.warn ? " warn" : ""}" style="width:${(100 * row.value) / max}%"></span></span>
         </div>`
    )
    .join("");
}

/* ---------- channel donut ---------- */

function renderChannel(sources) {
  const audio = sources.audio || 0;
  const text = sources.text || 0;
  const total = audio + text;
  const node = el("channel");

  if (!total) {
    node.innerHTML = '<p class="empty">Sin mensajes todavía</p>';
    return;
  }

  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const audioArc = (audio / total) * circumference;

  node.innerHTML = `
    <svg viewBox="0 0 90 90" width="104" height="104" aria-hidden="true">
      <circle cx="45" cy="45" r="${radius}" stroke="var(--hover)" stroke-width="13" fill="none"></circle>
      <circle cx="45" cy="45" r="${radius}" stroke="var(--accent)" stroke-width="13" fill="none"
              stroke-dasharray="${audioArc} ${circumference - audioArc}"
              stroke-dashoffset="${circumference / 4}" stroke-linecap="butt"></circle>
      <text x="45" y="43" text-anchor="middle" style="font-size:13px;fill:var(--fg)">${Math.round((100 * audio) / total)}%</text>
      <text x="45" y="55" text-anchor="middle" style="font-size:8px">voz</text>
    </svg>
    <div class="legend">
      <div><span class="dot"></span> Audio <b>${number(audio)}</b></div>
      <div><span class="dot alt"></span> Texto <b>${number(text)}</b></div>
      <small>${number(total)} consultas en total</small>
    </div>`;
}

/* ---------- activity chart ---------- */

function renderActivity(daily) {
  const node = el("activity");
  if (!daily.length) {
    node.innerHTML = '<p class="empty">Sin actividad en el rango</p>';
    return;
  }

  const width = 100 * daily.length + 40;
  const height = 190;
  const top = 18;
  const base = height - 30;
  const max = Math.max(...daily.map((d) => d.messages), 1);
  const step = (width - 48) / daily.length;
  const barWidth = Math.min(step * 0.55, 34);

  const bars = daily
    .map((day, index) => {
      const scaled = ((base - top) * day.messages) / max;
      const x = 34 + index * step + (step - barWidth) / 2;
      const label = day.day.slice(5).replace("-", "/");
      return `
        <rect class="bar" x="${x}" y="${base - scaled}" width="${barWidth}" height="${scaled}" rx="3"></rect>
        <text x="${x + barWidth / 2}" y="${base - scaled - 5}" text-anchor="middle">${day.messages}</text>
        <text x="${x + barWidth / 2}" y="${base + 14}" text-anchor="middle">${label}</text>
        <text x="${x + barWidth / 2}" y="${base + 25}" text-anchor="middle">${day.conversations} conv</text>`;
    })
    .join("");

  node.innerHTML = `
    <svg class="chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      <line class="grid-line" x1="30" y1="${base}" x2="${width - 10}" y2="${base}"></line>
      <line class="grid-line" x1="30" y1="${top}" x2="${width - 10}" y2="${top}" stroke-dasharray="3 4"></line>
      <text x="26" y="${top + 4}" text-anchor="end">${max}</text>
      <text x="26" y="${base + 3}" text-anchor="end">0</text>
      ${bars}
    </svg>`;
}

/* ---------- hour chart ---------- */

function renderHours(hourly) {
  const node = el("hours");
  const max = Math.max(...hourly.map((h) => h.total), 0);
  if (!max) {
    node.innerHTML = '<p class="empty">Sin mensajes todavía</p>';
    return;
  }

  const width = 260;
  const height = 130;
  const base = height - 22;
  const step = width / 24;

  const bars = hourly
    .map((slot, hour) => {
      const scaled = Math.max(((base - 12) * slot.total) / max, slot.total ? 2 : 1);
      const x = hour * step + 1;
      const labeled = hour % 6 === 0;
      return `
        <rect class="bar${slot.total ? "" : " dim"}" x="${x}" y="${base - scaled}"
              width="${step - 2}" height="${scaled}" rx="2">
          <title>${hour}:00 · ${slot.total} mensajes</title>
        </rect>
        ${labeled ? `<text x="${x + step / 2}" y="${base + 13}" text-anchor="middle">${hour}h</text>` : ""}`;
    })
    .join("");

  const peak = hourly.reduce((best, slot) => (slot.total > best.total ? slot : best), hourly[0]);

  node.innerHTML = `
    <svg class="chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      <line class="grid-line" x1="0" y1="${base}" x2="${width}" y2="${base}"></line>
      ${bars}
    </svg>
    <p class="note">Hora más activa: ${peak.hour}:00 (${peak.total} mensajes)</p>`;
}

/* ---------- inventory ---------- */

function renderInventory(inventory) {
  el("inventory-note").textContent =
    `${inventory.products} SKU · ${inventory.categories} categorías · ${number(inventory.units)} unidades`;

  const node = el("inventory");
  if (!inventory.risky.length) {
    node.innerHTML = '<p class="empty">Todo el catálogo tiene stock suficiente</p>';
    return;
  }

  node.innerHTML =
    `<p class="note" style="margin-top:0">${inventory.out_of_stock} sin stock · ` +
    `${inventory.risky.length} por reponer</p>` +
    inventory.risky
      .map(
        (row) => `
        <div class="stock-row">
          <span class="bar-label">${escape(row.nombre)}</span>
          <span class="${row.stock === 0 ? "tag-out" : "bar-value"}">${row.stock === 0 ? "sin stock" : `${row.stock} u`}</span>
        </div>`
      )
      .join("");
}

/* ---------- recent table ---------- */

function renderRecent(rows) {
  const node = el("recent");
  if (!rows.length) {
    node.innerHTML = '<p class="empty">Sin conversaciones registradas</p>';
    return;
  }

  const body = rows
    .map(
      (row) => `
      <tr>
        <td class="num">#${row.id}</td>
        <td class="wide">${escape(row.title)}</td>
        <td><span class="chip">${escape(row.label)}</span></td>
        <td class="num">${Math.round(row.confidence * 100)}%</td>
        <td class="num">${row.messages}</td>
        <td class="num">${row.audio_messages}</td>
        <td>${new Date(row.updated_at).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" })}</td>
      </tr>`
    )
    .join("");

  node.innerHTML = `
    <table>
      <thead>
        <tr><th>ID</th><th>Resumen</th><th>Categoría</th><th>Conf.</th><th>Msj</th><th>Audio</th><th>Última actividad</th></tr>
      </thead>
      <tbody>${body}</tbody>
    </table>`;
}

/* ---------- load ---------- */

async function load() {
  const stats = await fetch(`/api/stats?days=${days}`).then((r) => r.json());

  renderKpis(stats.totals);

  bars(
    el("categories"),
    stats.categories.map((row) => ({
      label: row.label,
      value: row.total,
      text: `${row.total} · ${row.share}%`,
    })),
    { empty: "Sin conversaciones clasificadas" }
  );

  const mentioned = stats.products.filter((row) => row.menciones > 0);
  bars(
    el("products"),
    (mentioned.length ? mentioned : stats.products).slice(0, 10).map((row) => ({
      label: row.nombre,
      value: row.menciones,
      text: `${row.menciones} · S/ ${row.precio.toFixed(2)}`,
      tag: row.stock === 0 ? "sin stock" : "",
      warn: row.stock === 0 && row.menciones > 0,
    })),
    { empty: "Sin menciones de productos" }
  );

  renderInventory(stats.inventory);
  renderChannel(stats.sources);
  renderActivity(stats.daily);
  renderHours(stats.hourly);
  renderRecent(stats.recent);

  el("activity-note").textContent = `últimos ${stats.days} días`;
}

el("range").onclick = (event) => {
  const button = event.target.closest("button[data-days]");
  if (!button) return;
  days = Number(button.dataset.days);
  [...el("range").children].forEach((child) => child.classList.toggle("on", child === button));
  load();
};

fetch("/api/config")
  .then((r) => r.json())
  .then((config) => {
    el("store").textContent = config.store;
    document.title = `${config.store} · Panel`;
  });

load();
setInterval(load, 30000);
