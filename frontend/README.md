# VSE Frontend

Das Frontend ist statisch und wird von `local_ui_server.py` ausgeliefert.
Es spricht ausschließlich mit der lokalen API desselben Prozesses:
- `GET /api/voices`
- `POST /api/run`

## Start

```bash
cd /Users/fabianprimus/workspaces/codex/projects/VSE
python3 local_ui_server.py --host 127.0.0.1 --port 5500
```

Dann im Browser öffnen: `http://127.0.0.1:5500`

Hinweis: Start/Konfiguration ist zentral in der Root-Doku beschrieben: `README.md`.
