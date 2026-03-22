# Architekturdokumentation – VSE Text-to-Speech Web UI

> **Zweck dieses Dokuments:** Grundlage für den Architekturteil der wissenschaftlichen Projektarbeit. Enthält alle technischen Details, Designentscheidungen und Codebeispiele aus der Anwendung.

---

## 1. Architekturüberblick: CLI-Bridge-Ansatz

### Problemstellung

Die Applio TTS-Engine ist ein kommandozeilenbasiertes Werkzeug — die Zielgruppe sind jedoch Mitarbeitende ohne CLI-Erfahrung (vgl. Anforderung NF-01). Ein direkter Zugang zur CLI ist für diese Nutzergruppe nicht praktikabel.

### Lösungsansatz

Die Anwendung folgt einer **Client-Server-Architektur** mit einem leichtgewichtigen HTTP-Server als zentrale Vermittlungsschicht. Dieser Server fungiert als **Bridge** (Brücke) zwischen dem Webbrowser und der Applio-CLI. Er übersetzt HTTP-Requests in CLI-Aufrufe und liefert die Ergebnisse als Audiodateien zurück.

**Diagramm:** [01_system_architecture.svg](diagrams/01_system_architecture.svg)

### Drei logische Schichten

| Schicht | Komponente | Technologie | Aufgabe |
|---------|-----------|-------------|---------|
| **Präsentation** | Browser (Client) | HTML, CSS, Vanilla JavaScript | Benutzeroberfläche, Eingabe, Audio-Wiedergabe |
| **Vermittlung** | local_ui_server.py (Bridge) | Python `ThreadingHTTPServer` | Protokollübersetzung (JSON ↔ CLI), Dateiverwaltung, statisches Hosting |
| **Verarbeitung** | Applio CLI (Engine) | Python, PyTorch (GPU/CPU) | Text-to-Speech, Voice Conversion |

### Zentrale Designentscheidung

Der Bridge-Server führt **keine Audioverarbeitung** durch. Seine Aufgabe beschränkt sich auf:

1. **Protokollübersetzung** — HTTP-Requests in CLI-Aufrufe umwandeln
2. **Dateiverwaltung** — Ein-/Ausgabedateien mit UUID-basierten Pfaden verwalten
3. **Statisches Hosting** — Die Web-Oberfläche an den Browser ausliefern

---

## 2. Technologieentscheidungen

### Warum kein API-Framework (FastAPI, Flask)?

Pythons `ThreadingHTTPServer` aus der Standardbibliothek wurde bewusst gewählt:

- **Keine externen Abhängigkeiten** — Der Server benötigt nur eine Python-Installation und die bereits vorhandene Applio-Umgebung
- **Einfaches Deployment** — Kein `pip install`, keine virtuelle Umgebung für den Server selbst (vgl. Randbedingung C-02: lokaler Server)
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
├── local_ui_server.py              # Bridge-Server (Routing + Protokollübersetzung)
├── frontend/                       # Statische Web-Oberfläche
│   ├── index.html                  # HTML-Struktur
│   ├── app.js                      # Client-Logik (Vanilla JS)
│   └── styles.css                  # Styling
└── backend/
    ├── .env                        # Konfiguration (Pfade zur Applio-Installation)
    ├── models/
    │   └── rvc/<voice_id>/         # Stimmmodelle (dynamisch erweiterbar)
    │       ├── model.pth           # RVC-Modell (obligatorisch)
    │       └── model.index         # Feature-Index (optional, verbessert Qualität)
    └── storage/
        ├── input/                  # Hochgeladene Audiodateien
        ├── intermediate/           # TTS-Zwischenergebnis (vor Voice Conversion)
        └── output/                 # Finale Audiodateien (zum Download)
