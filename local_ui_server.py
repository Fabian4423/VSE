#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as _urllib_req
from urllib.error import URLError
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
BACKEND_ROOT = PROJECT_ROOT / "backend"


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


_load_env_file(BACKEND_ROOT / ".env")

RUNNER_URL = os.getenv("APPLIO_RUNNER_URL", "http://192.168.100.64:5600").rstrip("/")
STORAGE_ROOT = Path(
    os.getenv("STORAGE_ROOT", str(BACKEND_ROOT / "storage"))
).expanduser().resolve()

OUTPUT_DIR = STORAGE_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _runner_get(path: str) -> dict:
    req = _urllib_req.Request(f"{RUNNER_URL}{path}")
    with _urllib_req.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _runner_post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = _urllib_req.Request(
        f"{RUNNER_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urllib_req.urlopen(req, timeout=700) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _list_voices() -> list[dict]:
    try:
        return _runner_get("/voices").get("voices", [])
    except Exception:
        return []


def _to_public_url(path: Path) -> str:
    rel = path.resolve().relative_to(STORAGE_ROOT)
    return f"/storage/{rel.as_posix()}"


def _json_response(handler: "LocalHandler", status: int, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/voices":
            _json_response(self, 200, {"voices": _list_voices()})
            return

        if path.startswith("/storage/"):
            rel = path.removeprefix("/storage/").strip("/")
            target = (STORAGE_ROOT / rel).resolve()
            try:
                target.relative_to(STORAGE_ROOT)
            except ValueError:
                _json_response(self, 403, {"detail": "Forbidden path."})
                return
            if not target.exists() or not target.is_file():
                _json_response(self, 404, {"detail": "File not found."})
                return

            content_type, _ = mimetypes.guess_type(str(target))
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            _json_response(self, 404, {"detail": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            _json_response(self, 400, {"detail": "Invalid content length."})
            return

        try:
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            _json_response(self, 400, {"detail": "Invalid JSON payload."})
            return

        voice_id = str(payload.get("voice_id", "")).strip()
        text = str(payload.get("text", "")).strip()
        tts_voice = str(payload.get("tts_voice", "de-DE-KatjaNeural")).strip() or "de-DE-KatjaNeural"
        tts_rate = int(payload.get("tts_rate", 0))
        audio_base64 = str(payload.get("audio_base64", "")).strip()
        audio_name = str(payload.get("audio_name", "input.wav")).strip() or "input.wav"

        if not voice_id:
            _json_response(self, 422, {"detail": "voice_id is required."})
            return

        token = uuid.uuid4().hex
        output_path = OUTPUT_DIR / f"{token}.wav"

        try:
            if audio_base64:
                # Audio-Modus: an Runner /infer schicken
                result = _runner_post("/infer", {
                    "voice_id": voice_id,
                    "audio_base64": audio_base64,
                })
                input_mode = "audio"
                input_text = text or "[audio input]"
                response_text = "Audio direkt konvertiert."
            elif text:
                # Text-Modus: an Runner /tts schicken
                result = _runner_post("/tts", {
                    "voice_id": voice_id,
                    "text": text,
                    "tts_voice": tts_voice,
                    "tts_rate": tts_rate,
                })
                input_mode = "text"
                input_text = text
                response_text = text
            else:
                _json_response(self, 422, {"detail": "Provide either text or audio_base64."})
                return

        except URLError as exc:
            _json_response(self, 502, {"detail": f"Runner nicht erreichbar: {exc}"})
            return
        except Exception as exc:
            _json_response(self, 500, {"detail": str(exc)})
            return

        # Audio-Daten aus Runner-Antwort lokal speichern
        try:
            audio_bytes = base64.b64decode(result["audio_base64"])
            output_path.write_bytes(audio_bytes)
        except Exception as exc:
            _json_response(self, 500, {"detail": f"Fehler beim Speichern der Audio-Datei: {exc}"})
            return

        _json_response(self, 200, {
            "input_text": input_text,
            "response_text": response_text,
            "voice_id": voice_id,
            "output_audio_url": _to_public_url(output_path),
            "output_audio_path": str(output_path),
            "metadata": {"input_mode": input_mode},
        })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local UI server – proxied to Applio Runner."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    args = parser.parse_args()

    if not FRONTEND_ROOT.exists():
        print(f"Frontend folder not found: {FRONTEND_ROOT}", file=sys.stderr)
        return 1

    # Runner-Erreichbarkeit prüfen
    try:
        _runner_get("/health")
        print(f"Applio Runner erreichbar: {RUNNER_URL}")
    except Exception:
        print(f"WARNUNG: Applio Runner nicht erreichbar ({RUNNER_URL})")
        print("  → Starte applio_runner.py auf dem Host-System.")
        print("  → Server startet trotzdem, API-Calls werden fehlschlagen bis Runner läuft.")

    server = ThreadingHTTPServer((args.host, args.port), LocalHandler)
    print(f"Local UI läuft auf http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
