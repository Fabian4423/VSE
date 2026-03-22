#!/usr/bin/env python3
"""Applio HTTP Runner - läuft auf dem Host-System mit GPU.

Starten:
    python3 applio_runner.py [--host 0.0.0.0] [--port 5600]

Konfiguration via runner.env (neben dieser Datei):
    APPLIO_ROOT=/pfad/zu/Applio
    APPLIO_PYTHON=/pfad/zu/Applio/.venv/bin/python
    RVC_MODEL_ROOT=/pfad/zu/models/rvc
    APPLIO_TIMEOUT_SECONDS=600
    RUNNER_PORT=5600
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parent


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


_load_env_file(PROJECT_DIR / "runner.env")

APPLIO_ROOT = Path(os.getenv("APPLIO_ROOT", "")).expanduser().resolve()
APPLIO_PYTHON = Path(os.getenv("APPLIO_PYTHON", "")).expanduser()
APPLIO_TIMEOUT = int(os.getenv("APPLIO_TIMEOUT_SECONDS", "600"))
MODEL_ROOT = Path(os.getenv("RVC_MODEL_ROOT", str(PROJECT_DIR / "models" / "rvc"))).expanduser().resolve()
RUNNER_PORT = int(os.getenv("RUNNER_PORT", "5600"))

_CORE_RUNNER_SHIM = (
    "import runpy,sys,types;"
    "distutils_mod=types.ModuleType('distutils');"
    "util_mod=types.ModuleType('distutils.util');"
    "util_mod.strtobool=lambda val: "
    "(1 if val.lower() in ('y','yes','t','true','on','1') else "
    "0 if val.lower() in ('n','no','f','false','off','0') else "
    "(_ for _ in ()).throw(ValueError('invalid truth value %r' % (val,))));"
    "distutils_mod.util=util_mod;"
    "sys.modules['distutils']=distutils_mod;"
    "sys.modules['distutils.util']=util_mod;"
    "sys.argv=['core.py']+sys.argv[1:];"
    "runpy.run_path('core.py',run_name='__main__')"
)


def _json(handler: "RunnerHandler", status: int, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


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


def _resolve_model(voice_id: str) -> tuple[Path, Path | None]:
    voice_dir = MODEL_ROOT / voice_id
    if not voice_dir.exists():
        raise ValueError(f"Unknown voice_id '{voice_id}'")
    pth = next(iter(sorted(voice_dir.glob("*.pth"))), voice_dir / "model.pth")
    if not pth.exists():
        raise ValueError(f"No .pth model for '{voice_id}'")
    idx = next(iter(sorted(voice_dir.glob("*.index"))), None)
    return pth, idx


def _run_applio(cmd: list[str]) -> None:
    shimmed = [cmd[0], "-c", _CORE_RUNNER_SHIM, *cmd[2:]]
    proc = subprocess.run(shimmed, cwd=APPLIO_ROOT, capture_output=True, text=True, timeout=APPLIO_TIMEOUT)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1200:]
        raise RuntimeError(f"Applio failed (exit {proc.returncode}): {tail}")


def _do_infer(audio_bytes: bytes, voice_id: str) -> bytes:
    pth, idx = _resolve_model(voice_id)
    idx_arg = str(idx) if idx else ""
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / "input.wav"
        out = Path(tmp) / "output.wav"
        inp.write_bytes(audio_bytes)
        _run_applio([
            str(APPLIO_PYTHON), "core.py", "infer",
            "--input_path", str(inp),
            "--output_path", str(out),
            "--pth_path", str(pth),
            "--index_path", idx_arg,
            "--index_rate", "0.3" if idx_arg else "0",
            "--f0_method", "rmvpe",
            "--export_format", "WAV",
            "--embedder_model", "contentvec",
        ])
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("Applio produced no output audio")
        return out.read_bytes()


def _do_tts(text: str, tts_voice: str, tts_rate: int, voice_id: str) -> bytes:
    pth, idx = _resolve_model(voice_id)
    idx_arg = str(idx) if idx else ""
    with tempfile.TemporaryDirectory() as tmp:
        tts_out = Path(tmp) / "tts.wav"
        rvc_out = Path(tmp) / "rvc.wav"
        fake_txt = Path(tmp) / "_text.txt"
        _run_applio([
            str(APPLIO_PYTHON), "core.py", "tts",
            "--tts_file", str(fake_txt),
            "--tts_text", text,
            "--tts_voice", tts_voice,
            "--tts_rate", str(tts_rate),
            "--output_tts_path", str(tts_out),
            "--output_rvc_path", str(rvc_out),
            "--pth_path", str(pth),
            "--index_path", idx_arg,
            "--index_rate", "0.3" if idx_arg else "0",
            "--f0_method", "rmvpe",
            "--export_format", "WAV",
            "--embedder_model", "contentvec",
        ])
        if not rvc_out.exists() or rvc_out.stat().st_size == 0:
            raise RuntimeError("Applio produced no output audio")
        return rvc_out.read_bytes()


class RunnerHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[{self.address_string()}] {format % args}", flush=True)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            _json(self, 200, {"status": "ok"})
        elif path == "/voices":
            _json(self, 200, {"voices": _list_voices()})
        else:
            _json(self, 404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        try:
            payload = self._read_json()
        except Exception:
            _json(self, 400, {"detail": "Invalid JSON"})
            return

        voice_id = str(payload.get("voice_id", "")).strip()
        if not voice_id:
            _json(self, 422, {"detail": "voice_id is required"})
            return

        try:
            if path == "/infer":
                raw_b64 = str(payload.get("audio_base64", ""))
                if raw_b64.startswith("data:") and "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                audio_bytes = base64.b64decode(raw_b64, validate=True)
                result = _do_infer(audio_bytes, voice_id)
                _json(self, 200, {
                    "audio_base64": base64.b64encode(result).decode(),
                    "format": "wav",
                })

            elif path == "/tts":
                text = str(payload.get("text", "")).strip()
                tts_voice = str(payload.get("tts_voice", "de-DE-KatjaNeural")).strip() or "de-DE-KatjaNeural"
                tts_rate = int(payload.get("tts_rate", 0))
                if not text:
                    _json(self, 422, {"detail": "text is required"})
                    return
                result = _do_tts(text, tts_voice, tts_rate, voice_id)
                _json(self, 200, {
                    "audio_base64": base64.b64encode(result).decode(),
                    "format": "wav",
                })

            else:
                _json(self, 404, {"detail": "Not found"})

        except ValueError as exc:
            _json(self, 404, {"detail": str(exc)})
        except Exception as exc:
            _json(self, 500, {"detail": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Applio HTTP Runner")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=RUNNER_PORT)
    args = parser.parse_args()

    if not APPLIO_ROOT.exists():
        print(f"APPLIO_ROOT not found: {APPLIO_ROOT}", file=sys.stderr)
        print("Bitte runner.env konfigurieren (siehe runner.env.example)", file=sys.stderr)
        return 1
    if not APPLIO_PYTHON.exists():
        print(f"APPLIO_PYTHON not found: {APPLIO_PYTHON}", file=sys.stderr)
        return 1

    print(f"Applio Runner läuft auf http://{args.host}:{args.port}")
    print(f"  APPLIO_ROOT : {APPLIO_ROOT}")
    print(f"  MODEL_ROOT  : {MODEL_ROOT}")
    server = ThreadingHTTPServer((args.host, args.port), RunnerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
