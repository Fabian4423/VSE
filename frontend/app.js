const apiBaseEl = document.getElementById("apiBase");
const voiceIdEl = document.getElementById("voiceId");
const ttsProviderEl = document.getElementById("ttsProvider");
const ttsVoiceEl = document.getElementById("ttsVoice");
const ttsRateEl = document.getElementById("ttsRate");
const textWrapEl = document.getElementById("textWrap");
const audioWrapEl = document.getElementById("audioWrap");
const textInputEl = document.getElementById("textInput");
const audioInputEl = document.getElementById("audioInput");
const runBtnEl = document.getElementById("runBtn");
const refreshVoicesEl = document.getElementById("refreshVoices");
const statusEl = document.getElementById("status");
const inputTextEl = document.getElementById("inputText");
const responseTextEl = document.getElementById("responseText");
const audioPlayerEl = document.getElementById("audioPlayer");

function getApiBase() {
  return apiBaseEl.value.replace(/\/+$/, "");
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function updateMode() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  textWrapEl.classList.toggle("hidden", mode !== "text");
  audioWrapEl.classList.toggle("hidden", mode !== "audio");
}

async function loadVoices() {
  setStatus("Lade Voices...");
  const res = await fetch(`${getApiBase()}/voices`);
  if (!res.ok) {
    throw new Error(`GET /voices fehlgeschlagen (${res.status})`);
  }
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
  setStatus(`Voices geladen: ${voices.length}`);
}

async function runAssistant() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  const voiceId = voiceIdEl.value;
  if (!voiceId) {
    setStatus("Keine Voice verfügbar.", true);
    return;
  }

  const fd = new FormData();
  fd.set("voice_id", voiceId);
  fd.set("tts_provider", ttsProviderEl.value);
  fd.set("tts_voice", ttsVoiceEl.value);
  fd.set("tts_rate", ttsRateEl.value || "0");

  if (mode === "text") {
    const text = textInputEl.value.trim();
    if (!text) {
      setStatus("Bitte Text eingeben.", true);
      return;
    }
    fd.set("text", text);
  } else {
    const file = audioInputEl.files?.[0];
    if (!file) {
      setStatus("Bitte eine Audiodatei wählen.", true);
      return;
    }
    fd.set("audio_file", file);
  }

  runBtnEl.disabled = true;
  setStatus("Verarbeite Anfrage...");
  audioPlayerEl.removeAttribute("src");
  audioPlayerEl.load();

  try {
    const res = await fetch(`${getApiBase()}/assistant/respond`, {
      method: "POST",
      body: fd,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request fehlgeschlagen (${res.status})`);
    }

    const data = await res.json();
    inputTextEl.textContent = data.input_text || "-";
    responseTextEl.textContent = data.response_text || "-";

    const audioUrl = data.output_audio_url?.startsWith("http")
      ? data.output_audio_url
      : `${getApiBase()}${data.output_audio_url}`;

    audioPlayerEl.src = audioUrl;
    audioPlayerEl.load();
    setStatus("Fertig.");
  } catch (error) {
    setStatus(String(error.message || error), true);
  } finally {
    runBtnEl.disabled = false;
  }
}

document.querySelectorAll("input[name='mode']").forEach((el) => {
  el.addEventListener("change", updateMode);
});

refreshVoicesEl.addEventListener("click", () => {
  loadVoices().catch((error) => setStatus(String(error.message || error), true));
});

runBtnEl.addEventListener("click", () => {
  runAssistant().catch((error) => setStatus(String(error.message || error), true));
});

updateMode();
loadVoices().catch((error) => setStatus(String(error.message || error), true));