```

---

## 4. Konfigurationsmanagement

Alle konfigurierbaren Pfade werden aus einer `.env`-Datei geladen. Ein eigener Parser vermeidet externe Abhängigkeiten:

```python
# local_ui_server.py, Zeile 22–32
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()
```

**Konfigurierbare Parameter:**

| Variable | Beschreibung | Standardwert |
|----------|-------------|--------------|
| `APPLIO_ROOT` | Installationspfad der Applio-Engine | — |
| `APPLIO_PYTHON` | Python-Interpreter der Applio-Umgebung | — |
| `APPLIO_TIMEOUT_SECONDS` | Maximale Laufzeit eines TTS-Prozesses | 600 |
| `RVC_MODEL_ROOT` | Verzeichnis der Stimmmodelle | `backend/models/rvc` |
| `STORAGE_ROOT` | Verzeichnis für Ein-/Ausgabedateien | `backend/storage` |

Diese Konfiguration ermöglicht den Betrieb auf unterschiedlichen Servern ohne Codeänderung.

---

## 5. REST-API-Schnittstelle

Der Bridge-Server stellt drei Endpunkte bereit:

| Endpunkt | Methode | Funktion |
|----------|---------|----------|
| `/api/voices` | GET | Liefert verfügbare Stimmmodelle als JSON |
| `/api/run` | POST | Führt TTS und/oder Voice Conversion durch |
| `/storage/*` | GET | Liefert generierte Audiodateien aus |

### Endpunkt: Dynamische Modellermittlung (`GET /api/voices`)

Neue Stimmen werden automatisch erkannt, indem das Modellverzeichnis zur Laufzeit gescannt wird:

```python
# local_ui_server.py, Zeile 99–118
def _list_voices() -> list[dict]:
    if not RVC_MODEL_ROOT.exists():
        return []
    voices: list[dict] = []
    for entry in sorted(RVC_MODEL_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        model = _resolve_model_path(entry)
        index = _resolve_index_path(entry)
        voices.append({
            "voice_id": entry.name,
            "has_model": model is not None,
            "model_path": str(model) if model else None,
            "has_index": index is not None,
            "index_path": str(index) if index else None,
        })
    return voices
```

Das erfüllt die Anforderung **F-04 (Erweiterbarkeit)**: Ein neues Modell wird durch Ablegen eines Ordners mit `.pth`-Datei im Verzeichnis `backend/models/rvc/` registriert — ohne Code- oder Konfigurationsänderung.

### Endpunkt: Audiogenerierung (`POST /api/run`)

**Request-Format:**

```json
{
  "voice_id": "4",
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
  "voice_id": "4",
  "output_audio_url": "/storage/output/a1b2c3d4.wav",
  "metadata": {
    "input_mode": "text",
    "has_index": true
  }
}
```

### Endpunkt: Dateiauslieferung (`GET /storage/*`)

Der Endpunkt liefert generierte Audiodateien aus und enthält einen Path-Traversal-Schutz:

```python
# local_ui_server.py, Zeile 253–259
rel = path.removeprefix("/storage/").strip("/")
target = (STORAGE_ROOT / rel).resolve()
try:
    target.relative_to(STORAGE_ROOT)
except ValueError:
    _json_response(self, 403, {"detail": "Forbidden path."})
    return
```

Durch `resolve()` werden symbolische Links und `../`-Pfade aufgelöst. Der anschließende `relative_to()`-Check stellt sicher, dass der aufgelöste Pfad innerhalb von `STORAGE_ROOT` liegt. Anfragen außerhalb dieses Verzeichnisses werden mit HTTP 403 abgelehnt.

---

## 6. Verarbeitungspipeline

**Diagramm:** [02_processing_pipeline.svg](diagrams/02_processing_pipeline.svg)

Die Audiogenerierung durchläuft eine zweistufige Pipeline. Das System unterstützt zwei Eingabemodi:

### Text-Modus (Hauptanwendungsfall)

1. **Stufe 1 — Text-to-Speech:** Der eingegebene Text wird von einer Edge-TTS-Stimme (z.B. `de-DE-KatjaNeural`) in eine neutrale Audiodatei umgewandelt
2. **Stufe 2 — Voice Conversion:** Die neutrale Audiodatei wird mittels RVC (Retrieval-based Voice Conversion) in die gewählte Zielstimme konvertiert

### Audio-Modus

1. Stufe 1 entfällt — die hochgeladene Audiodatei dient direkt als Eingabe
2. **Stufe 2 — Voice Conversion:** Wie im Text-Modus

### Codebeispiel: TTS mit anschließender Voice Conversion

Dieses Codebeispiel zeigt den Kern der Bridge-Funktion — die Übersetzung von Funktionsparametern in CLI-Argumente:

```python
# local_ui_server.py, Zeile 188–233
def _applio_tts_and_infer(
    text: str, tts_voice: str, tts_rate: int,
    output_tts_path: Path, output_rvc_path: Path,
    pth_path: Path, index_path: Path | None,
) -> None:
    index_arg = str(index_path) if index_path and index_path.exists() else ""
    index_rate = "0.3" if index_arg else "0"
    cmd = [
        str(APPLIO_PYTHON), "core.py", "tts",
        "--tts_text",        text,
        "--tts_voice",       tts_voice,
        "--tts_rate",        str(tts_rate),
        "--output_tts_path", str(output_tts_path),
        "--output_rvc_path", str(output_rvc_path),
        "--pth_path",        str(pth_path),
        "--index_path",      index_arg,
        "--index_rate",      index_rate,
        "--f0_method",       "rmvpe",
        "--export_format",   "WAV",
        "--embedder_model",  "contentvec",
    ]
    _run_applio(cmd)
    _validate_output(output_rvc_path)
```

Der Aufruf entspricht dem, was ein Nutzer manuell im Terminal eingeben müsste — nur automatisiert und mit generierten Dateipfaden.

### Codebeispiel: Subprozess-Ausführung mit Fehlerbehandlung

```python
# local_ui_server.py, Zeile 137–152
def _run_applio(cmd: list[str]) -> None:
    shimmed_cmd = [cmd[0], "-c", _CORE_RUNNER_SHIM, *cmd[2:]]
    process = subprocess.run(
        shimmed_cmd,
        cwd=APPLIO_ROOT,
        capture_output=True,
        text=True,
        timeout=APPLIO_TIMEOUT_SECONDS,
    )
    if process.returncode != 0:
        stderr_tail = (process.stderr or "").strip()[-1200:]
        stdout_tail = (process.stdout or "").strip()[-1200:]
        raise RuntimeError(
            f"Applio failed (exit {process.returncode}). "
            f"stderr: {stderr_tail or '-'} stdout: {stdout_tail or '-'}"
        )
```

Relevante Aspekte:
- `capture_output=True` fängt stdout/stderr für Fehlerdiagnose ab
- `timeout=APPLIO_TIMEOUT_SECONDS` verhindert, dass hängende Prozesse den Server blockieren
- `cwd=APPLIO_ROOT` stellt sicher, dass Applio seine relativen Pfade korrekt auflöst
- Bei Fehlern werden die letzten 1200 Zeichen der Ausgabe in die Exception übernommen

---

## 7. Datenfluss: Request-Response-Zyklus

**Diagramm:** [03_request_response_flow.svg](diagrams/03_request_response_flow.svg)

Ein vollständiger Request im Text-Modus durchläuft folgende Schritte:

1. **Client** sendet `POST /api/run` mit Text und Voice-ID
2. **Bridge** validiert die Eingabe (voice_id vorhanden? Text nicht leer?)
3. **Bridge** löst Modellpfade auf: `rvc/<voice_id>/model.pth` + optional `model.index`
4. **Bridge** erzeugt UUID-Token → eindeutige Dateipfade (`intermediate/<uuid>.wav`, `output/<uuid>.wav`)
5. **Bridge** startet Applio als Subprozess: `python core.py tts --tts_text "..." ...`
6. **Applio** führt TTS + RVC aus, schreibt Ergebnis nach `output/<uuid>.wav`
7. **Bridge** prüft, ob die Ausgabedatei existiert und nicht leer ist
8. **Bridge** antwortet mit JSON inkl. `output_audio_url`
9. **Client** lädt Audio via `GET /storage/output/<uuid>.wav`

---

## 8. Dynamisches Modellmanagement

Das System erkennt neue Stimmmodelle automatisch nach dem **Convention-over-Configuration**-Prinzip. Es gibt keine zentrale Modellliste oder Konfigurationsdatei — die Verzeichnisstruktur ist die Konfiguration:

```
backend/models/rvc/
├── 4/                          # voice_id = "4" (existierend)
│   └── STS4_320e_11520s.pth
└── neue_stimme/                # voice_id = "neue_stimme" (neu hinzugefügt)
    └── model.pth               # → sofort verfügbar, kein Neustart nötig
```

Die Modellauflösung ist fehlertolerant — sie sucht erst nach der Konvention `model.pth`, fällt dann auf die erste `.pth`-Datei im Verzeichnis zurück:

```python
# local_ui_server.py, Zeile 83–88
def _resolve_model_path(voice_dir: Path) -> Path | None:
    default = voice_dir / "model.pth"
    if default.exists():
        return default
    pth_files = sorted(voice_dir.glob("*.pth"))
    return pth_files[0] if pth_files else None
```

Da `_list_voices()` das Verzeichnis bei **jedem Request** scannt, sind neue Modelle sofort verfügbar — ohne Neustart oder Konfigurationsänderung (vgl. Anforderung F-04).

---

## 9. Sicherheitskonzept

Gemäß den Anforderungen (NF-03, C-01, C-03) setzt die Anwendung auf **Netzwerk-Restriktion** statt Authentifizierung:

| Maßnahme | Beschreibung |
|----------|-------------|
| **Bindung auf localhost** | Server bindet standardmäßig auf `127.0.0.1` — nur lokal erreichbar |
| **VPN-Pflicht** | Externer Zugriff nur über VPN (Infrastruktur-Ebene, nicht App-Ebene) |
| **Path-Traversal-Schutz** | Dateizugriffe werden gegen `STORAGE_ROOT` validiert (siehe Abschnitt 5) |
| **Prozessisolation** | Applio läuft in eigenem Subprozess mit Timeout |
| **Keine Secrets im Code** | Pfade und Konfiguration über `.env`-Datei (nicht im Repository) |

Ein explizites Authentifizierungssystem wurde bewusst nicht implementiert, da der Zugriff bereits auf Netzwerkebene eingeschränkt ist (internes Netz + VPN). Dies entspricht der Anforderung NF-03.

---

## 10. Anforderungsabdeckung

| ID | Anforderung | Status | Umsetzung |
|----|------------|--------|-----------|
| **F-01** | Text-zu-Audio-Generierung | Erfüllt | `POST /api/run` → Applio TTS + RVC → WAV |
| **F-02** | Modellauswahl | Erfüllt | `GET /api/voices` scannt Modellverzeichnis dynamisch |
| **F-03** | Download der Tondatei | Erfüllt | `GET /storage/*` liefert WAV-Dateien aus |
| **F-04** | Erweiterbarkeit für neue Modelle | Erfüllt | Convention-over-Configuration, kein Neustart nötig |
| **NF-01** | Usability | Erfüllt | Weboberfläche mit selbsterklärender Bedienung |
| **NF-02** | Performance / Feedback | Teilweise | Button-Disable während Generierung, kein Spinner |
| **NF-03** | Zugriffsbeschränkung | Erfüllt | Localhost-Bindung + VPN + Path-Traversal-Schutz |
| **NF-04** | Skalierbarkeit | Grundlegend | ThreadingHTTPServer für parallele Requests |
| **C-01** | Internes Netzwerk | Erfüllt | Kein externer Zugang |
| **C-02** | Lokaler Server | Erfüllt | Keine Cloud-Abhängigkeiten, keine ext. Python-Pakete |
| **C-03** | VPN-Pflicht | Erfüllt | Infrastruktur-seitig umgesetzt |

---

## Diagrammverzeichnis

| Datei | Beschreibung |
|-------|-------------|
| [diagrams/01_system_architecture.svg](diagrams/01_system_architecture.svg) | Systemarchitektur mit den drei Schichten (Client, Bridge, Engine) |
| [diagrams/02_processing_pipeline.svg](diagrams/02_processing_pipeline.svg) | Verarbeitungspipeline: Text-Modus vs. Audio-Modus |
| [diagrams/03_request_response_flow.svg](diagrams/03_request_response_flow.svg) | Sequenzdiagramm: Request-Response-Zyklus im Text-Modus |
