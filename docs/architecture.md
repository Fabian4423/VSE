# Architekturdokumentation – VSE Text-to-Speech Web UI

> **Zweck dieses Dokuments:** Grundlage für den Architekturteil der wissenschaftlichen Projektarbeit. Enthält alle technischen Details, Designentscheidungen und Codebeispiele aus der Anwendung.

---

## 1. Architekturüberblick: Zweistufige CLI-Bridge

### Problemstellung

Die Applio TTS-Engine ist ein kommandozeilenbasiertes Werkzeug — die Zielgruppe sind jedoch Mitarbeitende ohne CLI-Erfahrung (vgl. Anforderung NF-01). Ein direkter Zugang zur CLI ist für diese Nutzergruppe nicht praktikabel.

Zusätzlich erfordert die Engine GPU-Zugriff. Die VM, auf der der Webserver läuft, hat keinen direkten GPU-Zugang — Applio muss auf dem Host-System ausgeführt werden.

### Lösungsansatz

Die Anwendung folgt einer **zweistufigen Client-Server-Architektur**. Zwei HTTP-Server bilden zusammen die Bridge zwischen Browser und Applio-CLI:

1. **`applio_runner.py`** läuft auf dem **Host-System** mit GPU-Zugriff und kapselt alle CLI-Aufrufe an Applio
2. **`local_ui_server.py`** läuft auf der **VM**, stellt die Weboberfläche bereit und leitet API-Anfragen an den Runner weiter

**Diagramm:** [01_system_architecture.svg](diagrams/01_system_architecture.svg)

### Vier logische Schichten

| Schicht | Komponente | System | Technologie | Aufgabe |
|---------|-----------|--------|-------------|---------|
| **Präsentation** | Browser (Client) | Beliebig | HTML, CSS, Vanilla JavaScript | Benutzeroberfläche, Eingabe, Audio-Wiedergabe |
| **Vermittlung** | local_ui_server.py | VM | Python `ThreadingHTTPServer` | Frontend-Hosting, API-Proxy zum Runner |
| **Ausführung** | applio_runner.py | Host | Python `ThreadingHTTPServer` | Protokollübersetzung (JSON ↔ CLI), Dateiverwaltung |
| **Verarbeitung** | Applio CLI | Host | Python, PyTorch (GPU) | Text-to-Speech, Voice Conversion |

### Zentrale Designentscheidung

Beide Server führen **keine Audioverarbeitung** durch. Die Aufgabentrennung ist klar:

- **`local_ui_server.py`** — Frontend ausliefern, Requests entgegennehmen, an Runner weiterleiten
- **`applio_runner.py`** — CLI-Argumente aufbauen, Subprozesse starten, Ergebnisse als Base64 zurückgeben
- **Applio CLI** — alle GPU-intensive Arbeit

---

## 2. Technologieentscheidungen

### Warum zwei separate Server statt einem?

Die Trennung in `local_ui_server.py` (VM) und `applio_runner.py` (Host) ermöglicht:

- **GPU-Isolation** — Applio läuft dort wo die GPU ist (Host), der Webserver läuft auf der VM ohne GPU-Anforderung
- **Unabhängige Skalierbarkeit** — Runner und UI-Server können unabhängig voneinander neu gestartet oder skaliert werden
- **Klar definierte Schnittstelle** — Die HTTP-API zwischen VM und Host ist explizit und versionierbar

### Warum kein API-Framework (FastAPI, Flask)?

Pythons `ThreadingHTTPServer` aus der Standardbibliothek wurde für beide Server bewusst gewählt:

- **Keine externen Abhängigkeiten** — Beide Server benötigen nur eine Standard-Python-Installation
- **Einfaches Deployment** — Kein `pip install`, keine virtuelle Umgebung für die Server selbst
- **Ausreichend für den Anwendungsfall** — Wenige Endpunkte, geringe gleichzeitige Nutzerzahl im internen Netzwerk

### Warum Vanilla JavaScript (kein React/Vue)?

- Minimale Komplexität für eine Oberfläche mit wenigen Interaktionselementen
- Kein Build-Prozess nötig — statische Dateien werden direkt vom Server ausgeliefert
- Reduziert die Infrastrukturanforderungen auf dem lokalen Server

### Warum Subprozesse statt direkter Python-Integration?

Die Applio-Engine wird per `subprocess.run()` als eigener Betriebssystemprozess gestartet statt als Python-Modul importiert:

- **Fehlertoleranz** — Ein Absturz der TTS-Engine beendet nicht den Server
- **Timeout-Kontrolle** — Hängende Prozesse werden nach konfigurierbarer Zeit abgebrochen
- **Entkopplung** — Applio kann unabhängig vom Server aktualisiert werden
- **Ressourcentrennung** — GPU-/CPU-intensive Arbeit läuft isoliert

