#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as _urllib_req
from urllib.error import HTTPError, URLError
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

CHATTERBOX_URL = os.getenv("CHATTERBOX_URL", "http://192.168.100.64:8004").rstrip("/")
STORAGE_ROOT = Path(
    os.getenv("STORAGE_ROOT", str(BACKEND_ROOT / "storage"))
).expanduser().resolve()

OUTPUT_DIR = STORAGE_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHATTERBOX_VOICES_FALLBACK = [
    "Abigail", "Adrian", "Alexander", "Alice", "Austin", "Axel",
    "Connor", "Cora", "Elena", "Eli", "Emily", "Everett",
    "Gabriel", "Gianna", "Henry", "Ian", "Jade", "Jeremiah",
    "Jordan", "Julian", "Layla", "Leonardo", "Michael", "Miles",
    "Olivia", "Ryan", "Taylor", "Thomas",
]


def _fetch_chatterbox_voices() -> list[str] | None:
    """Fetch predefined voices from Chatterbox TTS. Returns None on failure."""
    try:
        req = _urllib_req.Request(f"{CHATTERBOX_URL}/get_predefined_voices")
        with _urllib_req.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, list) or not data:
            return None
        voices = []
        for item in data:
            if isinstance(item, str):
                voices.append(item.removesuffix(".wav"))
            elif isinstance(item, dict):
                name = item.get("name") or item.get("voice_id") or item.get("display_name", "")
                if name:
                    voices.append(str(name).removesuffix(".wav"))
        return voices or None
    except Exception:
        return None


def _chatterbox_tts(text: str, voice_id: str) -> bytes:
    """Send text to Chatterbox TTS and return WAV bytes."""
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


def _chatterbox_health() -> bool:
    """Check if Chatterbox TTS service is reachable."""
    try:
        req = _urllib_req.Request(f"{CHATTERBOX_URL}/")
        with _urllib_req.urlopen(req, timeout=5):
            pass
        return True
    except HTTPError:
        return True  # Server reachable, just returned non-2xx
    except Exception:
        return False


def _to_public_url(path: Path) -> str:
    rel = path.resolve().relative_to(STORAGE_ROOT)
    return f"storage/{rel.as_posix()}"


def _json_response(handler: "LocalHandler", status: int, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


BASE_PATH = "/vse"


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_ROOT), **kwargs)

    def _strip_base(self, path: str) -> str | None:
        """Strip BASE_PATH prefix. Returns stripped path or None if not matching."""
        if path == BASE_PATH or path == BASE_PATH + "/":
            return "/"
        if path.startswith(BASE_PATH + "/"):
            return path[len(BASE_PATH):]
        return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        # Redirect bare "/" to the base path
        if path == "/":
            self.send_response(302)
            self.send_header("Location", BASE_PATH + "/")
            self.end_headers()
            return

        stripped = self._strip_base(path)
        if stripped is None:
            _json_response(self, 404, {"detail": "Not found."})
            return

        if stripped == "/api/voices":
            voices_list = _fetch_chatterbox_voices() or CHATTERBOX_VOICES_FALLBACK
            voices = [{"voice_id": v} for v in voices_list]
            _json_response(self, 200, {"voices": voices})
            return

        if stripped.startswith("/storage/"):
            rel = stripped.removeprefix("/storage/").strip("/")
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

        # Serve static frontend files with stripped path
        self.path = stripped
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        stripped = self._strip_base(parsed.path)
        if stripped != "/api/run":
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

        if not voice_id:
            _json_response(self, 422, {"detail": "voice_id is required."})
            return
        if not text:
            _json_response(self, 422, {"detail": "text is required."})
            return
        token = uuid.uuid4().hex
        output_path = OUTPUT_DIR / f"{token}.wav"

        try:
            audio_bytes = _chatterbox_tts(text, voice_id)
            output_path.write_bytes(audio_bytes)
        except URLError as exc:
            _json_response(self, 502, {"detail": f"Chatterbox TTS nicht erreichbar: {exc}"})
            return
        except Exception as exc:
            _json_response(self, 500, {"detail": str(exc)})
            return

        _json_response(self, 200, {
            "input_text": text,
            "response_text": text,
            "voice_id": voice_id,
            "output_audio_url": _to_public_url(output_path),
            "output_audio_path": str(output_path),
            "metadata": {"input_mode": "text"},
        })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local UI server – proxied to Chatterbox TTS."
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5174)
    args = parser.parse_args()

    if not FRONTEND_ROOT.exists():
        print(f"Frontend folder not found: {FRONTEND_ROOT}", file=sys.stderr)
        return 1

    if _chatterbox_health():
        print(f"Chatterbox TTS erreichbar: {CHATTERBOX_URL}")
    else:
        print(f"WARNUNG: Chatterbox TTS nicht erreichbar ({CHATTERBOX_URL})")
        print("  → Server startet trotzdem, API-Calls werden fehlschlagen bis Chatterbox läuft.")

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
