# VSE

Monorepo für Voice-Assistant-Backend (FastAPI + Applio) und ein MVP-Frontend.

## Backend starten

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Frontend starten

```bash
cd frontend
python3 -m http.server 5500
```

Dann öffnen: `http://127.0.0.1:5500`
