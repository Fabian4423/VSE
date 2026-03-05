# VSE Backend (MVP)

## Setup

```bash
cd /Users/fabianprimus/workspaces/codex/projects/VSE/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
cd /Users/fabianprimus/workspaces/codex/projects/VSE/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI: `http://127.0.0.1:8000/docs`

## Core Endpoints

- `GET /health`
- `GET /voices`
- `POST /voice/convert` (multipart: `audio_file`, `voice_id`)
- `POST /assistant/respond` (multipart: `voice_id`, optional `text` or `audio_file`)

## Voice Model Layout

```text
backend/models/rvc/<voice_id>/model.pth
backend/models/rvc/<voice_id>/model.index   (optional)
backend/models/xtts_speakers/<speaker_id>/reference.wav
```

`model.index` is optional. If missing, Applio is invoked with `--index_path "" --index_rate 0`.

