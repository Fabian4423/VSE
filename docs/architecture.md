# Architekturdokumentation – VSE Text-to-Speech Web UI

> **Zweck dieses Dokuments:** Grundlage für den Architekturteil der wissenschaftlichen Projektarbeit. Enthält alle technischen Details, Designentscheidungen und Codebeispiele aus der Anwendung.

---

## 1. Architekturüberblick: Proxy-Architektur mit Chatterbox TTS

### Problemstellung

Die Zielgruppe sind Mitarbeitende ohne CLI-Erfahrung (vgl. Anforderung NF-01). Ein direkter Zugang zur TTS-API ist für diese Nutzergruppe nicht praktikabel.

Der Chatterbox TTS-Service läuft auf dem Host-System mit GPU-Zugriff. Die VM, auf der der Webserver läuft, hat keinen direkten GPU-Zugang — die TTS-Verarbeitung muss auf dem Host-System erfolgen.

### Lösungsansatz

Die Anwendung folgt einer **Client-Server-Proxy-Architektur**. Der UI-Server auf der VM dient als Vermittler zwischen Browser und Chatterbox TTS-Service:

1. **`local_ui_server.py`** läuft auf der **VM**, stellt die Weboberfläche bereit und leitet TTS-Anfragen an den Chatterbox-Service weiter
2. **Chatterbox TTS** läuft auf dem **Host-System** mit GPU-Zugriff und erzeugt die Sprachausgabe

**Diagramm:** [01_system_architecture.svg](diagrams/01_system_architecture.svg)

### Drei logische Schichten

| Schicht | Komponente | System | Technologie | Aufgabe |
|---------|-----------|--------|-------------|---------|
| **Präsentation** | Browser (Client) | Beliebig | HTML, CSS, Vanilla JavaScript | Benutzeroberfläche, Eingabe, Audio-Wiedergabe |
| **Vermittlung** | local_ui_server.py | VM | Python `ThreadingHTTPServer` | Frontend-Hosting, API-Proxy zu Chatterbox |
| **Verarbeitung** | Chatterbox TTS | Host | Python, GPU | Text-to-Speech mit vordefinierten Stimmen |

### Zentrale Designentscheidung

Der UI-Server führt **keine Audioverarbeitung** durch. Die Aufgabentrennung ist klar:

- **`local_ui_server.py`** — Frontend ausliefern, Requests entgegennehmen, an Chatterbox weiterleiten, Audio-Ergebnisse speichern
- **Chatterbox TTS** — Text-to-Speech-Generierung mit GPU-Beschleunigung

---

## 2. Technologieentscheidungen

### Warum ein separater UI-Server statt direktem API-Zugriff?

Die Trennung in `local_ui_server.py` (VM) und Chatterbox TTS (Host) ermöglicht:

- **GPU-Isolation** — Chatterbox läuft dort wo die GPU ist (Host), der Webserver läuft auf der VM ohne GPU-Anforderung
- **Entkopplung** — Der Chatterbox-Service kann unabhängig aktualisiert oder neu gestartet werden
- **Klar definierte Schnittstelle** — Die HTTP-API zwischen VM und Host ist explizit
- **Dateimanagement** — Generierte Audiodateien werden lokal auf der VM gespeichert und zum Download bereitgestellt

### Warum kein API-Framework (FastAPI, Flask)?

Pythons `ThreadingHTTPServer` aus der Standardbibliothek wurde bewusst gewählt:

- **Keine externen Abhängigkeiten** — Der UI-Server benötigt nur eine Standard-Python-Installation
- **Einfaches Deployment** — Kein `pip install`, keine virtuelle Umgebung
- **Ausreichend für den Anwendungsfall** — Wenige Endpunkte, geringe gleichzeitige Nutzerzahl im internen Netzwerk

### Warum Vanilla JavaScript (kein React/Vue)?

- Minimale Komplexität für eine Oberfläche mit wenigen Interaktionselementen
- Kein Build-Prozess nötig — statische Dateien werden direkt vom Server ausgeliefert
- Reduziert die Infrastrukturanforderungen auf dem lokalen Server

### Warum vordefinierte Stimmen statt eigener Modelle?

Chatterbox TTS bietet 28 vordefinierte Stimmen unterschiedlicher Charakteristik. Diese Entscheidung hat folgende Vorteile:

- **Kein Modell-Management** — Keine `.pth`- oder `.index`-Dateien, kein Modellverzeichnis
- **Sofort einsatzbereit** — Stimmen sind Teil des Chatterbox-Service
- **Konsistente Qualität** — Vordefinierte Stimmen sind getestet und optimiert

---

## 3. Verzeichnisstruktur

```
VSE/
├── local_ui_server.py              # UI-Server (VM): Frontend-Hosting + API-Proxy
├── frontend/                       # Statische Web-Oberfläche
│   ├── index.html                  # HTML-Struktur
│   ├── app.js                      # Client-Logik (Vanilla JS)
│   └── styles.css                  # Styling
└── backend/
    ├── .env                        # Konfiguration des UI-Servers (Chatterbox-URL etc.)
    └── storage/
        └── output/                 # Finale Audiodateien (zum Download, auf der VM)
```

