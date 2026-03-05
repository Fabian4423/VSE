from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ApplioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def infer(
        self,
        input_path: Path,
        output_path: Path,
        pth_path: Path,
        index_path: Path | None,
        f0_method: str = "rmvpe",
    ) -> None:
        if not input_path.exists():
            raise ValueError(f"Input audio not found: {input_path}")
        if not pth_path.exists():
            raise ValueError(f"Model file not found: {pth_path}")

        index_arg = str(index_path) if index_path and index_path.exists() else ""
        index_rate = "0.3" if index_arg else "0"

        cmd = [
            str(self.settings.applio_python),
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
            f0_method,
            "--export_format",
            "WAV",
            "--embedder_model",
            "contentvec",
        ]
        self._run(cmd)
        self._validate_output(output_path)

    def tts_and_infer(
        self,
        text: str,
        tts_voice: str,
        tts_rate: int,
        output_tts_path: Path,
        output_rvc_path: Path,
        pth_path: Path,
        index_path: Path | None,
        f0_method: str = "rmvpe",
    ) -> None:
        if not pth_path.exists():
            raise ValueError(f"Model file not found: {pth_path}")

        index_arg = str(index_path) if index_path and index_path.exists() else ""
        index_rate = "0.3" if index_arg else "0"
        # Applio expects --tts_file, even when text is passed inline.
        fake_tts_file = output_tts_path.parent / "_inline_text.txt"

        cmd = [
            str(self.settings.applio_python),
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
            f0_method,
            "--export_format",
            "WAV",
            "--embedder_model",
            "contentvec",
        ]
        self._run(cmd)
        self._validate_output(output_rvc_path)

    def _run(self, cmd: list[str]) -> None:
        logger.info("Running Applio command: %s", " ".join(cmd))
        # Python 3.12 removed distutils from stdlib. Applio imports distutils.util
        # at module import time, so we inject a tiny compatible module and run core.py.
        shimmed_cmd = [cmd[0], "-c", _CORE_RUNNER_SHIM, *cmd[2:]]
        process = subprocess.run(
            shimmed_cmd,
            cwd=self.settings.applio_root,
            capture_output=True,
            text=True,
            timeout=self.settings.applio_timeout_seconds,
        )
        if process.returncode != 0:
            logger.error("Applio stdout:\n%s", process.stdout)
            logger.error("Applio stderr:\n%s", process.stderr)
            raise RuntimeError(
                f"Applio failed with exit code {process.returncode}. "
                "Check server logs for stdout/stderr."
            )

    @staticmethod
    def _validate_output(path: Path) -> None:
        if not path.exists() or path.stat().st_size <= 0:
            raise RuntimeError(f"Applio produced no output audio at {path}")


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
