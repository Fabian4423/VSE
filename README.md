# VSE

Lokale TTS/STS Web-UI mit direkter Applio-CLI-Ansteuerung.

Die Anwendung läuft als **ein lokaler Python-Prozess** (`local_ui_server.py`) und stellt:
- das Frontend (`/`)
- eine kleine lokale JSON-API (`/api/voices`, `/api/run`)
- den Dateizugriff auf generierte Audios (`/storage/...`)

bereit.

## Empfohlener Start (Single Process)

```bash
cd /path/to/VSE
python3 local_ui_server.py --host 127.0.0.1 --port 5500
```

Dann öffnen: `http://127.0.0.1:5500`

## Voraussetzungen / Konfiguration

- Applio installiert (z. B. `/path/to/Applio`)
- Mindestens ein RVC-Modell unter `backend/models/rvc/<voice_id>/model.pth`
- Pfade in `backend/.env` (oder `.env.example`) prüfen:
  - `APPLIO_ROOT` (Applio-Projektpfad)
  - `APPLIO_PYTHON` (Python aus Applio-venv)
  - `APPLIO_TIMEOUT_SECONDS`
  - `RVC_MODEL_ROOT`
  - `STORAGE_ROOT`

## Ablauf

- Text-Modus: `text` -> Applio `tts` -> Voice Conversion -> WAV
- Audio-Modus: `audio` -> Applio `infer` -> WAV

Es gibt **kein LLM/STT/FastAPI** im aktuellen Runtime-Flow.

## Lokale API (intern für UI)

- `GET /api/voices`: listet verfügbare `voice_id`s
- `POST /api/run`: startet Text- oder Audio-Verarbeitung
  - Text-Request:
    - `voice_id`
    - `text`
    - optional `tts_voice`, `tts_rate`
  - Audio-Request:
    - `voice_id`
    - `audio_base64`
    - optional `audio_name`

## Schnelltest

1. Browser-Test:
   - Öffne `http://127.0.0.1:5500`
   - Wähle Voice
   - Text oder Audio eingeben
   - `Audio erzeugen`
2. API-Test:
```bash
curl http://127.0.0.1:5500/api/voices
```

## Stoppen

- Vordergrundprozess: `Ctrl+C`
- Hintergrundprozess (falls so gestartet): `pkill -f "local_ui_server.py --host 127.0.0.1 --port 5500"`
