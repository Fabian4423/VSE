// ── Element refs ──────────────────────────────────────────
const voiceIdEl       = document.getElementById("voiceId");
const textInputEl     = document.getElementById("textInput");
const runBtnEl        = document.getElementById("runBtn");
const refreshVoicesEl = document.getElementById("refreshVoices");
const previewVoiceEl  = document.getElementById("previewVoice");
const previewAudioEl  = document.getElementById("previewAudio");
const statusTextEl    = document.getElementById("statusText");
const statusDotEl     = document.querySelector(".status-dot");
const chatAreaEl      = document.getElementById("chatArea");
const emptyStateEl    = document.getElementById("emptyState");
const sidebarEl       = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebarToggle");
const openSidebarEl   = document.getElementById("openSidebar");

// ── Helpers ───────────────────────────────────────────────
function setStatus(message, state = "ready") {
  statusTextEl.textContent = message;
  statusDotEl.className = "status-dot";
  if (state === "busy")  statusDotEl.classList.add("busy");
  if (state === "error") statusDotEl.classList.add("error");
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
  if (responseText) bodyHtml += `<div class="msg-label">Sprachausgabe</div><div class="msg-text">${escHtml(responseText)}</div>`;
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
    const res = await fetch("api/voices");
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    const voices = data.voices || [];
    voiceIdEl.innerHTML = "";
    voices.forEach((voice) => {
      const opt = document.createElement("option");
      opt.value = voice.voice_id;
      opt.textContent = voice.voice_id;
      voiceIdEl.appendChild(opt);
    });
    setStatus(`${voices.length} Stimmen geladen`, "ready");
  } catch (err) {
    setStatus(friendlyError(err), "error");
  }
}

// ── Main action ───────────────────────────────────────────
async function runAssistant() {
  const voiceId = voiceIdEl.value;
  if (!voiceId) { appendError("Keine Stimme verfuegbar."); return; }

  const text = textInputEl.value.trim();
  if (!text) { setStatus("Bitte Text eingeben.", "error"); return; }

  appendUserMessage(text);
  textInputEl.value = "";
  textInputEl.style.height = "auto";

  runBtnEl.disabled = true;
  setStatus("Verarbeite...", "busy");
  appendThinking();

  try {
    const res = await fetch("api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_id: voiceId, text }),
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

// ── Voice preview ─────────────────────────────────────────
async function previewVoice() {
  const voiceId = voiceIdEl.value;
  if (!voiceId) { setStatus("Keine Stimme ausgewaehlt.", "error"); return; }

  if (!previewAudioEl.paused) {
    previewAudioEl.pause();
    previewAudioEl.currentTime = 0;
    setStatus("Preview gestoppt.", "ready");
    return;
  }

  previewVoiceEl.disabled = true;
  setStatus(`Lade Preview: ${voiceId}...`, "busy");
  try {
    const url = `api/voices/${encodeURIComponent(voiceId)}/preview`;
    previewAudioEl.src = url;
    await previewAudioEl.play();
    setStatus(`Preview: ${voiceId}`, "ready");
  } catch (err) {
    setStatus(`Preview fehlgeschlagen: ${friendlyError(err)}`, "error");
  } finally {
    previewVoiceEl.disabled = false;
  }
}

previewAudioEl.addEventListener("ended", () => setStatus("Bereit", "ready"));

// ── Event listeners ───────────────────────────────────────
refreshVoicesEl.addEventListener("click", () => loadVoices());
previewVoiceEl.addEventListener("click", () => previewVoice());
runBtnEl.addEventListener("click", () => runAssistant().catch((err) => appendError(friendlyError(err))));
sidebarToggleEl.addEventListener("click", toggleSidebar);
openSidebarEl.addEventListener("click", toggleSidebar);

// ── Init ──────────────────────────────────────────────────
loadVoices();
