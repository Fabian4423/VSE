// ── Element refs ──────────────────────────────────────────
const voiceIdEl       = document.getElementById("voiceId");
const ttsVoiceEl      = document.getElementById("ttsVoice");
const ttsRateEl       = document.getElementById("ttsRate");
const ttsPresetEl     = document.getElementById("ttsPreset");
const speedValueEl    = document.getElementById("speedValue");
const textWrapEl      = document.getElementById("textWrap");
const audioWrapEl     = document.getElementById("audioWrap");
const textInputEl     = document.getElementById("textInput");
const audioInputEl    = document.getElementById("audioInput");
const fileLabelEl     = document.getElementById("fileLabel");
const fileLabelTextEl = document.getElementById("fileLabelText");
const runBtnEl        = document.getElementById("runBtn");
const refreshVoicesEl = document.getElementById("refreshVoices");
const statusTextEl    = document.getElementById("statusText");
const statusDotEl     = document.querySelector(".status-dot");
const chatAreaEl      = document.getElementById("chatArea");
const emptyStateEl    = document.getElementById("emptyState");
const pillTextEl      = document.getElementById("pillText");
const pillAudioEl     = document.getElementById("pillAudio");
const sidebarEl       = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebarToggle");
const openSidebarEl   = document.getElementById("openSidebar");

// ── Tonlage-Presets ───────────────────────────────────────
// Jedes Preset setzt: tts_voice (Edge-Stimme) + rate-Offset
const PRESETS = {
  sachlich:     { voice: "de-DE-KatjaNeural",     rateOffset: 0  },
  freundlich:   { voice: "de-DE-SeraphinaNeural", rateOffset: 5  },
  energetisch:  { voice: "de-DE-AmalaNeural",     rateOffset: 30 },
  jugendlich:   { voice: "de-DE-AmalaNeural",     rateOffset: 10 },
  bestimmt:     { voice: "de-DE-ConradNeural",    rateOffset: 0  },
  eindringlich: { voice: "de-DE-ConradNeural",    rateOffset: 20 },
};

function getEffectiveRate() {
  const preset = PRESETS[ttsPresetEl.value] || PRESETS.sachlich;
  return Number(ttsRateEl.value) + preset.rateOffset;
}

function applyPreset() {
  const preset = PRESETS[ttsPresetEl.value] || PRESETS.sachlich;
  ttsVoiceEl.value = preset.voice;
}

// ── Helpers ───────────────────────────────────────────────
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error || new Error("Datei konnte nicht gelesen werden."));
    reader.readAsDataURL(file);
  });
}

function setStatus(message, state = "ready") {
  statusTextEl.textContent = message;
  statusDotEl.className = "status-dot";
  if (state === "busy")  statusDotEl.classList.add("busy");
  if (state === "error") statusDotEl.classList.add("error");
}

// ── Mode switching ────────────────────────────────────────
function updateMode() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  textWrapEl.classList.toggle("hidden", mode !== "text");
  audioWrapEl.classList.toggle("hidden", mode !== "audio");
  pillTextEl.classList.toggle("active", mode === "text");
  pillAudioEl.classList.toggle("active", mode === "audio");
}

// ── Sidebar ───────────────────────────────────────────────
function toggleSidebar() {
  sidebarEl.classList.toggle("collapsed");
}

// ── Auto-resize textarea ──────────────────────────────────
textInputEl.addEventListener("input", () => {
  textInputEl.style.height = "auto";
  textInputEl.style.height = Math.min(textInputEl.scrollHeight, 180) + "px";
});

textInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    runAssistant().catch((err) => appendError(String(err.message || err)));
  }
});

// ── File input label ──────────────────────────────────────
audioInputEl.addEventListener("change", () => {
  const file = audioInputEl.files?.[0];
  if (file) {
    fileLabelTextEl.textContent = file.name;
    fileLabelEl.classList.add("has-file");
  } else {
    fileLabelTextEl.textContent = "Audiodatei waehlen...";
    fileLabelEl.classList.remove("has-file");
  }
});

