"""Short-form social video templates (TikTok / Reels / Shorts / LinkedIn).

`creator.py reel --spec reel.json --output productions/<name>` writes a self-contained,
deterministic `index.html` (no network, no wall clock), records it frame-exact with
`showcase.record` to `reel.mp4`, optionally muxes narration audio, and writes `poster.png`
and (with --gif) `preview.gif`.

Spec (JSON):
  template   kinetic | pov | countdown | before-after | carousel | stat | quote | phone
  format     9:16 (default) | 1:1 | 4:5 | 16:9
  platform   cross (default) | tiktok | reels | shorts | none   (safe zones, 9:16 only)
  style / theme / accent     palette from styles.py (default noir/dark) + optional highlight hex
  title, kicker, handle, mode, align, progress (true), loop (true), fps (30)
  beats      [{text, duration?, kind?, ...template fields}]   kind "end" = shared CTA card
  background image path (optional, ken-burns behind everything)
  screen     image path or {"terminal": [...], "title": "..."}   (phone template)
  narration  {"timeline": "timeline.json", "audio": "narration.wav"}  (optional)
Paths are resolved relative to the spec file. Media is inlined as data URIs.
"""
from __future__ import annotations

import base64
import colorsys
import json
import subprocess
from pathlib import Path

from . import showcase, styles

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates" / "reel"
TEMPLATES = ("kinetic", "pov", "countdown", "before-after", "carousel", "stat", "quote", "phone")
FORMATS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}

# 9:16 safe zones in px (top, right, bottom, left) on 1080x1920. Sources (checked 2026-11):
# vidova.ai, revid.ai/tiktok-safe-zone, solidlabs.com/social-safe-zones. Production guides,
# not platform guarantees; "cross" is the organic-post union with the right action rail.
SAFE_916 = {
    "tiktok": (220, 140, 480, 60),
    "reels": (250, 120, 560, 65),
    "shorts": (260, 180, 560, 50),
    "cross": (250, 170, 560, 80),
    "none": (72, 72, 72, 72),
}
FEED_MARGIN = {"1:1": 80, "4:5": 80, "16:9": 96}

DEFAULT_BEAT = {"kinetic": 1.8, "pov": 1.7, "countdown": 3.0, "before-after": 2.6, "carousel": 2.9,
                "stat": 3.2, "quote": 5.0, "phone": 2.8}
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif", ".svg": "image/svg+xml"}
OUTPUTS = ("index.html", "reel.mp4", "poster.png", "preview.gif")


class ReelError(ValueError):
    pass


def safe_zone(fmt: str, platform: str = "cross") -> dict:
    if fmt == "9:16":
        if platform not in SAFE_916:
            raise ReelError(f"unknown platform {platform!r}; one of {', '.join(SAFE_916)}")
        t, r, b, l = SAFE_916[platform]
    else:
        t = r = b = l = FEED_MARGIN[fmt]
    return {"t": t, "r": r, "b": b, "l": l}


def _media(path, base: Path) -> str:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = base / p
    if not p.is_file():
        raise ReelError(f"media not found: {p}")
    mime = MEDIA_TYPES.get(p.suffix.lower())
    if not mime:
        raise ReelError(f"unsupported media type {p.suffix} (images only: {', '.join(MEDIA_TYPES)})")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _sat(hexc: str) -> float:
    r, g, b = (c / 255 for c in styles._hex(hexc))
    return colorsys.rgb_to_hls(r, g, b)[2]


def palette(style: str = "noir", theme: str | None = None, accent: str | None = None) -> dict:
    st = styles.build_style(style)
    mode = theme or st.get("default_theme", "dark")
    if mode not in st["palettes"]:
        mode = next(iter(st["palettes"]))
    pal = st["palettes"][mode]
    hi = accent or (pal["accent"] if _sat(pal["accent"]) > 0.25 else pal.get("atRisk", "#f2b544"))
    hi = styles.ensure_contrast(hi, pal["bg"], 4.5)
    hi2 = pal.get("system", styles.mix(hi, pal["bg"], 0.4))
    return {"pal": pal, "hi": hi, "hi2": hi2, "onhi": styles._on(hi), "font": st["font"], "mono": st["mono"],
            "radius": float(st.get("radius", 10)), "mode": mode, "style": st["name"]}


def _word_times(text: str, start: float, speech: float) -> list[dict]:
    words = [w for w in text.replace("*", " * ").split() if w != "*"]
    total = sum(len(w) + 2 for w in words) or 1
    out, c = [], start
    for w in words:
        d = speech * (len(w) + 2) / total
        out.append({"w": w, "s": round(c, 3), "e": round(c + d, 3)})
        c += d
    return out


