# VSE – Text-to-Speech Web UI

Lokale Web-Oberfläche für Applio TTS/RVC. Macht Sprachmodelle für Nutzer ohne CLI-Erfahrung zugänglich.

Architektur und Anforderungen: [`docs/`](docs/)

---

## Wie es funktioniert

Zwei Python-Prozesse arbeiten zusammen:

| Prozess | Läuft auf | Port | Aufgabe |
|---------|-----------|------|---------|
| `local_ui_server.py` | VM | 5500 | Frontend ausliefern, API-Proxy zum Runner |
| `applio_runner.py` | Host (GPU) | 5600 | Applio CLI kapseln, Audio als Base64 zurückgeben |

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/Fabian4423/VSE.git
cd VSE
```

### 2. Runner konfigurieren (Host-System, einmalig)

```bash
cp runner.env.example runner.env
```

`runner.env` anpassen:

```env
APPLIO_ROOT=/pfad/zu/Applio
APPLIO_PYTHON=/pfad/zu/Applio/.venv/bin/python
RVC_MODEL_ROOT=/pfad/zu/VSE/backend/models/rvc
```

### 3. UI-Server konfigurieren (VM, einmalig)

```bash
cp backend/.env.example backend/.env
```

`backend/.env` anpassen:

```env
APPLIO_RUNNER_URL=http://<HOST-IP>:5600
STORAGE_ROOT=/pfad/zu/VSE/backend/storage
```

> Wenn Runner und UI-Server auf derselben Maschine laufen: `APPLIO_RUNNER_URL=http://localhost:5600`

### 4. Stimmmodelle hinzufügen

Modelle im folgenden Format ablegen (Verzeichnisname = `voice_id`):

```
backend/models/rvc/
└── MeineStimme/
    ├── MeineStimme.pth      ← obligatorisch
    └── MeineStimme.index    ← optional, verbessert Qualität
```

Neue Modelle werden automatisch erkannt — kein Neustart nötig.

---

## Starten

**Host-System (Runner):**
```bash
python3 applio_runner.py
```

**VM (UI-Server):**
```bash
python3 local_ui_server.py
```

Dann im Browser öffnen: `http://127.0.0.1:5500`

---

## Schnelltest

```bash
# Runner erreichbar?
curl http://localhost:5600/health

# Modelle geladen?
curl http://localhost:5500/api/voices
```

---

## Frontend-Entwicklung

Die Oberfläche liegt in `frontend/` (HTML/CSS/JS, keine Build-Tools nötig).

Der UI-Server liefert die Dateien direkt aus — nach Änderungen einfach im Browser neu laden.

```
frontend/
├── index.html
├── app.js
└── styles.css
```

API-Endpunkte für die UI:

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/voices` | GET | Verfügbare Stimmmodelle |
| `/api/run` | POST | Audio erzeugen (Text- oder Audio-Modus) |
| `/storage/*` | GET | Generierte Audiodateien abrufen |

**POST /api/run – Text-Modus:**
```json
{
  "voice_id": "MeineStimme",
  "text": "Hallo Welt",
  "tts_voice": "de-DE-KatjaNeural",
  "tts_rate": 0
}
```

**POST /api/run – Audio-Modus:**
```json
{
  "voice_id": "MeineStimme",
  "audio_base64": "data:audio/wav;base64,..."
}
```

**Response:**
```json
{
  "output_audio_url": "/storage/output/<uuid>.wav"
}
```

---

## Stoppen

```bash
pkill -f applio_runner.py
pkill -f local_ui_server.py
```