// ── Speed slider label ────────────────────────────────────
function updateSpeedLabel() {
  const v = Number(ttsRateEl.value);
  let label;
  if (v === 0)       label = "Normal (0)";
  else if (v <= -50) label = `Sehr langsam (${v})`;
  else if (v < 0)    label = `Langsamer (${v})`;
  else if (v >= 50)  label = `Sehr schnell (+${v})`;
  else               label = `Schneller (+${v})`;
  speedValueEl.textContent = label;
}

ttsRateEl.addEventListener("input", updateSpeedLabel);

// ── Custom Preset Dropdown ────────────────────────────────
const presetTriggerEl = document.getElementById("presetTrigger");
const presetListEl    = document.getElementById("presetList");
const presetLabelEl   = document.getElementById("presetLabel");
const presetSelectEl  = document.getElementById("presetSelect");

presetTriggerEl.addEventListener("click", (e) => {
  e.stopPropagation();
  const isOpen = presetSelectEl.classList.contains("open");
  presetSelectEl.classList.toggle("open", !isOpen);
  presetTriggerEl.setAttribute("aria-expanded", String(!isOpen));
});

presetListEl.querySelectorAll(".custom-select-option").forEach((opt) => {
  opt.addEventListener("click", () => {
    const val = opt.dataset.value;
    ttsPresetEl.value = val;
    presetLabelEl.textContent = opt.textContent;
    presetListEl.querySelectorAll(".custom-select-option").forEach(o => o.classList.remove("selected"));
    opt.classList.add("selected");
    presetSelectEl.classList.remove("open");
    presetTriggerEl.setAttribute("aria-expanded", "false");
    applyPreset();
  });
});

document.addEventListener("click", () => {
  presetSelectEl.classList.remove("open");
  presetTriggerEl.setAttribute("aria-expanded", "false");
});

// ── Chat rendering ────────────────────────────────────────
function hideEmpty() {
  if (emptyStateEl) emptyStateEl.remove();
}

function scrollToBottom() {
  chatAreaEl.scrollTo({ top: chatAreaEl.scrollHeight, behavior: "smooth" });
}

function appendUserMessage(text) {
  hideEmpty();
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `
    <div class="msg-bubble">
      <div class="msg-text">${escHtml(text)}</div>
    </div>
    <div class="msg-avatar">Du</div>
  `;
  chatAreaEl.appendChild(row);
  scrollToBottom();
}

function appendUserAudio(filename) {
  hideEmpty();
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `
    <div class="msg-bubble">
      <div class="msg-label">Audio-Datei</div>
      <div class="msg-text">${escHtml(filename)}</div>
    </div>
    <div class="msg-avatar">Du</div>
  `;
  chatAreaEl.appendChild(row);
  scrollToBottom();
}