def timed_beats(template: str, beats: list[dict], timeline: dict | None = None) -> list[dict]:
    """Give every beat absolute start/end. Narration slides (in order) win over durations."""
    slides = (timeline or {}).get("slides") or []
    out, cursor = [], 0.0
    for i, b in enumerate(beats):
        b = dict(b)
        if i < len(slides):
            s = slides[i]
            b["start"], b["end"] = float(s["start"]), float(s["end"])
            if "words" not in b and b.get("text"):
                b["words"] = _word_times(b["text"], b["start"], float(s.get("speech_duration") or (b["end"] - b["start"])))
        else:
            d = b.get("duration")
            if d is None:
                if b.get("kind") == "end":
                    d = 2.6
                elif template == "quote":
                    d = max(4.0, 0.34 * len(str(b.get("text", "")).split()) + 2.4)
                elif template == "before-after" and i == 1:
                    d = 4.2
                else:
                    d = DEFAULT_BEAT[template]
            d = float(d)
            if not 0.3 <= d <= 60:
                raise ReelError(f"beat {i + 1}: duration {d} out of range 0.3..60")
            b["start"], b["end"] = cursor, cursor + d
        cursor = b["end"]
        out.append(b)
    if out:
        out[-1]["last"] = True
    return out


def validate(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise ReelError("spec must be a JSON object")
    t = spec.get("template")
    if t not in TEMPLATES:
        raise ReelError(f"template must be one of {', '.join(TEMPLATES)}")
    if spec.get("format", "9:16") not in FORMATS:
        raise ReelError(f"format must be one of {', '.join(FORMATS)}")
    beats = spec.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ReelError("beats must be a non-empty list")
    if not all(isinstance(b, dict) for b in beats):
        raise ReelError("every beat must be an object")
    content = [b for b in beats if b.get("kind") != "end"]
    if not content:
        raise ReelError("need at least one non-end beat")
    for i, b in enumerate(beats, 1):
        if b.get("kind") == "end" and not b.get("text"):
            raise ReelError(f"beat {i}: end card needs text")
    need = {"kinetic": "text", "pov": "text", "countdown": "title", "carousel": None, "stat": "value", "quote": "text", "phone": None}
    for i, b in enumerate(content, 1):
        key = need.get(t)
        if key and not str(b.get(key, "")).strip():
            raise ReelError(f"{t} beat {i} needs {key!r}")
        if t == "carousel" and not (b.get("title") or b.get("text")):
            raise ReelError(f"carousel beat {i} needs title or text")
    if t == "before-after" and len(content) < 2:
        raise ReelError("before-after needs a before beat and an after beat")
    if spec.get("fps", 30) not in (24, 25, 30, 60):
        raise ReelError("fps must be 24, 25, 30 or 60")


def build(spec: dict, base: Path, *, fmt=None, platform=None, style=None, theme=None,
          show_safe=False, timeline=None) -> dict:
    """Resolve a spec into the page model embedded in index.html."""
    validate(spec)
    fmt = fmt or spec.get("format", "9:16")
    if fmt not in FORMATS:
        raise ReelError(f"format must be one of {', '.join(FORMATS)}")
    W, H = FORMATS[fmt]
    look = palette(style or spec.get("style", "noir"), theme or spec.get("theme"), spec.get("accent"))
    beats = []
    for b in spec["beats"]:
        b = dict(b)
        if b.get("media"):
            b["media"] = _media(b["media"], base)
        beats.append(b)
    beats = timed_beats(spec["template"], beats, timeline)
    duration = round(max(b["end"] for b in beats), 3)
    if timeline and timeline.get("total_duration"):
        duration = max(duration, float(timeline["total_duration"]))
    screen = spec.get("screen")
    if isinstance(screen, str):
        screen = _media(screen, base)
    model = {
        "template": spec["template"], "format": fmt, "W": W, "H": H, "u": min(W, H) / 1080,
        "safe": safe_zone(fmt, platform or spec.get("platform", "cross")), "duration": duration,
        "beats": beats, "title": spec.get("title"), "kicker": spec.get("kicker"), "handle": spec.get("handle"),
        "mode": spec.get("mode"), "align": spec.get("align"), "progress": bool(spec.get("progress", True)),
        "loop": bool(spec.get("loop", True)), "showSafe": bool(show_safe), "fps": int(spec.get("fps", 30)),
        "background": _media(spec["background"], base) if spec.get("background") else None,
        "screen": screen, **look,
    }
    return model


def render_html(model: dict) -> str:
    css = (TEMPLATE_DIR / "reel.css").read_text(encoding="utf-8")
    tpl = (TEMPLATE_DIR / f"{model['template']}.js").read_text(encoding="utf-8")
    rt = (TEMPLATE_DIR / "runtime.js").read_text(encoding="utf-8")
    data = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
            f"<meta name=\"viewport\" content=\"width={model['W']}\">\n"
            f"<title>reel · {model['template']} · {model['format']}</title>\n<style>{css}</style></head>\n"
            f"<body><script>window.__SPEC={data};</script>\n<script>{tpl}</script>\n<script>{rt}</script>\n</body></html>\n")


def _resolve(p, base: Path) -> Path:
    p = Path(p).expanduser()
    return p if p.is_absolute() else (base / p)


def _ff(*cmd):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *cmd], check=True)


