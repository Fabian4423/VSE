# Backend Assets

Dieser Ordner enthält Runtime-Assets für den lokalen UI-Runner:
- `models/rvc/<voice_id>/...` für die Zielstimmen
- `storage/{input,intermediate,output}` für generierte Dateien
- `.env` für Pfade/Timeouts

## Voice Model Layout

```text
backend/models/rvc/<voice_id>/model.pth
backend/models/rvc/<voice_id>/model.index   (optional)
```

`model.index` ist optional. Fehlt der Index, läuft Applio mit `--index_path "" --index_rate 0`.

## Wichtige Env-Variablen

- `APPLIO_ROOT`
- `APPLIO_PYTHON`
- `APPLIO_TIMEOUT_SECONDS`
- `RVC_MODEL_ROOT`
- `STORAGE_ROOT`

Siehe Vorlage: `backend/.env.example`
