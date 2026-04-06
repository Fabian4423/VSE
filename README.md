# VSE – Text-to-Speech Web UI

Lokale Web-Oberfläche für Chatterbox TTS. Macht Sprachausgabe mit 28 vordefinierten Stimmen für Nutzer ohne CLI-Erfahrung zugänglich.

Architektur und Anforderungen: [`docs/`](docs/)

---

## Wie es funktioniert

Der UI-Server stellt das Frontend bereit und leitet TTS-Anfragen an den Chatterbox-Service weiter:

| Prozess | Läuft auf | Port | Aufgabe |
|---------|-----------|------|---------|
| `local_ui_server.py` | VM | 5174 | Frontend ausliefern, API-Proxy zu Chatterbox |
| Chatterbox TTS | Host (GPU) | 8004 | Text-to-Speech mit vordefinierten Stimmen |

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/Fabian4423/VSE.git
cd VSE
```

### 2. UI-Server konfigurieren (VM, einmalig)

```bash
cp backend/.env.example backend/.env
```

`backend/.env` anpassen:

```env
CHATTERBOX_URL=http://<HOST-IP>:8004
STORAGE_ROOT=/pfad/zu/VSE/backend/storage
```

> Wenn Chatterbox und UI-Server auf derselben Maschine laufen: `CHATTERBOX_URL=http://localhost:8004`

### 3. Verfügbare Stimmen

Die verfügbaren Stimmen werden **dynamisch vom Chatterbox-Service** abgefragt. Neue Stimmen erscheinen automatisch in der UI, sobald sie im Chatterbox-Service registriert sind.

---

## Starten

**VM (UI-Server):**
```bash
python3 local_ui_server.py
```

Dann im Browser öffnen: `http://127.0.0.1:5174`

---

## Schnelltest

```bash
# UI-Server erreichbar?
curl http://localhost:5174/api/voices

# Chatterbox direkt testen:
curl -X POST "http://192.168.100.64:8004/tts" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hallo Welt", "voice_mode": "predefined", "predefined_voice_id": "Alexander.wav"}' \
  -o test.wav
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
| `/api/voices` | GET | Verfügbare Stimmen |
| `/api/run` | POST | Audio erzeugen (Text-Modus) |
| `/storage/*` | GET | Generierte Audiodateien abrufen |

**POST /api/run:**
```json
{
  "voice_id": "Alexander",
  "text": "Hallo Welt"
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
pkill -f local_ui_server.py
```
