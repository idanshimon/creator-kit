"""`creator.py design-check`: run the browser quality gate on a local HTML file.

Thin wrapper over studio-ui/design-check.mjs (playwright-core + local Chrome).
Floor findings fail the gate (exit 1); reflex/finish findings are reported only.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "studio-ui" / "design-check.mjs"


def run(source: str | Path, report: str | Path | None = None, shots: str | Path | None = None) -> dict:
    if isinstance(source, str) and re.match(r"^http://(127\.0\.0\.1|localhost):\d+/", source):
        src = source  # a page served on loopback (e.g. `mission-control serve`)
    else:
        src = Path(source).expanduser().resolve()
        if not src.is_file() or src.suffix.lower() not in (".html", ".htm"):
            raise ValueError(f"design-check needs an existing .html file or a http://127.0.0.1:PORT/ URL: {src}")
    if not (ROOT / "studio-ui" / "node_modules" / "playwright-core").exists():
        raise RuntimeError("playwright-core missing; run `cd studio-ui && npm ci`")
    cmd = ["node", str(SCRIPT), str(src)]
    if shots:
        cmd.append(str(Path(shots).expanduser().resolve()))
    proc = subprocess.run(cmd, cwd=ROOT / "studio-ui", capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"design-check browser run failed: {proc.stderr.strip()[-800:]}")
    result = json.loads(proc.stdout)
    if report:
        out = Path(report).expanduser().resolve()
        if out.exists():
            raise FileExistsError(f"Report exists; select a new path: {out}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2))
        result["report"] = str(out)
    # Keep stdout readable: drop per-element detail beyond the first few.
    for r in result.get("runs", []):
        r["contrast"] = r["contrast"][:6]
    return result
