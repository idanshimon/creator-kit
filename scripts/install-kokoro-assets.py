"""Install the official English release pair without overwriting unverified files."""
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "OpenMontage/.venv/share/hyperframes-model-files-v1.1/tts"
URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
ASSETS = {
    "models/kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices/voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

if __name__ == "__main__":
    for rel, expected in ASSETS.items():
        target = CACHE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(target) != expected:
                raise SystemExit(f"Unexpected contents: {target}; move aside before retrying")
            continue
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            staged = Path(tmp) / target.name
            with urlopen(URL + target.name, timeout=180) as src, staged.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            if digest(staged) != expected:
                raise SystemExit(f"Digest mismatch: {rel}")
            staged.replace(target)