---

## 3. Verzeichnisstruktur

```
VSE/
├── local_ui_server.py              # UI-Server (VM): Frontend-Hosting + API-Proxy
├── applio_runner.py                # Runner (Host): CLI-Bridge zu Applio
├── runner.env                      # Konfiguration des Runners (nicht im Repository)
├── frontend/                       # Statische Web-Oberfläche
│   ├── index.html                  # HTML-Struktur
│   ├── app.js                      # Client-Logik (Vanilla JS)
│   └── styles.css                  # Styling
└── backend/
    ├── .env                        # Konfiguration des UI-Servers (Runner-URL etc.)
    ├── models/
    │   └── rvc/<voice_id>/         # Stimmmodelle (auf dem Host, vom Runner gelesen)
    │       ├── model.pth           # RVC-Modell (obligatorisch)
    │       └── model.index         # Feature-Index (optional, verbessert Qualität)
    └── storage/
        └── output/                 # Finale Audiodateien (zum Download, auf der VM)
```

---

## 4. Konfigurationsmanagement

Das System verwendet zwei getrennte Konfigurationsdateien — eine pro Server. Beide nutzen denselben einfachen `.env`-Parser ohne externe Abhängigkeiten:

```python
# applio_runner.py / local_ui_server.py
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()
```

### `runner.env` — Konfiguration des Host-Runners

| Variable | Beschreibung | Beispiel |
|----------|-------------|---------|
| `APPLIO_ROOT` | Installationspfad der Applio-Engine | `/home/user/Applio` |
| `APPLIO_PYTHON` | Python-Interpreter der Applio-Umgebung | `/home/user/Applio/.venv/bin/python` |
| `APPLIO_TIMEOUT_SECONDS` | Maximale Laufzeit eines TTS-Prozesses | `600` |
| `RVC_MODEL_ROOT` | Verzeichnis der Stimmmodelle | `/pfad/zu/models/rvc` |
| `RUNNER_PORT` | Port des Runners | `5600` |

### `backend/.env` — Konfiguration des VM-UI-Servers

| Variable | Beschreibung | Standardwert |
|----------|-------------|--------------|
| `APPLIO_RUNNER_URL` | URL des Runners auf dem Host | `http://192.168.100.64:5600` |
| `STORAGE_ROOT` | Verzeichnis für Ausgabedateien | `backend/storage` |

---

## 5. REST-API-Schnittstelle

Das System stellt zwei HTTP-APIs bereit — eine auf der VM (öffentlich zugänglich), eine auf dem Host (intern).

### VM: `local_ui_server.py` (Port 5500)

| Endpunkt | Methode | Funktion |
|----------|---------|----------|
| `/api/voices` | GET | Liefert verfügbare Stimmmodelle (proxied vom Runner) |
| `/api/run` | POST | Startet TTS oder Voice Conversion (proxied zum Runner) |
| `/storage/*` | GET | Liefert generierte Audiodateien aus |

### Host: `applio_runner.py` (Port 5600)

| Endpunkt | Methode | Funktion |
|----------|---------|----------|
| `/health` | GET | Statusabfrage |
| `/voices` | GET | Scannt Modellverzeichnis und gibt Modell-Liste zurück |
| `/tts` | POST | Text → TTS → Voice Conversion → WAV (Base64) |
| `/infer` | POST | Audio (Base64) → Voice Conversion → WAV (Base64) |

### Endpunkt: Dynamische Modellermittlung

Der Runner scannt das Modellverzeichnis bei jedem Request. `local_ui_server.py` leitet die Anfrage transparent weiter:

```python
# local_ui_server.py
def _list_voices() -> list[dict]:
    try:
        return _runner_get("/voices").get("voices", [])
    except Exception:
        return []
```

```python
# applio_runner.py
def _list_voices() -> list[dict]:
    if not MODEL_ROOT.exists():
        return []
    voices = []
    for d in sorted(MODEL_ROOT.iterdir()):
        if not d.is_dir():
            continue
        pth = next(iter(sorted(d.glob("*.pth"))), None)
        idx = next(iter(sorted(d.glob("*.index"))), None)
        voices.append({
            "voice_id": d.name,
            "has_model": pth is not None,
            "has_index": idx is not None,
        })
    return voices
```

Das erfüllt die Anforderung **F-04 (Erweiterbarkeit)**: Ein neues Modell wird durch Ablegen eines Ordners mit `.pth`-Datei im Modellverzeichnis registriert — ohne Code- oder Konfigurationsänderung.

### Endpunkt: Audiogenerierung (`POST /api/run`)

**Request-Format:**

```json
{
  "voice_id": "MeineStimme",
  "text": "Hallo, dies ist ein Test.",
  "tts_voice": "de-DE-KatjaNeural",
  "tts_rate": 0
}
```