def make(spec_path, out_dir, *, fmt=None, platform=None, style=None, theme=None, show_safe=False,
         gif=False, html_only=False, timeline_path=None, audio_path=None, fps=None, log=print) -> dict:
    spec_path = Path(spec_path).expanduser().resolve()
    if not spec_path.is_file():
        raise ReelError(f"no such spec: {spec_path}")
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReelError(f"spec is not valid JSON: {e}") from e
    base = spec_path.parent
    narr = spec.get("narration") or {}
    tl_path = Path(timeline_path).expanduser().resolve() if timeline_path else (_resolve(narr["timeline"], base) if narr.get("timeline") else None)
    au_path = Path(audio_path).expanduser().resolve() if audio_path else (_resolve(narr["audio"], base) if narr.get("audio") else None)
    timeline = None
    if tl_path:
        if not tl_path.is_file():
            raise ReelError(f"timeline not found: {tl_path}")
        timeline = json.loads(tl_path.read_text(encoding="utf-8"))
    if au_path and not au_path.is_file():
        raise ReelError(f"audio not found: {au_path}")
    if fps:
        spec["fps"] = fps
    model = build(spec, base, fmt=fmt, platform=platform, style=style, theme=theme,
                  show_safe=show_safe, timeline=timeline)

    out = Path(out_dir).expanduser().resolve()
    clash = [n for n in OUTPUTS if (out / n).exists()]
    if clash:
        raise ReelError(f"refusing to overwrite {out / clash[0]}")
    out.mkdir(parents=True, exist_ok=True)
    html = out / "index.html"
    with html.open("x", encoding="utf-8") as f:
        f.write(render_html(model))
    result = {"html": str(html), "template": model["template"], "format": model["format"],
              "size": [model["W"], model["H"]], "duration": model["duration"], "fps": model["fps"],
              "safe": model["safe"], "style": model["style"], "beats": len(model["beats"])}
    if html_only:
        return result

    video = out / "reel.mp4"
    silent = out / ".reel-silent.mp4" if au_path else video
    log(f"recording {model['template']} {model['W']}x{model['H']} {model['duration']}s @ {model['fps']}fps")
    showcase.record(html, silent, width=model["W"], height=model["H"], fps=model["fps"],
                    seconds=model["duration"], log=log)
    if au_path:
        _ff("-i", str(silent), "-i", str(au_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-t", f"{model['duration']}",
            "-movflags", "+faststart", str(video))
        silent.unlink()
        result["audio"] = str(au_path)
    result["video"] = str(video)
    first = next(b for b in model["beats"] if b.get("kind") != "end")
    at = min(model["duration"] - 0.1, first["start"] + max(0.9, (first["end"] - first["start"]) * 0.85))
    result["poster"] = showcase.poster(video, out / "poster.png", at=at)
    if gif:
        # Grain + gradients balloon GIFs; denoise and diff-mode palettes keep ~10 s near 2 MB.
        w = 320 if model["W"] <= model["H"] else 480
        _ff("-i", str(video), "-vf", f"fps=10,scale={w}:-2:flags=lanczos,hqdn3d=4:4:6:6,split[a][b];"
            "[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            "-loop", "0", str(out / "preview.gif"))
        result["gif"] = str(out / "preview.gif")
    return result


def add_arguments(p) -> None:
    p.add_argument("--spec", required=True, help="Reel spec JSON (see docs/REEL.md, examples/reel/)")
    p.add_argument("--output", required=True, help="New output directory (index.html, reel.mp4, poster.png)")
    p.add_argument("--format", choices=list(FORMATS), help="Override spec format (default 9:16)")
    p.add_argument("--platform", choices=list(SAFE_916), help="Safe-zone profile for 9:16 (default cross)")
    p.add_argument("--style", help="Palette from `creator.py style list` (default noir)")
    p.add_argument("--theme", choices=["dark", "light"], help="Palette theme")
    p.add_argument("--safe-zones", action="store_true", help="Draw platform UI safe zones over the video (review aid)")
    p.add_argument("--gif", action="store_true", help="Also write preview.gif (10 fps, 320 px wide; 480 for 16:9)")
    p.add_argument("--html-only", action="store_true", help="Write index.html only (open index.html#play to preview)")
    p.add_argument("--timeline", help="Narration timeline.json (from `creator.py narrate`); beats follow its slides")
    p.add_argument("--audio", help="Audio to mux into reel.mp4 (e.g. narration.wav)")
    p.add_argument("--fps", type=int, choices=[24, 25, 30, 60], help="Frame rate (default 30)")


def run(args) -> dict:
    return make(args.spec, args.output, fmt=args.format, platform=args.platform, style=args.style,
                theme=args.theme, show_safe=args.safe_zones, gif=args.gif, html_only=args.html_only,
                timeline_path=args.timeline, audio_path=args.audio, fps=args.fps)


def templates() -> list[str]:
    return list(TEMPLATES)


__all__ = ["add_arguments", "run", "make", "build", "render_html", "safe_zone", "timed_beats", "ReelError", "TEMPLATES", "FORMATS"]
