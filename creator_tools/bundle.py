"""Per-production manifest builder.

Inventories every artifact under a production directory and surfaces open
decisions (human-routed crawl nodes, provenance awaiting review). Read-only over
the production directory except for the single manifest it writes; no network,
no cloud. Never overwrites an existing manifest.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

MANIFEST_NAME = "manifest.json"

_EXT_TYPE = {
    ".mp4": "video", ".mov": "video", ".webm": "video", ".mkv": "video",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image", ".svg": "image",
    ".html": "html", ".htm": "html",
    ".json": "json",
    ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".flac": "audio", ".aac": "audio", ".ogg": "audio",
    ".txt": "text", ".md": "text", ".srt": "text", ".vtt": "text",
}


def _classify(path: Path) -> str:
    return _EXT_TYPE.get(path.suffix.lower(), "other")


def _iso(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_duration(path: Path):
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            stderr=subprocess.DEVNULL, timeout=30).decode().strip()
        return round(float(out), 3)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _open_decisions(root: Path, artifacts):
    decisions = []
    for a in artifacts:
        rel = a["path"]
        name = Path(rel).name
        p = root / rel
        if name == "crawl.json":
            try:
                data = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            for node in data.get("nodes", []):
                if node.get("route") == "human":
                    decisions.append({
                        "source": rel,
                        "kind": "crawl-human-route",
                        "section": node.get("section"),
                        "text": node.get("text"),
                        "scores": node.get("scores", {}),
                    })
        elif name.endswith(".provenance.json"):
            try:
                data = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if data.get("review_required") is True:
                decisions.append({
                    "source": rel,
                    "kind": "provenance-review-required",
                    "operation": data.get("operation"),
                })
    return decisions


def build(production_dir, manifest_name=MANIFEST_NAME) -> dict:
    root = Path(production_dir).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a production directory: {root}")
    artifacts = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == manifest_name:
            continue
        stat = path.stat()
        artifacts.append({
            "path": rel,
            "type": _classify(path),
            "bytes": stat.st_size,
            "sha256": _sha256(path),
            "mtime": _iso(stat.st_mtime),
        })
    videos = [{"path": a["path"], "duration": _ffprobe_duration(root / a["path"])}
              for a in artifacts if a["type"] == "video"]
    images = [a["path"] for a in artifacts if a["type"] == "image"]
    cover = None
    if "poster.png" in images:
        cover = "poster.png"
    elif images:
        pngs = [i for i in images if i.lower().endswith(".png")]
        cover = (pngs or images)[0]
    return {
        "production": root.name,
        "generated_at": _iso(_dt.datetime.now(_dt.timezone.utc).timestamp()),
        "artifacts": artifacts,
        "videos": videos,
        "cover": cover,
        "open_decisions": _open_decisions(root, artifacts),
    }


def write_manifest(production_dir, output=None) -> str:
    root = Path(production_dir).expanduser().resolve()
    if output is None:
        out = root / MANIFEST_NAME
        manifest_name = MANIFEST_NAME
    else:
        out = Path(output).expanduser().resolve()
        manifest_name = out.relative_to(root).as_posix() if out.parent == root else out.name
    if out.exists():
        raise FileExistsError(
            f"Manifest exists: {out}. Pass --output with a new path to avoid overwriting.")
    data = build(root, manifest_name=manifest_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")
    return str(out)
