# Backend Assets

Dieser Ordner enthält nur noch Runtime-Assets für den lokalen UI-Runner:
- `models/rvc/<voice_id>/...` für die Zielstimmen
- `storage/{input,intermediate,output}` für generierte Dateien
- `.env` für Pfade/Timeouts

## Voice Model Layout

```text
backend/models/rvc/<voice_id>/model.pth
backend/models/rvc/<voice_id>/model.index   (optional)
```

`model.index` is optional. If missing, Applio is invoked with `--index_path "" --index_rate 0`.
