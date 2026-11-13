"""Showcase recorder: turn a self-animating HTML page into a frame-exact MP4.

Contract with the page (opt-in, deterministic):
  window.__ready            -> true once the page can be stepped
  window.__advance(ms)      -> advance the page clock by ms and draw one frame
  window.__done()           -> optional; true when the animation has finished
Pages without the contract can still be recorded with --realtime (wall-clock
screenshots, not frame-exact).

Local only: launches headless Chrome on loopback, screenshots over CDP, pipes
PNG frames into ffmpeg (libx264, yuv420p). No uploads, no network beyond the
page's own assets.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


class ShowcaseError(RuntimeError):
    pass


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise ShowcaseError("Chrome/Chromium not found; set CHROME_PATH")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _to_url(src) -> str:
    src = str(src)
    if src.startswith(("http://", "https://", "file://")):
        return src
    path, _, query = src.partition("?")
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise ShowcaseError(f"no such file: {p}")
    return p.as_uri() + (f"?{query}" if query else "")


async def _record(url, out, width, height, fps, seconds, scale, realtime, crf, max_seconds, log):
    import websockets  # local dependency, already in the studio venv

    port = _free_port()
    profile = tempfile.mkdtemp(prefix="showcase-chrome-")
    chrome = subprocess.Popen(
        [find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
         "--remote-debugging-address=127.0.0.1", f"--user-data-dir={profile}",
         "--hide-scrollbars", "--mute-audio", "--no-first-run", "--disable-gpu-vsync",
         f"--window-size={width},{height}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ff = None
    try:
        ws_url = None
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.1)
        if not ws_url:
            raise ShowcaseError("Chrome DevTools endpoint did not come up")

        async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
            seq = 0

            async def cdp(method, **params):
                nonlocal seq
                seq += 1
                my = seq
                await ws.send(json.dumps({"id": my, "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == my:
                        if "error" in msg:
                            raise ShowcaseError(f"{method}: {msg['error']}")
                        return msg.get("result", {})

            async def ev(expr):
                r = await cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                if r.get("exceptionDetails"):
                    raise ShowcaseError(f"page error: {r['exceptionDetails'].get('text')}")
                return r.get("result", {}).get("value")

            await cdp("Emulation.setDeviceMetricsOverride", width=width, height=height,
                      deviceScaleFactor=scale, mobile=False)
            await cdp("Page.enable")
            await cdp("Page.navigate", url=url)

            deterministic = False
            for _ in range(150):  # up to ~15s for fonts/CDN/layout
                await asyncio.sleep(0.1)
                if await ev("document.readyState") == "complete" and (
                        realtime or await ev("!!window.__ready")):
                    deterministic = not realtime and bool(await ev("!!window.__ready"))
                    break
            else:
                if not realtime:
                    raise ShowcaseError("page never set window.__ready; use --realtime")
            await ev("document.fonts ? document.fonts.ready.then(()=>1) : 1")
            await asyncio.sleep(0.4)  # let one-shot CSS/D3 intro transitions settle

            ff = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe",
                 "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                 "-vf", f"scale={width*scale}:{height*scale}:flags=lanczos,format=yuv420p",
                 "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                 "-movflags", "+faststart", str(out)],
                stdin=subprocess.PIPE)
            sink = ff.stdin
            assert sink is not None

            step_ms = 1000.0 / fps
            limit = int((seconds or max_seconds) * fps)
            n = 0
            while n < limit:
                if deterministic:
                    await ev(f"window.__advance({step_ms})")
                # JPEG q95 is ~4x faster to capture than PNG and visually lossless after x264
                shot = await cdp("Page.captureScreenshot", format="jpeg", quality=95, captureBeyondViewport=False)
                sink.write(base64.b64decode(shot["data"]))
                n += 1
                if realtime:
                    await asyncio.sleep(step_ms / 1000)
                if not seconds and deterministic and n % fps == 0:
                    if await ev("window.__done ? !!window.__done() : false"):
                        # hold the finished frame for one second
                        for _ in range(fps):
                            sink.write(base64.b64decode(shot["data"]))
                            n += 1
                        break
                if log and n % (fps * 2) == 0:
                    log(f"  {n} frames ({n / fps:.0f}s)")
            sink.close()
            if ff.wait() != 0:
                raise ShowcaseError("ffmpeg failed")
            ff = None
            return {"output": str(out), "frames": n, "seconds": round(n / fps, 2), "fps": fps,
                    "size": [width * scale, height * scale], "deterministic": deterministic}
    finally:
        if ff and ff.poll() is None:
            ff.kill()
        chrome.terminate()
        try:
            chrome.wait(5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


def record(src, out, *, width=1920, height=1080, fps=30, seconds=None, scale=1,
           realtime=False, crf=18, max_seconds=90, log=print):
    out = Path(out).expanduser().resolve()
    if out.exists():
        raise ShowcaseError(f"refusing to overwrite {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        raise ShowcaseError("ffmpeg not found")
    return asyncio.run(_record(_to_url(src), out, width, height, fps, seconds, scale,
                               realtime, crf, max_seconds, log))


def poster(video, out, at=None):
    """Extract one frame (default: last second) as a PNG poster/thumbnail."""
    video, out = Path(video), Path(out)
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]))
    t = dur - 0.5 if at is None else at
    subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t}",
                           "-i", str(video), "-frames:v", "1", str(out)])
    return str(out)