**Response-Format:**

```json
{
  "input_text": "Hallo, dies ist ein Test.",
  "response_text": "Hallo, dies ist ein Test.",
  "voice_id": "MeineStimme",
  "output_audio_url": "/storage/output/a1b2c3d4.wav",
  "output_audio_path": "/absoluter/pfad/output/a1b2c3d4.wav",
  "metadata": {"input_mode": "text"}
}
```

### Endpunkt: Dateiauslieferung (`GET /storage/*`)

Der Endpunkt liefert generierte Audiodateien aus und enthält einen Path-Traversal-Schutz:

```python
# local_ui_server.py
rel = path.removeprefix("/storage/").strip("/")
target = (STORAGE_ROOT / rel).resolve()
try:
    target.relative_to(STORAGE_ROOT)
except ValueError:
    _json_response(self, 403, {"detail": "Forbidden path."})
    return
```

Durch `resolve()` werden symbolische Links und `../`-Pfade aufgelöst. Der `relative_to()`-Check stellt sicher, dass der aufgelöste Pfad innerhalb von `STORAGE_ROOT` liegt.

---

## 6. Verarbeitungspipeline

**Diagramm:** [02_processing_pipeline.svg](diagrams/02_processing_pipeline.svg)

Die Audiogenerierung durchläuft eine zweistufige Pipeline auf dem Host-System. Das System unterstützt zwei Eingabemodi:

### Text-Modus (Hauptanwendungsfall)

1. **Stufe 1 — Text-to-Speech:** Der eingegebene Text wird von einer Edge-TTS-Stimme (z.B. `de-DE-KatjaNeural`) in eine neutrale Audiodatei umgewandelt
2. **Stufe 2 — Voice Conversion:** Die neutrale Audiodatei wird mittels RVC (Retrieval-based Voice Conversion) in die gewählte Zielstimme konvertiert

### Audio-Modus

1. Stufe 1 entfällt — die hochgeladene Audiodatei dient direkt als Eingabe
2. **Stufe 2 — Voice Conversion:** Wie im Text-Modus

### Codebeispiel: TTS mit anschließender Voice Conversion (Runner)

```python
# applio_runner.py
def _do_tts(text: str, tts_voice: str, tts_rate: int, voice_id: str) -> bytes:
    pth, idx = _resolve_model(voice_id)
    idx_arg = str(idx) if idx else ""
    with tempfile.TemporaryDirectory() as tmp:
        tts_out = Path(tmp) / "tts.wav"
        rvc_out = Path(tmp) / "rvc.wav"
        _run_applio([
            str(APPLIO_PYTHON), "core.py", "tts",
            "--tts_text",        text,
            "--tts_voice",       tts_voice,
            "--tts_rate",        str(tts_rate),
            "--output_tts_path", str(tts_out),
            "--output_rvc_path", str(rvc_out),
            "--pth_path",        str(pth),
            "--index_path",      idx_arg,
            "--index_rate",      "0.3" if idx_arg else "0",
            "--f0_method",       "rmvpe",
            "--export_format",   "WAV",
            "--embedder_model",  "contentvec",
        ])
        return rvc_out.read_bytes()
```

### Codebeispiel: Subprozess-Ausführung mit Fehlerbehandlung

```python
# applio_runner.py
def _run_applio(cmd: list[str]) -> None:
    shimmed = [cmd[0], "-c", _CORE_RUNNER_SHIM, *cmd[2:]]
    proc = subprocess.run(
        shimmed,
        cwd=APPLIO_ROOT,
        capture_output=True,
        text=True,
        timeout=APPLIO_TIMEOUT,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1200:]
        raise RuntimeError(f"Applio failed (exit {proc.returncode}): {tail}")
```

Relevante Aspekte:
- `capture_output=True` fängt stdout/stderr für Fehlerdiagnose ab
- `timeout=APPLIO_TIMEOUT` verhindert, dass hängende Prozesse den Server blockieren
- `cwd=APPLIO_ROOT` stellt sicher, dass Applio seine relativen Pfade korrekt auflöst
- Der `_CORE_RUNNER_SHIM` umgeht ein Kompatibilitätsproblem mit `distutils` in Python 3.12+

---

## 7. Datenfluss: Request-Response-Zyklus

**Diagramm:** [03_request_response_flow.svg](diagrams/03_request_response_flow.svg)

Ein vollständiger Request im Text-Modus durchläuft folgende Schritte:

1. **Client** sendet `POST /api/run` mit Text und Voice-ID an `local_ui_server.py` (VM)
2. **UI-Server** validiert Eingabe (voice_id vorhanden? Text nicht leer?)
3. **UI-Server** leitet Request als `POST /tts` an `applio_runner.py` (Host) weiter
4. **Runner** löst Modellpfade auf: `rvc/<voice_id>/*.pth` + optional `*.index`
5. **Runner** erstellt temporäres Verzeichnis, startet Applio als Subprozess
6. **Applio** führt TTS + RVC aus, schreibt Ergebnis in temporäre Datei
7. **Runner** liest Ergebnis, kodiert als Base64, sendet JSON-Response
8. **UI-Server** dekodiert Base64, speichert WAV unter UUID-Dateinamen in `storage/output/`
9. **UI-Server** antwortet mit JSON inkl. `output_audio_url`
10. **Client** lädt Audio via `GET /storage/output/<uuid>.wav`

Der Audiodatenstrom zwischen Runner und UI-Server läuft als **Base64-kodierter JSON-Payload** über HTTP. Dies vermeidet geteilte Dateisysteme zwischen Host und VM.

---

## 8. Dynamisches Modellmanagement

Das System erkennt neue Stimmmodelle automatisch nach dem **Convention-over-Configuration**-Prinzip. Es gibt keine zentrale Modellliste — die Verzeichnisstruktur ist die Konfiguration:

```
backend/models/rvc/
├── MeineStimme/                # voice_id = "MeineStimme"
│   ├── MeineStimme.pth         # → erste .pth-Datei wird verwendet
│   └── MeineStimme.index       # → optional, verbessert Qualität
└── neue_stimme/                # sofort verfügbar nach Ablegen, kein Neustart nötig
    └── model.pth
```

Da der Runner das Verzeichnis bei **jedem Request** scannt, sind neue Modelle sofort verfügbar — ohne Neustart oder Konfigurationsänderung (vgl. Anforderung F-04).

---

## 9. Sicherheitskonzept

Gemäß den Anforderungen (NF-03, C-01, C-03) setzt die Anwendung auf **Netzwerk-Restriktion** statt Authentifizierung:

| Maßnahme | Beschreibung |
|----------|-------------|
| **UI-Server auf localhost** | `local_ui_server.py` bindet standardmäßig auf `127.0.0.1` — nur lokal auf der VM erreichbar |
| **Runner intern** | `applio_runner.py` ist nur im internen Host-Netzwerk erreichbar, nicht von außen |
| **VPN-Pflicht** | Externer Zugriff nur über VPN (Infrastruktur-Ebene, nicht App-Ebene) |
| **Path-Traversal-Schutz** | Dateizugriffe werden gegen `STORAGE_ROOT` validiert (siehe Abschnitt 5) |
| **Prozessisolation** | Applio läuft in eigenem Subprozess mit Timeout |
| **Keine Secrets im Code** | Pfade und Konfiguration über `.env`/`runner.env` (nicht im Repository) |

---

## 10. Anforderungsabdeckung

| ID | Anforderung | Status | Umsetzung |
|----|------------|--------|-----------|
| **F-01** | Text-zu-Audio-Generierung | Erfüllt | `POST /api/run` → Runner `/tts` → Applio TTS + RVC → WAV |
| **F-02** | Modellauswahl | Erfüllt | `GET /api/voices` proxied Runner `/voices`, scannt Verzeichnis dynamisch |
| **F-03** | Download der Tondatei | Erfüllt | `GET /storage/*` liefert WAV-Dateien aus |
| **F-04** | Erweiterbarkeit für neue Modelle | Erfüllt | Convention-over-Configuration, kein Neustart nötig |
| **NF-01** | Usability | Erfüllt | Weboberfläche mit selbsterklärender Bedienung |
| **NF-02** | Performance / Feedback | Teilweise | Button-Disable während Generierung, kein Spinner |
| **NF-03** | Zugriffsbeschränkung | Erfüllt | Localhost-Bindung + VPN + Path-Traversal-Schutz |
| **NF-04** | Skalierbarkeit | Grundlegend | ThreadingHTTPServer für parallele Requests auf beiden Servern |
| **C-01** | Internes Netzwerk | Erfüllt | Kein externer Zugang |
| **C-02** | Lokaler Server | Erfüllt | Keine Cloud-Abhängigkeiten, keine externen Python-Pakete |
| **C-03** | VPN-Pflicht | Erfüllt | Infrastruktur-seitig umgesetzt |

---

## Diagrammverzeichnis

| Datei | Beschreibung |
|-------|-------------|
| [diagrams/01_system_architecture.svg](diagrams/01_system_architecture.svg) | Systemarchitektur mit den vier Schichten (Client, UI-Server, Runner, Engine) |
| [diagrams/02_processing_pipeline.svg](diagrams/02_processing_pipeline.svg) | Verarbeitungspipeline: Text-Modus vs. Audio-Modus |
| [diagrams/03_request_response_flow.svg](diagrams/03_request_response_flow.svg) | Sequenzdiagramm: Request-Response-Zyklus im Text-Modus |