function appendThinking() {
  hideEmpty();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "thinkingRow";
  row.innerHTML = `
    <div class="msg-avatar">VSE</div>
    <div class="msg-bubble">
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  chatAreaEl.appendChild(row);
  scrollToBottom();
  return row;
}

function removeThinking() {
  document.getElementById("thinkingRow")?.remove();
}

function appendBotResult(data) {
  removeThinking();
  const audioUrl  = data.output_audio_url || "";
  const fileName  = (data.output_audio_path || "").split("/").pop() || "chattie-output.wav";
  const inputText    = data.input_text || "";
  const responseText = data.response_text || "";

  const row = document.createElement("div");
  row.className = "msg-row bot";

  let audioHtml = "";
  if (audioUrl) {
    audioHtml = `
      <div class="audio-card">
        <audio controls src="${escAttr(audioUrl)}"></audio>
        <a class="download-link" href="${escAttr(audioUrl)}" download="${escAttr(fileName)}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          ${escHtml(fileName)} herunterladen
        </a>
      </div>
    `;
  }

  let bodyHtml = "";
  if (inputText)    bodyHtml += `<div class="msg-label">Erkannter Text</div><div class="msg-text">${escHtml(inputText)}</div>`;
  if (responseText) bodyHtml += `${inputText ? '<div style="margin-top:8px"></div>' : ''}<div class="msg-label">Antwort</div><div class="msg-text">${escHtml(responseText)}</div>`;
  bodyHtml += audioHtml;

  row.innerHTML = `
    <div class="msg-avatar">VSE</div>
    <div class="msg-bubble">${bodyHtml}</div>
  `;

  const dlLink = row.querySelector(".download-link");
  if (dlLink && audioUrl) {
    dlLink.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        setStatus("Download laeuft...", "busy");
        const res = await fetch(audioUrl);
        if (!res.ok) throw new Error(`Download fehlgeschlagen (${res.status})`);
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objUrl;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(objUrl);
        setStatus("Download fertig.", "ready");
      } catch (err) {
        setStatus(String(err.message || err), "error");
      }
    });
  }

  chatAreaEl.appendChild(row);
  scrollToBottom();
}

function appendError(message) {
  removeThinking();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.innerHTML = `
    <div class="msg-avatar">VSE</div>
    <div class="msg-bubble error-bubble">
      <div class="msg-text">${escHtml(message)}</div>
    </div>
  `;
  chatAreaEl.appendChild(row);
  scrollToBottom();
}

// ── Voices ────────────────────────────────────────────────
async function loadVoices() {
  setStatus("Lade Voices...", "busy");
  try {
    const res = await fetch("/api/voices");
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    const voices = data.voices || [];
    voiceIdEl.innerHTML = "";
    voices.forEach((voice) => {
      const opt = document.createElement("option");
      opt.value = voice.voice_id;
      const suffix = voice.has_index ? "index" : "no-index";
      opt.textContent = `${voice.voice_id} (${suffix})`;
      voiceIdEl.appendChild(opt);
    });
    setStatus(`${voices.length} Voices geladen`, "ready");
  } catch (err) {
    setStatus(friendlyError(err), "error");
  }
}

// ── Main action ───────────────────────────────────────────
async function runAssistant() {
  const mode    = document.querySelector("input[name='mode']:checked").value;
  const voiceId = voiceIdEl.value;

  if (!voiceId) { appendError("Keine Voice verfuegbar."); return; }

  applyPreset();

  const payload = {
    voice_id:  voiceId,
    tts_voice: ttsVoiceEl.value,
    tts_rate:  getEffectiveRate(),
  };

  if (mode === "text") {
    const text = textInputEl.value.trim();
    if (!text) { setStatus("Bitte Text eingeben.", "error"); return; }
    payload.text = text;
    appendUserMessage(text);
    textInputEl.value = "";
    textInputEl.style.height = "auto";
  } else {
    const file = audioInputEl.files?.[0];
    if (!file) { setStatus("Bitte Audiodatei waehlen.", "error"); return; }
    payload.audio_base64 = await fileToBase64(file);
    payload.audio_name   = file.name || "input.wav";
    appendUserAudio(file.name);
    audioInputEl.value = "";
    fileLabelTextEl.textContent = "Audiodatei waehlen...";
    fileLabelEl.classList.remove("has-file");
  }

  runBtnEl.disabled = true;
  setStatus("Verarbeite...", "busy");
  appendThinking();

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request fehlgeschlagen (${res.status})`);
    }
    const data = await res.json();
    if (!data.output_audio_url) throw new Error("Kein Audio-Output vom Server erhalten.");
    appendBotResult(data);
    setStatus("Fertig.", "ready");
  } catch (err) {
    const msg = friendlyError(err);
    appendError(msg);
    setStatus(msg, "error");
  } finally {
    runBtnEl.disabled = false;
  }
}

// ── Sanitizers ────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function escAttr(str) { return escHtml(str); }

function friendlyError(err) {
  const msg = String(err?.message || err);
  if (
    msg.includes("Failed to fetch") ||
    msg.includes("NetworkError") ||
    msg.includes("fetch") ||
    msg.includes("404") ||
    msg.includes("ECONNREFUSED") ||
    msg.includes("fehlgeschlagen")
  ) return "Keine Verbindung zum Server";
  return msg;
}

// ── Event listeners ───────────────────────────────────────
document.querySelectorAll("input[name='mode']").forEach((el) => el.addEventListener("change", updateMode));
refreshVoicesEl.addEventListener("click", () => loadVoices());
runBtnEl.addEventListener("click", () => runAssistant().catch((err) => appendError(friendlyError(err))));
sidebarToggleEl.addEventListener("click", toggleSidebar);
openSidebarEl.addEventListener("click", toggleSidebar);

// ── Init ──────────────────────────────────────────────────
updateMode();
updateSpeedLabel();
applyPreset();
loadVoices();