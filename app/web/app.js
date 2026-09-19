const el = (id) => document.getElementById(id);
const thread = el("thread");
const list = el("conversations");
const input = el("input");
const micButton = el("mic");
const sendButton = el("send");
const timer = el("timer");

let conversationId = null;
let busy = false;
let recorder = null;
let chunks = [];
let tick = null;
let ttsEnabled = false;
let player = null;
let playing = null;

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

el("menu").onclick = () => el("sidebar").classList.toggle("open");

const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = (text) => text.replace(/[&<>"']/g, (c) => ENTITIES[c]);

const inline = (text) =>
  text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)\*(?!\s)(.+?)\*/g, "$1<em>$2</em>");

function format(text) {
  return escape(text || "")
    .trim()
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n");
      if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
        const items = lines
          .map((line) => `<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }
      return `<p>${inline(lines.join("<br>"))}</p>`;
    })
    .join("");
}

const scroll = () => thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });

function addMessage(role, text, meta) {
  el("empty")?.remove();
  const message = document.createElement("div");
  message.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = format(text);
  if (meta) bubble.insertAdjacentHTML("beforeend", `<span class="meta">${escape(meta)}</span>`);
  message.append(bubble);
  thread.append(message);
  scroll();
  return bubble;
}

const SPEAKER_ICON = `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
  <path d="M4 10v4h3l4 3V7L7 10H4Z"/><path d="M15.5 9a4 4 0 0 1 0 6"/><path d="M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>`;
const STOP_ICON = `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
  <rect x="7" y="7" width="10" height="10" rx="2"/></svg>`;

function stopPlayback() {
  if (player) player.pause();
  player = null;
  if (playing) {
    playing.classList.remove("on");
    playing.innerHTML = SPEAKER_ICON;
    playing = null;
  }
}

function addSpeakButton(bubble, text) {
  if (!ttsEnabled || !text.trim()) return;

  const actions = document.createElement("div");
  actions.className = "bubble-actions";
  const button = document.createElement("button");
  button.className = "speak";
  button.title = "Escuchar respuesta";
  button.setAttribute("aria-label", "Escuchar respuesta");
  button.innerHTML = SPEAKER_ICON;
  actions.append(button);
  bubble.append(actions);

  button.onclick = async () => {
    if (playing === button) {
      stopPlayback();
      return;
    }
    stopPlayback();

    if (!button.dataset.src) {
      button.disabled = true;
      button.classList.add("wait");
      try {
        const response = await fetch("/api/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        button.dataset.src = URL.createObjectURL(await response.blob());
      } catch {
        toast("No se pudo generar la voz");
        return;
      } finally {
        button.disabled = false;
        button.classList.remove("wait");
      }
    }

    player = new Audio(button.dataset.src);
    playing = button;
    button.classList.add("on");
    button.innerHTML = STOP_ICON;
    player.onended = stopPlayback;
    player.play().catch(() => stopPlayback());
  };
}

function addTyping() {
  const bubble = addMessage("assistant", "");
  bubble.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
  return bubble;
}

function toast(text) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = text;
  document.body.append(node);
  setTimeout(() => node.remove(), 3200);
}

async function loadConversations() {
  const conversations = await fetch("/api/conversations").then((r) => r.json());
  list.innerHTML = "";
  conversations.forEach((conversation) => {
    const row = document.createElement("div");
    row.className = "conv-row";

    const button = document.createElement("button");
    button.className = "conv" + (conversation.id === conversationId ? " active" : "");
    button.innerHTML =
      `<b>${escape(conversation.title)}</b><small>${escape(conversation.category_label)}</small>`;
    button.onclick = () => openConversation(conversation.id);

    const remove = document.createElement("button");
    remove.className = "conv-delete";
    remove.title = "Eliminar conversación";
    remove.setAttribute("aria-label", `Eliminar conversación: ${conversation.title}`);
    remove.innerHTML = TRASH_ICON;
    remove.onclick = () => deleteConversation(conversation.id, conversation.title);

    row.append(button, remove);
    list.append(row);
  });
}

const TRASH_ICON = `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
  <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>`;

async function deleteConversation(id, title) {
  if (busy && id === conversationId) {
    toast("Espera a que termine la respuesta");
    return;
  }
  if (!confirm(`¿Eliminar la conversación "${title}"?`)) return;

  try {
    const response = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch {
    toast("No se pudo eliminar la conversación");
    return;
  }

  if (id === conversationId) resetChat();
  else loadConversations();
  toast("Conversación eliminada");
}

async function openConversation(id) {
  const data = await fetch(`/api/conversations/${id}`).then((r) => r.json());
  conversationId = id;
  stopPlayback();
  thread.innerHTML = "";
  data.messages.forEach((message) => {
    const bubble = addMessage(
      message.role,
      message.content,
      message.source === "audio" ? "audio" : null
    );
    if (message.role === "assistant") addSpeakButton(bubble, message.content);
  });
  el("sidebar").classList.remove("open");
  loadConversations();
}

function resetChat() {
  conversationId = null;
  stopPlayback();
  thread.innerHTML =
    '<div id="empty" class="empty"><p>Escribe tu consulta o graba un audio.</p></div>';
  loadConversations();
  input.focus();
}

el("new-chat").onclick = resetChat;

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  micButton.disabled = value;
}

async function* readEvents(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop();
    for (const frame of frames) {
      const name = frame.match(/^event: (.+)$/m)?.[1];
      const payload = frame.match(/^data: (.+)$/m)?.[1];
      if (name && payload) yield { event: name, data: JSON.parse(payload) };
    }
  }
}

async function send(text, source = "text", language = null, seconds = null) {
  if (!text || busy) return;
  addMessage("user", text, source === "audio" ? `audio · ${seconds}s` : null);
  setBusy(true);
  const bubble = addTyping();
  let answer = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        conversation_id: conversationId,
        source,
        language,
        audio_seconds: seconds,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    for await (const { event, data } of readEvents(response)) {
      if (event === "start") conversationId = data.conversation_id;
      if (event === "token") {
        answer += data.text;
        bubble.innerHTML = format(answer);
        scroll();
      }
      if (event === "error") bubble.innerHTML = format(data.detail);
      if (event === "done") {
        conversationId = data.conversation_id;
        loadConversations();
      }
    }
    if (!bubble.textContent.trim()) bubble.innerHTML = format("Sin respuesta del modelo.");
    addSpeakButton(bubble, answer);
  } catch (error) {
    bubble.innerHTML = format(`No pude responder ahora mismo (${error.message}).`);
  } finally {
    setBusy(false);
    input.focus();
  }
}

