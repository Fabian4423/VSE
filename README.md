# VSE

Lokale TTS/STS Web-UI mit direkter Applio-CLI-Ansteuerung (ohne FastAPI im Laufzeitpfad).

## Empfohlener Start (Single Process)

```bash
cd /Users/fabianprimus/workspaces/codex/projects/VSE
python3 local_ui_server.py --host 127.0.0.1 --port 5500
```

Dann öffnen: `http://127.0.0.1:5500`

## Voraussetzungen

- Applio installiert (z. B. `/Users/fabianprimus/applio/Applio`)
- Pfade in `backend/.env` prüfen:
  - `APPLIO_ROOT`
  - `APPLIO_PYTHON`
  - `RVC_MODEL_ROOT`
  - `STORAGE_ROOT`

## Hinweis

Der lokale Runner nutzt Assets aus `backend/`:
- `backend/models/rvc` für Voice-Modelle
- `backend/storage` für Ein-/Ausgabe-Audio
- `backend/.env` für Pfad-Konfiguration
