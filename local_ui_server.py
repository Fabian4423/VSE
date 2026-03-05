#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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

APPLIO_ROOT = Path(
    os.getenv("APPLIO_ROOT", "/Users/fabianprimus/applio/Applio")
).expanduser().resolve()
APPLIO_PYTHON = Path(
    os.getenv("APPLIO_PYTHON", "/Users/fabianprimus/applio/Applio/.venv/bin/python")
).expanduser()
APPLIO_TIMEOUT_SECONDS = int(os.getenv("APPLIO_TIMEOUT_SECONDS", "600"))
RVC_MODEL_ROOT = Path(
    os.getenv("RVC_MODEL_ROOT", str(BACKEND_ROOT / "models" / "rvc"))
).expanduser().resolve()
STORAGE_ROOT = Path(
    os.getenv("STORAGE_ROOT", str(BACKEND_ROOT / "storage"))
).expanduser().resolve()

INPUT_DIR = STORAGE_ROOT / "input"
INTERMEDIATE_DIR = STORAGE_ROOT / "intermediate"
OUTPUT_DIR = STORAGE_ROOT / "output"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def _json_response(handler: "LocalHandler", status: int, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _resolve_model_path(voice_dir: Path) -> Path | None:
    default = voice_dir / "model.pth"
    if default.exists():
        return default
    pth_files = sorted(voice_dir.glob("*.pth"))
    return pth_files[0] if pth_files else None


def _resolve_index_path(voice_dir: Path) -> Path | None:
    default = voice_dir / "model.index"
    if default.exists():
        return default
    idx_files = sorted(voice_dir.glob("*.index"))
    return idx_files[0] if idx_files else None


def _list_voices() -> list[dict]:
    if not RVC_MODEL_ROOT.exists():
        return []

    voices: list[dict] = []
    for entry in sorted(RVC_MODEL_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        model = _resolve_model_path(entry)
        index = _resolve_index_path(entry)
        voices.append(
            {
                "voice_id": entry.name,
                "has_model": model is not None,
                "model_path": str(model) if model else None,
                "has_index": index is not None,
                "index_path": str(index) if index else None,
            }
        )
    return voices


def _resolve_voice(voice_id: str) -> tuple[Path, Path | None]:
    voice_dir = RVC_MODEL_ROOT / voice_id
    if not voice_dir.exists():
        raise ValueError(f"Unknown voice_id '{voice_id}'.")
    pth_path = _resolve_model_path(voice_dir)
    if pth_path is None:
        raise ValueError(f"Voice '{voice_id}' has no .pth model.")
    index_path = _resolve_index_path(voice_dir)
    return pth_path, index_path


def _validate_output(path: Path) -> None:
    if not path.exists() or path.stat().st_size <= 0:
        raise RuntimeError(f"Applio produced no output audio at {path}")


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


def _applio_infer(input_path: Path, output_path: Path, pth_path: Path, index_path: Path | None) -> None:
    if not input_path.exists():
        raise ValueError(f"Input audio not found: {input_path}")
    if not pth_path.exists():
        raise ValueError(f"Model file not found: {pth_path}")

    index_arg = str(index_path) if index_path and index_path.exists() else ""
    index_rate = "0.3" if index_arg else "0"
    cmd = [
        str(APPLIO_PYTHON),
        "core.py",
        "infer",
        "--input_path",
        str(input_path),
        "--output_path",
        str(output_path),
        "--pth_path",
        str(pth_path),
        "--index_path",
        index_arg,
        "--index_rate",
        index_rate,
        "--f0_method",
        "rmvpe",
        "--export_format",
        "WAV",
        "--embedder_model",
        "contentvec",
    ]
    _run_applio(cmd)
    _validate_output(output_path)


def _applio_tts_and_infer(
    text: str,
    tts_voice: str,
    tts_rate: int,
    output_tts_path: Path,
    output_rvc_path: Path,
    pth_path: Path,
    index_path: Path | None,
) -> None:
    if not pth_path.exists():
        raise ValueError(f"Model file not found: {pth_path}")

    index_arg = str(index_path) if index_path and index_path.exists() else ""
    index_rate = "0.3" if index_arg else "0"
    fake_tts_file = output_tts_path.parent / "_inline_text.txt"
    cmd = [
        str(APPLIO_PYTHON),
        "core.py",
        "tts",
        "--tts_file",
        str(fake_tts_file),
        "--tts_text",
        text,
        "--tts_voice",
        tts_voice,
        "--tts_rate",
        str(tts_rate),
        "--output_tts_path",
        str(output_tts_path),
        "--output_rvc_path",
        str(output_rvc_path),
        "--pth_path",
        str(pth_path),
        "--index_path",
        index_arg,
        "--index_rate",
        index_rate,
        "--f0_method",
        "rmvpe",
        "--export_format",
        "WAV",
        "--embedder_model",
        "contentvec",
    ]
    _run_applio(cmd)
    _validate_output(output_rvc_path)


def _to_public_url(path: Path) -> str:
    rel = path.resolve().relative_to(STORAGE_ROOT)
    return f"/storage/{rel.as_posix()}"


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

        try:
            pth_path, index_path = _resolve_voice(voice_id)
        except ValueError as exc:
            _json_response(self, 404, {"detail": str(exc)})
            return

        token = uuid.uuid4().hex
        output_tts_path = INTERMEDIATE_DIR / f"{token}.wav"
        output_rvc_path = OUTPUT_DIR / f"{token}.wav"
        metadata = {"has_index": index_path is not None}

        if audio_base64:
            if "," in audio_base64 and audio_base64.startswith("data:"):
                audio_base64 = audio_base64.split(",", 1)[1]
            ext = Path(audio_name).suffix or ".wav"
            input_path = INPUT_DIR / f"{token}{ext}"
            try:
                audio_bytes = base64.b64decode(audio_base64, validate=True)
            except Exception:
                _json_response(self, 400, {"detail": "Invalid audio_base64 payload."})
                return
            input_path.write_bytes(audio_bytes)

            try:
                _applio_infer(
                    input_path=input_path,
                    output_path=output_rvc_path,
                    pth_path=pth_path,
                    index_path=index_path,
                )
            except Exception as exc:
                _json_response(self, 500, {"detail": f"Voice conversion failed: {exc}"})
                return

            metadata["input_mode"] = "audio"
            if text:
                metadata["text_note"] = "Ignored because audio_base64 was provided."
            _json_response(
                self,
                200,
                {
                    "input_text": text or "[audio input]",
                    "response_text": "Audio direkt konvertiert.",
                    "voice_id": voice_id,
                    "output_audio_url": _to_public_url(output_rvc_path),
                    "output_audio_path": str(output_rvc_path),
                    "metadata": metadata,
                },
            )
            return

        if not text:
            _json_response(self, 422, {"detail": "Provide either text or audio_base64."})
            return

        try:
            _applio_tts_and_infer(
                text=text,
                tts_voice=tts_voice,
                tts_rate=tts_rate,
                output_tts_path=output_tts_path,
                output_rvc_path=output_rvc_path,
                pth_path=pth_path,
                index_path=index_path,
            )
        except Exception as exc:
            _json_response(self, 500, {"detail": str(exc)})
            return

        metadata["input_mode"] = "text"
        _json_response(
            self,
            200,
            {
                "input_text": text,
                "response_text": text,
                "voice_id": voice_id,
                "output_audio_url": _to_public_url(output_rvc_path),
                "output_audio_path": str(output_rvc_path),
                "metadata": metadata,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local UI server for TTS + STS (Applio CLI bridge)."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    args = parser.parse_args()

    if not FRONTEND_ROOT.exists():
        print(f"Frontend folder not found: {FRONTEND_ROOT}", file=sys.stderr)
        return 1
    if not APPLIO_ROOT.exists():
        print(f"APPLIO_ROOT not found: {APPLIO_ROOT}", file=sys.stderr)
        return 1
    if not APPLIO_PYTHON.exists():
        print(f"APPLIO_PYTHON not found: {APPLIO_PYTHON}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), LocalHandler)
    print(f"Local UI running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