el("composer").onsubmit = (event) => {
  event.preventDefault();
  const text = input.value.trim();
  input.value = "";
  input.style.height = "auto";
  send(text);
};

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    el("composer").requestSubmit();
  }
});

const MIME = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(
  (type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)
);

function startTimer() {
  const started = Date.now();
  timer.textContent = "0:00";
  tick = setInterval(() => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    timer.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    if (seconds >= 120) recorder.stop();
  }, 250);
}

function stopTimer() {
  clearInterval(tick);
  timer.textContent = "";
  micButton.classList.remove("recording");
}

async function transcribe(blob) {
  setBusy(true);
  const extension = MIME.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("audio", blob, `clip.${extension}`);
  try {
    const result = await fetch("/api/transcribe", { method: "POST", body: form }).then((r) =>
      r.json()
    );
    setBusy(false);
    if (!result.text) {
      toast("No se detectó voz en el audio");
      return;
    }
    send(result.text, "audio", result.language, result.duration);
  } catch {
    setBusy(false);
    toast("No se pudo transcribir el audio");
  }
}

micButton.onclick = async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  if (!navigator.mediaDevices || !MIME) {
    toast("Este navegador no permite grabar audio");
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    toast("Sin acceso al micrófono");
    return;
  }

  chunks = [];
  recorder = new MediaRecorder(stream, { mimeType: MIME });
  recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    stopTimer();
    const blob = new Blob(chunks, { type: MIME });
    if (blob.size < 1200) {
      toast("Grabación demasiado corta");
      return;
    }
    await transcribe(blob);
  };

  recorder.start();
  micButton.classList.add("recording");
  startTimer();
};

fetch("/api/config")
  .then((r) => r.json())
  .then((config) => {
    el("store").textContent = config.store;
    document.title = `${config.store} · Asistente`;
    ttsEnabled = Boolean(config.tts);
  });

loadConversations();
input.focus();