---

## 4. Konfigurationsmanagement

Das System verwendet eine Konfigurationsdatei auf der VM. Der einfache `.env`-Parser kommt ohne externe Abhängigkeiten aus:

```python
# local_ui_server.py
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

### `backend/.env` — Konfiguration des VM-UI-Servers

| Variable | Beschreibung | Standardwert |
|----------|-------------|--------------|
| `CHATTERBOX_URL` | URL des Chatterbox TTS-Service auf dem Host | `http://192.168.100.64:8004` |
| `STORAGE_ROOT` | Verzeichnis für Ausgabedateien | `backend/storage` |

---

## 5. REST-API-Schnittstelle

Das System stellt zwei HTTP-APIs bereit — eine auf der VM (öffentlich zugänglich), eine auf dem Host (intern).

### VM: `local_ui_server.py` (Port 5174)

| Endpunkt | Methode | Funktion |
|----------|---------|----------|
| `/api/voices` | GET | Liefert die 28 verfügbaren Chatterbox-Stimmen |
| `/api/run` | POST | Startet TTS-Generierung via Chatterbox |
| `/storage/*` | GET | Liefert generierte Audiodateien aus |

### Host: Chatterbox TTS (Port 8004)

| Endpunkt | Methode | Funktion |
|----------|---------|----------|
| `/get_predefined_voices` | GET | Liefert die Liste verfügbarer vordefinierter Stimmen |
| `/tts` | POST | Text → WAV-Audiodatei (binary) |

### Endpunkt: Verfügbare Stimmen

Die verfügbaren Stimmen werden **dynamisch vom Chatterbox TTS-Service** abgefragt (`GET /get_predefined_voices`). Wird eine neue Stimme im Chatterbox-Service hinzugefügt, erscheint sie automatisch in der UI — ohne Anpassung des UI-Servers.

Falls Chatterbox nicht erreichbar ist, greift der UI-Server auf eine statische Fallback-Liste zurück:

```python
# local_ui_server.py
def _fetch_chatterbox_voices() -> list[str] | None:
    """Fetch predefined voices from Chatterbox TTS. Returns None on failure."""
    try:
        req = _urllib_req.Request(f"{CHATTERBOX_URL}/get_predefined_voices")
        with _urllib_req.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ...
        return voices or None
    except Exception:
        return None

CHATTERBOX_VOICES_FALLBACK = [
    "Abigail", "Adrian", "Alexander", "Alice", "Austin", "Axel",
    "Connor", "Cora", "Elena", "Eli", "Emily", "Everett",
    "Gabriel", "Gianna", "Henry", "Ian", "Jade", "Jeremiah",
    "Jordan", "Julian", "Layla", "Leonardo", "Michael", "Miles",
    "Olivia", "Ryan", "Taylor", "Thomas",
]
```

### Endpunkt: Audiogenerierung (`POST /api/run`)

**Request-Format:**

```json
{
  "voice_id": "Alexander",
  "text": "Hallo, dies ist ein Test."
}
```

**Response-Format:**

```json
{
  "input_text": "Hallo, dies ist ein Test.",
  "response_text": "Hallo, dies ist ein Test.",
  "voice_id": "Alexander",
  "output_audio_url": "/storage/output/a1b2c3d4.wav",
  "output_audio_path": "/absoluter/pfad/output/a1b2c3d4.wav",
  "metadata": {"input_mode": "text"}
}
```

### Chatterbox TTS API (`POST /tts`)

Der UI-Server sendet folgendes Format an den Chatterbox-Service:

```json
{
  "text": "Hallo, dies ist ein Test.",
  "voice_mode": "predefined",
  "predefined_voice_id": "Alexander.wav"
}
```

Die Antwort ist eine **binäre WAV-Datei** (kein JSON). Der UI-Server speichert diese direkt als Datei.

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

Die Audiogenerierung erfolgt in einer einstufigen Pipeline:

1. **Texteingabe** — Der Nutzer gibt Text ein und wählt eine der 28 vordefinierten Stimmen
2. **Weiterleitung** — Der UI-Server leitet den Text und die Stimmenauswahl an den Chatterbox TTS-Service weiter
3. **Text-to-Speech** — Chatterbox generiert die Sprachausgabe als WAV-Datei
4. **Speicherung** — Der UI-Server speichert die WAV-Datei lokal unter einem UUID-Dateinamen
5. **Wiedergabe/Download** — Der Browser lädt die Datei und bietet Wiedergabe und Download an

### Codebeispiel: TTS-Aufruf an Chatterbox

```python
# local_ui_server.py
def _chatterbox_tts(text: str, voice_id: str) -> bytes:
    payload = json.dumps({
        "text": text,
        "voice_mode": "predefined",
        "predefined_voice_id": f"{voice_id}.wav",
    }).encode("utf-8")
    req = _urllib_req.Request(
        f"{CHATTERBOX_URL}/tts",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urllib_req.urlopen(req, timeout=120) as resp:
        return resp.read()
```

