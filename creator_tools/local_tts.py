"""Local open-weight TTS (Qwen3-TTS, Chatterbox) for `narrate` and `voices`.

The registry `integrations/voice-models.json` is the single owner of model ids, pinned
revisions, licenses and stock voices. Weights live in ignored `local/models/hf` (HF_HOME).
A missing runtime or model is bootstrapped on first use (runtime via uv + the pinned
mlx-audio; weights via huggingface_hub at the pinned revision) unless `offline=True`.
Inference runs in `local/voice-venv` through `voice_worker.py`; this module is stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "integrations" / "voice-models.json"
WORKER = Path(__file__).resolve().parent / "voice_worker.py"
ENGINES = ("qwen3", "chatterbox")
# Optional package index for the voice runtime (e.g. a corporate PyPI mirror); default is PyPI.
PACKAGE_INDEX = os.environ.get("CREATOR_PIP_INDEX", "").strip()


def registry(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / "integrations" / "voice-models.json").read_text())


def pick_model(engine: str, *, clone: bool, reg: dict | None = None) -> tuple[str, dict]:
    reg = reg or registry()
    if engine not in ENGINES:
        raise ValueError(f"local engine must be one of {ENGINES}")
    key = engine if engine == "chatterbox" else ("qwen3-clone" if clone else "qwen3-stock")
    return key, reg["models"][key]


def check_voice(model: dict, voice: str | None) -> str | None:
    voices = model.get("voices")
    if not voices:
        return None
    voice = voice or model.get("default_voice")
    if voice not in voices:
        raise ValueError(f"Unknown voice {voice!r}; stock voices: {', '.join(voices)}")
    return voice


def _child_env(root: Path, offline: bool) -> dict:
    keep = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "UV_DEFAULT_INDEX", "PIP_INDEX_URL",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "HF_TOKEN")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["HF_HOME"] = str(root / registry(root)["runtime"]["hf_home"])
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    if offline:
        env["HF_HUB_OFFLINE"] = "1"
    return env


def venv_python(root: Path = ROOT) -> Path:
    return Path(root) / registry(root)["runtime"]["venv"] / "bin" / "python"


def ensure_runtime(root: Path = ROOT, *, offline: bool = False) -> Path:
    """Return the runtime interpreter, creating the pinned venv when it is missing."""
    py = venv_python(root)
    if py.is_file():
        return py
    if offline:
        raise RuntimeError(f"Voice runtime missing at {py.parent.parent}; run without --offline to bootstrap")
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("Voice runtime bootstrap needs `uv` on PATH")
    rt = registry(root)["runtime"]
    env = dict(os.environ)
    if PACKAGE_INDEX:
        env.setdefault("UV_DEFAULT_INDEX", PACKAGE_INDEX)
    venv = py.parent.parent
    subprocess.run([uv, "venv", "-q", "-p", rt["python"], str(venv)], check=True, env=env, timeout=600)
    pins = [f"{k}=={v}" for k, v in rt["packages"].items()]
    subprocess.run([uv, "pip", "install", "-q", "--python", str(py), *pins], check=True, env=env, timeout=1800)
    return py


def _run_worker(job: dict, root: Path, offline: bool, timeout: int) -> dict:
    py = ensure_runtime(root, offline=offline)
    proc = subprocess.run([str(py), str(WORKER)], input=json.dumps(job), capture_output=True,
                          text=True, env=_child_env(root, offline), timeout=timeout, cwd=str(root))
    last = [l for l in proc.stdout.splitlines() if l.startswith("{")]
    if proc.returncode or not last:
        raise RuntimeError("Local TTS worker failed: " + (proc.stderr or proc.stdout)[-800:])
    return json.loads(last[-1])


def _job_base(model: dict) -> dict:
    return {"repo": model["repo"], "revision": model["revision"],
            "extra_repos": model.get("extra_repos") or {}, "engine": model["engine"],
            "overlay_files": model.get("overlay_files") or {},
            "mode": model["mode"]}


def fetch(keys=None, root: Path = ROOT, timeout: int = 7200) -> list[dict]:
    """Bootstrap runtime + weights ahead of time (download only what is missing)."""
    reg = registry(root)
    out = []
    for key in keys or list(reg["models"]):
        res = _run_worker({**_job_base(reg["models"][key]), "fetch_only": True}, Path(root), False, timeout)
        out.append({"model": key, **res})
    return out


def status(root: Path = ROOT) -> dict:
    reg = registry(root)
    cache = Path(root) / reg["runtime"]["hf_home"] / "hub"
    models = {}
    for key, m in reg["models"].items():
        snap = cache / ("models--" + m["repo"].replace("/", "--")) / "snapshots" / m["revision"]
        models[key] = {"repo": m["repo"], "license": m["license"], "downloaded": snap.is_dir(),
                       "voices": m.get("voices") or {}, "languages": m["languages"],
                       "verified_languages": m.get("verified_languages", []),
                       "blocked_languages": sorted(m.get("blocked_languages") or {})}
    return {"runtime_installed": venv_python(root).is_file(), "models": models}


def _peak_db(wav: Path) -> float:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", "volumedetect",
                           "-f", "null", "-"], capture_output=True, text=True, timeout=60)
    m = re.search(r"max_volume:\s*(-?[0-9.]+|-inf) dB", proc.stderr)
    return float("-inf") if not m or m.group(1) == "-inf" else float(m.group(1))


def synthesize_lines(engine: str, lines: list[dict], *, ref_wav: str | None = None,
                     ref_text: str | None = None, lang: str = "en", speed: float = 1.0,
                     offline: bool = False, root: Path = ROOT, timeout: int = 3600) -> dict:
    """lines: [{"text", "voice", "instruct", "out"}]. Loads the model once for all lines."""
    clone = bool(ref_wav)
    key, model = pick_model(engine, clone=clone, reg=registry(root))
    blocked = (model.get("blocked_languages") or {}).get(lang)
    if blocked:
        raise ValueError(f"{key} is blocked for {lang!r}: {blocked}")
    if lang not in model["languages"]:
        raise ValueError(f"{key} does not support language {lang!r}; supported: {', '.join(model['languages'])}")
    if clone and engine == "qwen3" and not (ref_text or "").strip():
        raise ValueError("Qwen3 voice cloning needs --ref-text: the exact transcript of --ref")
    prepared = []
    for line in lines:
        voice = None if clone else check_voice(model, line.get("voice"))
        prepared.append({**line, "voice": voice})
    job = {**_job_base(model), "lang": lang, "speed": speed,
           "ref_audio": str(Path(ref_wav).expanduser().resolve()) if ref_wav else None,
           "ref_text": ref_text, "lines": prepared}
    job["root"] = str(Path(root))
    result = _run_worker(job, Path(root), offline, timeout)
    for item in result["lines"]:
        wav = Path(item["out"])
        if not wav.is_file() or wav.stat().st_size < 4096:
            wav.unlink(missing_ok=True)
            raise ValueError(f"{key} produced an undersized WAV: {wav}")
        peak = _peak_db(wav)
        if peak < -40:
            raise ValueError(f"{key} produced near-silent audio ({peak} dB peak): {wav}")
        item["peak_db"] = peak
    return {"model": key, "repo": model["repo"], "revision": model["revision"],
            "license": model["license"], **result}
