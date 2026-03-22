# Text-to-Speech Web UI – Anforderungen für Implementierung

## Projektkontext

Eine Weboberfläche soll entwickelt werden, die bestehende Text-to-Speech-Modelle (aktuell nur per CLI nutzbar) für alle Mitarbeitenden zugänglich macht. Die Zielgruppe sind Mitarbeitende mit IT-Affinität, aber ohne CLI-Erfahrung. Betrieb erfolgt ausschließlich im internen Unternehmensnetz auf einem lokalen Server, Zugriff nur via VPN.

---

## Funktionale Anforderungen

### F-01: Text-zu-Audio-Generierung
- Nutzer gibt Text in ein Eingabefeld ein
- Die Anwendung sendet den Text an ein Backend, das daraus eine Tondatei erzeugt
- Kernfunktion der gesamten Anwendung

### F-02: Modellauswahl
- Nutzer kann aus vorhandenen Sprachmodellen auswählen (z.B. Dropdown)
- Die verfügbaren Modelle werden dynamisch vom Backend geladen
- Verschiedene Modelle = verschiedene Stimmen/Anwendungsfälle

### F-03: Download der Tondatei
- Nach Generierung wird die Audiodatei zum Download bereitgestellt
- Einfache Weiterverwendung in nachgelagerten Prozessen (z.B. Videoproduktion)

### F-04: Erweiterbarkeit für neue Modelle
- Neue Modelle müssen ohne Umbau der Oberfläche hinzugefügt werden können
- Backend liefert Modell-Liste dynamisch → Frontend passt sich automatisch an

---

## Nicht-funktionale Anforderungen

### NF-01: Usability
- Intuitives Frontend für Nutzer ohne CLI-Erfahrung
- Geringe Einstiegshürden, selbsterklärende Oberfläche
- Referenz: ISO 9241-11:2018

### NF-02: Performance / Antwortzeiten
- Angemessene Antwortzeiten bei der Audioerzeugung
- Ggf. Ladeindikator/Progress-Feedback während Generierung
- Produktivität darf nicht durch Wartezeiten beeinträchtigt werden

### NF-03: Zugriffsbeschränkung
- Zugriff ausschließlich im Unternehmensnetz
- Kein öffentlicher Zugang, Schutz vor unautorisiertem Zugriff

### NF-04: Skalierbarkeit
- System muss bei steigender Nutzerzahl keine Engpässe erzeugen
- Architektur sollte horizontal oder vertikal skalierbar sein

---

## Randbedingungen (Constraints)

### C-01: Internes Netzwerk
- Betrieb ausschließlich im internen Unternehmensnetz

### C-02: Lokaler Server
- Hosting auf einem lokalen Server (kein Cloud-Deployment)
- Volle Kontrolle über Infrastruktur und Daten

### C-03: VPN-Pflicht
- Zugriff nur über VPN möglich

---

## Referenzszenario (für Akzeptanztest)

**Social-Media-Clip:**
1. Mitarbeiterin meldet sich per VPN an
2. Öffnet die Weboberfläche im Browser
3. Kopiert Sprechertext in das Eingabefeld
4. Wählt ein Sprachmodell aus
5. Startet die Generierung
6. Lädt die fertige Tondatei herunter
7. Verwendet die Datei im Videoprojekt

→ Neue Modelle lassen sich ohne Prozessänderung integrieren.

---

## Technische Implikationen (abgeleitet)

- **Frontend:** Web-UI (HTML/CSS/JS oder React o.ä.), responsiv, simpel
- **Backend:** API-Endpunkte für:
  - `GET /models` – Liste verfügbarer TTS-Modelle
  - `POST /generate` – Text + Modell-ID → Audiodatei zurück
- **Audiodatei:** Als Download bereitgestellt (z.B. WAV, MP3)
- **Sicherheit:** Kein Auth-System explizit gefordert, aber Netzwerk-Restriktion (VPN/internes Netz) ist Pflicht. OWASP Top 10 beachten.
- **Deployment:** Lokaler Server, kein externer Cloud-Dienst
