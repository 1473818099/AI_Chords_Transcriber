# backend/server.py
import os
import sys
import asyncio
import tempfile
import pathlib
import subprocess
import importlib.util
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# =======================
# Config (edit if needed)
# =======================
DEFAULT_REPO_NAME = "ISMIR2019-Large-Vocabulary-Chord-Recognition"
SCRIPT_NAME = "chord_recognition.py"

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
MAX_AUDIO_SECONDS = int(os.environ.get("MAX_AUDIO_SECONDS", "600"))          # best-effort via ffprobe
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "180"))
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "1"))

# audio normalization (optional)
TRANSCODE_TO_WAV = os.environ.get("TRANSCODE_TO_WAV", "1") == "1"
WAV_SR = int(os.environ.get("WAV_SR", "22050"))

# ffmpeg tools
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

# =======================
# App
# =======================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

_sem = asyncio.Semaphore(MAX_CONCURRENT)

# -----------------------
# Repo / script discovery
# -----------------------
def _default_repo_dir() -> pathlib.Path:
    backend_dir = pathlib.Path(__file__).resolve().parent
    return (backend_dir / DEFAULT_REPO_NAME).resolve()

def _resolve_repo_dir() -> pathlib.Path:
    env = os.environ.get("CHORD_REPO_DIR", "").strip()
    if env:
        return pathlib.Path(env).expanduser().resolve()
    return _default_repo_dir()

def _require_paths():
    repo = _resolve_repo_dir()
    script = repo / SCRIPT_NAME

    if not repo.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Repo not found: {repo}. Put repo at backend/{DEFAULT_REPO_NAME} or set CHORD_REPO_DIR."
        )
    if not script.exists():
        raise HTTPException(
            status_code=500,
            detail=f"{SCRIPT_NAME} not found in repo: {repo}"
        )

    # best-effort: check weights exist (*.best)
    weight_candidates = list(repo.glob("**/*.best"))
    return repo, script, weight_candidates

def _which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)

def _probe_duration_seconds(path: pathlib.Path) -> Optional[float]:
    if not _which(FFPROBE):
        return None
    try:
        p = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10
        )
        if p.returncode != 0:
            return None
        s = (p.stdout or "").strip()
        return float(s) if s else None
    except Exception:
        return None

def _transcode_to_wav(src: pathlib.Path, dst: pathlib.Path):
    if not _which(FFMPEG):
        raise RuntimeError("ffmpeg not found")
    cmd = [
        FFMPEG, "-y",
        "-i", str(src),
        "-ac", "1",
        "-ar", str(WAV_SR),
        str(dst)
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=True)

async def _save_upload_streaming(up: UploadFile, dst: pathlib.Path):
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    with open(dst, "wb") as f:
        while True:
            chunk = await up.read(1024 * 1024)  # 1MB chunk
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail=f"File too large (>{MAX_UPLOAD_MB}MB).")
            f.write(chunk)

def _tail(s: str, n: int = 2000) -> str:
    if not s:
        return ""
    return s[-n:]

def _inference_env() -> dict:
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    return env

def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

# -----------------------
# Health / diagnostics
# -----------------------
@app.get("/health")
def health():
    repo, script, weights = _require_paths()

    ffmpeg_ok = _which(FFMPEG) is not None
    ffprobe_ok = _which(FFPROBE) is not None

    deps = {
        "torch": _module_available("torch"),
        "librosa": _module_available("librosa"),
        "numpy": _module_available("numpy"),
        "scipy": _module_available("scipy"),
    }

    return {
        "ok": True,
        "repo": str(repo),
        "script": str(script),
        "python": sys.executable,
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "weights_found": len(weights),
        "deps": deps,
        "limits": {
            "max_upload_mb": MAX_UPLOAD_MB,
            "max_audio_seconds": MAX_AUDIO_SECONDS,
            "timeout_seconds": TIMEOUT_SECONDS,
            "max_concurrent": MAX_CONCURRENT,
            "transcode_to_wav": TRANSCODE_TO_WAV,
            "wav_sr": WAV_SR
        }
    }

# -----------------------
# Main API
# -----------------------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    repo, script, _weights = _require_paths()

    fname = (file.filename or "audio").strip()
    suffix = pathlib.Path(fname).suffix.lower() or ".audio"

    async with _sem:
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)

            raw_path = td / f"input{suffix}"
            lab_path = td / "chord.lab"
            input_path = raw_path

            # 1) save upload to disk (streaming, size-limited)
            await _save_upload_streaming(file, raw_path)

            # 2) duration check (best-effort)
            dur = _probe_duration_seconds(raw_path)
            if dur is not None and dur > MAX_AUDIO_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Audio too long: {dur:.1f}s (limit {MAX_AUDIO_SECONDS}s)."
                )

            # 3) optional transcode to wav (best-effort)
            if TRANSCODE_TO_WAV:
                try:
                    wav_path = td / "input.wav"
                    _transcode_to_wav(raw_path, wav_path)
                    input_path = wav_path
                except Exception:
                    input_path = raw_path

            # 4) run inference using current python (same env)
            cmd = [sys.executable, str(script), str(input_path), str(lab_path)]

            try:
                p = subprocess.run(
                    cmd,
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS,
                    env=_inference_env()
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="Inference timeout.")

            if p.returncode != 0 or not lab_path.exists():
                return JSONResponse(
                    {
                        "ok": False,
                        "detail": "Inference failed.",
                        "cmd": cmd,
                        "stdout": _tail(p.stdout),
                        "stderr": _tail(p.stderr),
                        "duration_sec": dur
                    },
                    status_code=500
                )

            lab_text = lab_path.read_text(encoding="utf-8", errors="ignore")
            return {"ok": True, "lab": lab_text, "duration_sec": dur}
