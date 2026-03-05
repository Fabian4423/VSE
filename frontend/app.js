const voiceIdEl = document.getElementById("voiceId");
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
const downloadBtnEl = document.getElementById("downloadBtn");
let latestDownload = null;

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

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function setDownloadButton(url = "", filename = "vse-output.wav") {
  if (!url) {
    downloadBtnEl.href = "#";
    downloadBtnEl.setAttribute("aria-disabled", "true");
    downloadBtnEl.classList.add("disabled");
    latestDownload = null;
    return;
  }
  downloadBtnEl.href = url;
  downloadBtnEl.download = filename;
  downloadBtnEl.setAttribute("aria-disabled", "false");
  downloadBtnEl.classList.remove("disabled");
  latestDownload = { url, filename };
}

function updateMode() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  textWrapEl.classList.toggle("hidden", mode !== "text");
  audioWrapEl.classList.toggle("hidden", mode !== "audio");
}

async function loadVoices() {
  setStatus("Lade Voices...");
  const res = await fetch("/api/voices");
  if (!res.ok) {
    throw new Error(`GET /api/voices fehlgeschlagen (${res.status})`);
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

  const payload = {
    voice_id: voiceId,
    tts_voice: ttsVoiceEl.value,
    tts_rate: Number(ttsRateEl.value || "0"),
  };

  if (mode === "text") {
    const text = textInputEl.value.trim();
    if (!text) {
      setStatus("Bitte Text eingeben.", true);
      return;
    }
    payload.text = text;
  } else {
    const file = audioInputEl.files?.[0];
    if (!file) {
      setStatus("Bitte eine Audiodatei wählen.", true);
      return;
    }
    payload.audio_base64 = await fileToBase64(file);
    payload.audio_name = file.name || "input.wav";
  }

  runBtnEl.disabled = true;
  setStatus("Verarbeite Anfrage...");
  audioPlayerEl.removeAttribute("src");
  audioPlayerEl.load();
  setDownloadButton();

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request fehlgeschlagen (${res.status})`);
    }

    const data = await res.json();
    inputTextEl.textContent = data.input_text || "-";
    responseTextEl.textContent = data.response_text || "-";

    const audioUrl = data.output_audio_url || "";
    if (!audioUrl) {
      throw new Error("Kein Audio-Output vom Server erhalten.");
    }

    audioPlayerEl.src = audioUrl;
    audioPlayerEl.load();
    const fileName = (data.output_audio_path || "").split("/").pop() || "vse-output.wav";
    setDownloadButton(audioUrl, fileName);
    setStatus("Fertig.");
  } catch (error) {
    setDownloadButton();
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

downloadBtnEl.addEventListener("click", async (event) => {
  event.preventDefault();
  if (!latestDownload) return;

  try {
    setStatus("Download startet...");
    const res = await fetch(latestDownload.url);
    if (!res.ok) {
      throw new Error(`Download fehlgeschlagen (${res.status})`);
    }
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = latestDownload.filename || "vse-output.wav";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
    setStatus("Download fertig.");
  } catch (error) {
    setStatus(String(error.message || error), true);
  }
});

updateMode();
setDownloadButton();
loadVoices().catch((error) => setStatus(String(error.message || error), true));