Im Vergleich zur früheren Architektur entfällt die CLI-Bridge: Chatterbox TTS ist ein eigenständiger HTTP-Service, der direkt angesprochen wird — ohne Subprozesse, temporäre Dateien oder Base64-Kodierung.

---

## 7. Datenfluss: Request-Response-Zyklus

**Diagramm:** [03_request_response_flow.svg](diagrams/03_request_response_flow.svg)

Ein vollständiger Request durchläuft folgende Schritte:

1. **Client** sendet `POST /api/run` mit Text und Voice-ID an `local_ui_server.py` (VM)
2. **UI-Server** validiert Eingabe (voice_id gültig? Text nicht leer?)
3. **UI-Server** leitet Request als `POST /tts` an Chatterbox TTS (Host) weiter
4. **Chatterbox** generiert Sprachausgabe und gibt binäre WAV-Datei zurück
5. **UI-Server** speichert WAV unter UUID-Dateinamen in `storage/output/`
6. **UI-Server** antwortet mit JSON inkl. `output_audio_url`
7. **Client** lädt Audio via `GET /storage/output/<uuid>.wav`

Der Audiodatenstrom zwischen Chatterbox und UI-Server läuft als **binäre WAV-Daten** über HTTP — kein Base64-Overhead, kein geteiltes Dateisystem.

---

## 8. Stimmenverwaltung

Das System fragt die verfügbaren Stimmen **dynamisch** vom Chatterbox TTS-Service ab (`GET /get_predefined_voices`). Wird eine neue Stimme im Chatterbox-Service registriert, erscheint sie beim nächsten Laden der Seite automatisch im Frontend — ohne Änderung am UI-Server.

Als Fallback enthält der UI-Server eine statische Liste mit 28 Stimmen (Abigail, Adrian, Alexander, …), die genutzt wird, wenn der Chatterbox-Service nicht erreichbar ist.

---

## 9. Sicherheitskonzept

Gemäß den Anforderungen (NF-03, C-01, C-03) setzt die Anwendung auf **Netzwerk-Restriktion** statt Authentifizierung:

| Maßnahme | Beschreibung |
|----------|-------------|
| **UI-Server auf localhost** | `local_ui_server.py` bindet standardmäßig auf `127.0.0.1` — nur lokal auf der VM erreichbar |
| **Chatterbox intern** | Chatterbox TTS ist nur im internen Host-Netzwerk erreichbar, nicht von außen |
| **VPN-Pflicht** | Externer Zugriff nur über VPN (Infrastruktur-Ebene, nicht App-Ebene) |
| **Path-Traversal-Schutz** | Dateizugriffe werden gegen `STORAGE_ROOT` validiert (siehe Abschnitt 5) |
| **Eingabevalidierung** | Voice-ID wird gegen die Liste gültiger Stimmen geprüft |
| **Keine Secrets im Code** | Konfiguration über `.env` (nicht im Repository) |

---

## 10. Anforderungsabdeckung

| ID | Anforderung | Status | Umsetzung |
|----|------------|--------|-----------|
| **F-01** | Text-zu-Audio-Generierung | Erfüllt | `POST /api/run` → Chatterbox `/tts` → WAV |
| **F-02** | Stimmauswahl | Erfüllt | 28 vordefinierte Chatterbox-Stimmen über `/api/voices` |
| **F-03** | Download der Tondatei | Erfüllt | `GET /storage/*` liefert WAV-Dateien aus |
| **F-04** | Erweiterbarkeit für neue Stimmen | Erfüllt | Dynamische Abfrage vom Chatterbox-Service — neue Stimmen erscheinen automatisch |
| **NF-01** | Usability | Erfüllt | Weboberfläche mit selbsterklärender Bedienung |
| **NF-02** | Performance / Feedback | Erfüllt | Button-Disable und Ladeanimation während Generierung |
| **NF-03** | Zugriffsbeschränkung | Erfüllt | Localhost-Bindung + VPN + Path-Traversal-Schutz |
| **NF-04** | Skalierbarkeit | Grundlegend | ThreadingHTTPServer für parallele Requests |
| **C-01** | Internes Netzwerk | Erfüllt | Kein externer Zugang |
| **C-02** | Lokaler Server | Erfüllt | Keine Cloud-Abhängigkeiten, keine externen Python-Pakete |
| **C-03** | VPN-Pflicht | Erfüllt | Infrastruktur-seitig umgesetzt |

---

## Diagrammverzeichnis

| Datei | Beschreibung |
|-------|-------------|
| [diagrams/01_system_architecture.svg](diagrams/01_system_architecture.svg) | Systemarchitektur mit den drei Schichten (Client, UI-Server, Chatterbox TTS) |
| [diagrams/02_processing_pipeline.svg](diagrams/02_processing_pipeline.svg) | Verarbeitungspipeline: Text → Chatterbox TTS → WAV |
| [diagrams/03_request_response_flow.svg](diagrams/03_request_response_flow.svg) | Sequenzdiagramm: Request-Response-Zyklus |
