"""Local TTS worker. Runs INSIDE local/voice-venv (mlx-audio), never in creator.py's Python.

Reads one JSON job on stdin:
  {"repo", "revision", "extra_repos": {repo: rev}, "engine", "mode",
   "lang": "en", "speed": 1.0, "ref_audio": path|null, "ref_text": str|null,
   "lines": [{"text", "voice", "instruct", "out"}]}
Resolves every repo at its pinned revision in HF_HOME (downloads only when missing and
HF_HUB_OFFLINE is not set), loads the model once, writes one 24 kHz mono WAV per line,
and prints one JSON result line.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _pin_main_ref(repo: str, revision: str) -> None:
    """Some loaders fetch helper repos without a revision; point refs/main at our pin
    so offline runs resolve the cached snapshot instead of failing."""
    from huggingface_hub.constants import HF_HUB_CACHE
    ref = Path(HF_HUB_CACHE) / ("models--" + repo.replace("/", "--")) / "refs" / "main"
    if not ref.exists():
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(revision)


def resolve(repo: str, revision: str) -> str:
    from huggingface_hub import snapshot_download
    path = snapshot_download(repo, revision=revision)
    _pin_main_ref(repo, revision)
    return path


def main() -> int:
    job = json.loads(sys.stdin.read())
    t0 = time.time()
    for repo, rev in (job.get("extra_repos") or {}).items():
        resolve(repo, rev)
    path = resolve(job["repo"], job["revision"])
    overlays = job.get("overlay_files") or {}
    if overlays:
        # Read-only view: snapshot files + pinned extra files, without editing the HF cache.
        from huggingface_hub import hf_hub_download
        view = Path(os.environ["HF_HOME"]).parent / "overlays" / (job["repo"].replace("/", "--") + "@" + job["revision"][:12])
        view.mkdir(parents=True, exist_ok=True)
        for item in Path(path).iterdir():
            link = view / item.name
            if not link.exists():
                link.symlink_to(item.resolve())
        for name, src in overlays.items():
            link = view / name
            if not link.exists():
                link.symlink_to(Path(hf_hub_download(src["repo"], name, revision=src["revision"])).resolve())
        path = str(view)
    if job.get("fetch_only"):
        print(json.dumps({"ok": True, "path": path, "seconds": round(time.time() - t0, 1)}))
        return 0
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    model = load_model(path)
    sr = int(getattr(model, "sample_rate", 24000))
    load_s = time.time() - t0
    outputs = []
    for line in job["lines"]:
        kw = {"text": line["text"], "speed": float(job.get("speed") or 1.0)}
        lang = job.get("lang") or "en"
        if job["engine"] == "qwen3":
            kw["lang_code"] = {"en": "english", "zh": "chinese", "ja": "japanese", "ko": "korean",
                               "de": "german", "fr": "french", "ru": "russian", "pt": "portuguese",
                               "es": "spanish", "it": "italian"}.get(lang, lang)
        else:
            kw["lang_code"] = lang
        if job.get("ref_audio"):
            kw["ref_audio"] = job["ref_audio"]
            if job["engine"] == "qwen3":
                kw["ref_text"] = job.get("ref_text") or ""
        elif job["engine"] == "qwen3":
            kw["voice"] = line.get("voice")
            if line.get("instruct"):
                kw["instruct"] = line["instruct"]
        start = time.time()
        chunks = [np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in model.generate(**kw)]
        if not chunks:
            raise RuntimeError(f"model produced no audio for: {line['text'][:60]}")
        audio = np.concatenate(chunks)
        out = Path(line["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), audio, sr, subtype="PCM_16")
        outputs.append({"out": str(out), "seconds_audio": round(len(audio) / sr, 2),
                        "seconds_compute": round(time.time() - start, 2)})
    print(json.dumps({"ok": True, "path": path, "sample_rate": sr, "load_seconds": round(load_s, 1),
                      "lines": outputs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
