"""Narrated product walkthroughs from screenshots or live URLs.

Spec (JSON):
  {
    "title": "optional",
    "width": 1920, "height": 1080,          # output canvas (optional)
    "viewport": [1440, 900],                # capture viewport for url steps (optional)
    "steps": [
      {"image": "shot.png" | "url": "https://… or file path",
       "target": {"x":..,"y":..,"w":..,"h":..} | "selector": "#css",   # image px
       "annotations": ["arrow","spotlight","zoom","click","badge","callout","cursor"],
       "arrow_style": "hand" | "clean",
       "callout": "short label (optional)",
       "caption": "on-screen lower-third (defaults to narration)",
       "narration": "spoken text", "dwell": 0.6}
    ]
  }

Pipeline: resolve/capture images -> SCRIPT.md -> narrate (kokoro default) ->
deterministic HTML (templates/walkthrough, no CDN) timed to timeline.json ->
showcase.record (frame exact) -> mux narration (h264+aac) -> poster.png ->
optional README GIF (palettegen, burned-in captions).
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "walkthrough" / "walkthrough.html"
KINDS = ("arrow", "spotlight", "zoom", "click", "badge", "callout", "cursor")
DEFAULT_KINDS = ["arrow", "spotlight", "zoom", "click", "badge", "cursor"]



class WalkthroughError(ValueError):
    pass


# ---------------------------------------------------------------- spec
def load_spec(path) -> dict:
    p = Path(path).expanduser().resolve()
    spec = json.loads(p.read_text(encoding="utf-8"))
    return validate_spec(spec, base=p.parent)


def _rect(t, where):
    if not isinstance(t, dict) or not all(k in t for k in "xywh"):
        raise WalkthroughError(f"{where}: target must be {{x,y,w,h}}")
    r = {k: float(t[k]) for k in "xywh"}
    if r["w"] <= 0 or r["h"] <= 0 or r["x"] < 0 or r["y"] < 0:
        raise WalkthroughError(f"{where}: target needs positive w/h and non-negative x/y")
    return r


def validate_spec(spec: dict, base: Path | None = None) -> dict:
    if not isinstance(spec, dict) or not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise WalkthroughError("spec needs a non-empty 'steps' list")
    base = Path(base or ".")
    out = {"title": str(spec.get("title", "")), "width": int(spec.get("width", 1920)),
           "height": int(spec.get("height", 1080)),
           "viewport": list(spec.get("viewport", [1440, 900])), "steps": []}
    for i, s in enumerate(spec["steps"], 1):
        where = f"step {i}"
        if not isinstance(s, dict):
            raise WalkthroughError(f"{where}: must be an object")
        if bool(s.get("image")) == bool(s.get("url")):
            raise WalkthroughError(f"{where}: give exactly one of 'image' or 'url'")
        narration = str(s.get("narration", "")).strip()
        if not narration:
            raise WalkthroughError(f"{where}: narration text is required")
        kinds = s.get("annotations", DEFAULT_KINDS)
        bad = [k for k in kinds if k not in KINDS]
        if bad:
            raise WalkthroughError(f"{where}: unknown annotation(s) {bad}; choose from {KINDS}")
        step = {"narration": narration, "caption": str(s.get("caption") or narration).strip(),
                "annotations": list(kinds), "arrow_style": s.get("arrow_style", "hand"),
                "callout": str(s.get("callout", "")), "dwell": float(s.get("dwell", 0.6))}
        if step["arrow_style"] not in ("hand", "clean"):
            raise WalkthroughError(f"{where}: arrow_style must be hand or clean")
        if s.get("image"):
            img = Path(s["image"]).expanduser()
            img = img if img.is_absolute() else (base / img)
            if not img.exists():
                raise WalkthroughError(f"{where}: image not found: {img}")
            step["image"] = str(img.resolve())
            step["target"] = _rect(s.get("target"), where)
        else:
            u = str(s["url"])
            if not u.startswith(("http://", "https://", "file://")):
                p = Path(u).expanduser()
                p = p if p.is_absolute() else base / p
                u = p.resolve().as_uri()
            step["url"] = u
            if s.get("selector"):
                step["selector"] = str(s["selector"])
            elif s.get("target"):
                step["target"] = _rect(s["target"], where)
            else:
                raise WalkthroughError(f"{where}: url steps need 'selector' or 'target'")
        out["steps"].append(step)
    return out


def write_script(spec: dict, path: Path) -> str:
    lines = [f"# {spec.get('title') or 'Walkthrough'}", ""]
    for i, s in enumerate(spec["steps"], 1):
        lines += [f"## Step {i} (Frame {i})", "", f"**Dwell:** {s['dwell']}", "",
                  "    " + " ".join(s["narration"].split()), ""]
    text = "\n".join(lines)
    with Path(path).open("x", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------- capture
def png_size(path) -> tuple[int, int]:
    b = Path(path).read_bytes()[:32]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height", "-of", "csv=p=0", str(path)], text=True)
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


async def _capture(url, selector, out_png, vw, vh):
    import websockets
    from creator_tools import showcase
    port = showcase._free_port()
    profile = tempfile.mkdtemp(prefix="walkthrough-chrome-")
    chrome = subprocess.Popen(
        [showcase.find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
         "--remote-debugging-address=127.0.0.1", f"--user-data-dir={profile}", "--hide-scrollbars",
         "--mute-audio", "--no-first-run", f"--window-size={vw},{vh}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            raise WalkthroughError("Chrome DevTools endpoint did not come up")
        async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
            seq = 0

            async def cdp(method, **params):
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"id": seq, "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == seq:
                        if "error" in msg:
                            raise WalkthroughError(f"{method}: {msg['error']}")
                        return msg.get("result", {})

            async def ev(expr):
                r = await cdp("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
                return r.get("result", {}).get("value")

            await cdp("Emulation.setDeviceMetricsOverride", width=vw, height=vh, deviceScaleFactor=1, mobile=False)
            await cdp("Page.enable")
            await cdp("Page.navigate", url=url)
            for _ in range(150):
                await asyncio.sleep(0.1)
                if await ev("document.readyState") == "complete":
                    break
            await ev("document.fonts ? document.fonts.ready.then(()=>1) : 1")
            await asyncio.sleep(1.2)  # let intro transitions settle
            rect = None
            if selector:
                sel = json.dumps(selector)
                find = ("(s => { if (!s.startsWith('text=')) return document.querySelector(s);"
                        " const want = s.slice(5).trim(); let best = null;"
                        " for (const e of document.querySelectorAll('body *')) {"
                        "  if ((e.textContent || '').trim() === want && (!best || best.contains(e))) best = e; }"
                        " return best && best.closest('g') && best instanceof SVGElement ? best.closest('g') : best; })")
                await ev(f"window.__wtFind = {find}")
                rect = await ev(f"""(() => {{ const e = window.__wtFind({sel}); if (!e) return null;
                    e.scrollIntoView({{block:'nearest'}}); const r = e.getBoundingClientRect();
                    return {{x:r.left, y:r.top, w:r.width, h:r.height}}; }})()""")
                if not rect or rect["w"] <= 0:
                    raise WalkthroughError(f"selector not found or not visible: {selector}")
                await asyncio.sleep(0.3)
                rect = await ev(f"""(() => {{ const r = window.__wtFind({sel}).getBoundingClientRect();
                    return {{x:r.left, y:r.top, w:r.width, h:r.height}}; }})()""")
                # clip to viewport
                x0, y0 = max(0, rect["x"]), max(0, rect["y"])
                rect = {"x": x0, "y": y0, "w": min(vw, rect["x"] + rect["w"]) - x0,
                        "h": min(vh, rect["y"] + rect["h"]) - y0}
            shot = await cdp("Page.captureScreenshot", format="png", captureBeyondViewport=False)
            Path(out_png).write_bytes(base64.b64decode(shot["data"]))
            return rect
    finally:
        chrome.terminate()
        try:
            chrome.wait(5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


def capture_url(url, out_png, selector=None, viewport=(1440, 900)):
    return asyncio.run(_capture(url, selector, out_png, int(viewport[0]), int(viewport[1])))


def resolve_assets(spec: dict, out: Path, log=print) -> list[dict]:
    assets = out / "assets"
    assets.mkdir(exist_ok=True)
    steps = []
    for i, s in enumerate(spec["steps"], 1):
        dst = assets / f"step-{i:02d}.png"
        if "image" in s:
            src = Path(s["image"])
            if src.suffix.lower() != ".png":
                subprocess.check_call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), str(dst)])
            else:
                shutil.copyfile(src, dst)
            target = s["target"]
        else:
            log(f"  capturing step {i}: {s['url']}")
            rect = capture_url(s["url"], dst, s.get("selector"), spec["viewport"])
            target = rect or s["target"]
        w, h = png_size(dst)
        if target["x"] + target["w"] > w + 1 or target["y"] + target["h"] > h + 1:
            raise WalkthroughError(f"step {i}: target {target} lies outside the {w}x{h} image")
        steps.append({**{k: v for k, v in s.items() if k not in ("image",)},
                      "src": f"assets/{dst.name}", "iw": w, "ih": h,
                      "target": {k: round(float(v), 1) for k, v in target.items()}})
    return steps


# ---------------------------------------------------------------- html
def build_html(spec: dict, steps: list[dict], timeline: dict) -> str:
    slides = timeline["slides"]
    if len(slides) != len(steps):
        raise WalkthroughError(f"timeline has {len(slides)} slides but spec has {len(steps)} steps")
    data_steps = []
    for i, (s, sl) in enumerate(zip(steps, slides), 1):
        data_steps.append({**s, "n": i, "start": sl["start"], "end": sl["end"],
                           "speech": sl["speech_duration"], "spoken": sl["text"]})
    data = {"title": spec.get("title", ""), "W": spec["width"], "H": spec["height"],
            "total": timeline["total_duration"], "steps": data_steps}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if "/*__WALKTHROUGH_DATA__*/null" not in tpl:
        raise WalkthroughError("template missing data placeholder")
    return tpl.replace("/*__WALKTHROUGH_DATA__*/null", blob)


# ---------------------------------------------------------------- media
def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *args], check=True)


def mux(video, audio, out, total):
    _ff("-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out))


def make_gif(video, out, width=900, fps=12, max_mb=6.0, log=print):
    tries = [(width, fps), (width, 10), (800, 10), (720, 8)]
    for w, f in tries:
        tmp = Path(out).with_suffix(".tmp.gif")
        if tmp.exists():
            tmp.unlink()
        vf = (f"fps={f},scale={w}:-2:flags=lanczos,split[a][b];"
              "[a]palettegen=max_colors=128:stats_mode=diff[p];"
              "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
        _ff("-i", str(video), "-vf", vf, "-loop", "0", str(tmp))
        mb = tmp.stat().st_size / 1e6
        log(f"  gif {w}px @{f}fps = {mb:.2f} MB")
        if mb <= max_mb or (w, f) == tries[-1]:
            tmp.rename(out)
            return {"path": str(out), "width": w, "fps": f, "mb": round(mb, 2)}
        tmp.unlink()


def probe(path) -> dict:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,codec_name:format=duration", "-of", "json", str(path)])
    j = json.loads(out)
    return {"duration": round(float(j["format"]["duration"]), 3),
            "codecs": {s["codec_type"]: s["codec_name"] for s in j["streams"]}}


# ---------------------------------------------------------------- cli
def _engines():
    from creator_tools import narrate
    return narrate.ENGINES


def add_arguments(p):
    p.add_argument("--spec", required=True, help="walkthrough spec JSON (steps with image|url, target|selector, narration)")
    p.add_argument("--output", required=True, help="new output directory (refuses to overwrite)")
    p.add_argument("--engine", default="kokoro", choices=_engines(), help="narration engine (default kokoro, local)")
    p.add_argument("--voice", default=None, help="narration voice passthrough")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--allow-cloud", action="store_true", help="required for --engine azure")
    p.add_argument("--narration", default=None,
                   help="reuse an existing narrate output dir (timeline.json + narration.wav) instead of synthesizing")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--gif", action="store_true", help="also write walkthrough.gif (README preview, burned-in captions)")
    p.add_argument("--gif-width", type=int, default=900)
    p.add_argument("--gif-max-mb", type=float, default=6.0)
    p.add_argument("--html-only", action="store_true", help="stop after walkthrough.html (no recording)")
    return p


def run(args, log=print) -> dict:
    out = Path(args.output).expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Output exists; select a new directory: {out}")
    spec = load_spec(args.spec)
    if args.engine == "azure" and not args.allow_cloud and not args.narration:
        raise WalkthroughError("--engine azure sends narration text to Azure; add --allow-cloud")
    out.mkdir(parents=True)
    with (out / "spec.resolved.json").open("x", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    write_script(spec, out / "SCRIPT.md")
    log("[1/5] resolving screenshots")
    steps = resolve_assets(spec, out, log)

    log("[2/5] narration")
    if args.narration:
        ndir = Path(args.narration).expanduser().resolve()
    else:
        from creator_tools import narrate
        ndir = out / "narration"
        narrate.run(out / "SCRIPT.md", ndir, engine=args.engine, default_voice=args.voice,
                    speed=args.speed, allow_cloud=args.allow_cloud, root=ROOT)
    timeline = json.loads((ndir / "timeline.json").read_text(encoding="utf-8"))
    wav = ndir / "narration.wav"

    log("[3/5] html")
    html = out / "walkthrough.html"
    with html.open("x", encoding="utf-8") as f:
        f.write(build_html(spec, steps, timeline))
    result = {"output": str(out), "html": str(html), "steps": len(steps), "timeline": str(ndir / "timeline.json"),
              "narration_wav": str(wav), "total_duration": timeline["total_duration"]}
    if args.html_only:
        return result

    from creator_tools import showcase
    log("[4/5] recording")
    total = float(timeline["total_duration"])
    silent = out / "silent.mp4"
    showcase.record(html, silent, width=spec["width"], height=spec["height"], fps=args.fps,
                    seconds=total, log=log)
    mp4 = out / "walkthrough.mp4"
    mux(silent, wav, mp4, total)
    silent.unlink()
    showcase.poster(mp4, out / "poster.png", at=min(total - 0.2, steps and timeline["slides"][0]["start"] + 2.2))
    result.update(video=str(mp4), poster=str(out / "poster.png"), probe=probe(mp4))
    if args.gif:
        log("[5/5] gif")
        result["gif"] = make_gif(mp4, out / "walkthrough.gif", width=args.gif_width,
                                 max_mb=args.gif_max_mb, log=log)
    with (out / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


def main(argv=None):  # standalone: python3 -m creator_tools.walkthrough
    import argparse
    ap = add_arguments(argparse.ArgumentParser(prog="walkthrough"))
    print(json.dumps(run(ap.parse_args(argv)), indent=2))


if __name__ == "__main__":
    main()
