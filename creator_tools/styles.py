"""Style library: DESIGN.md brand systems -> render-ready palettes.

Reads the vendored VoltAgent/awesome-design-md files (integrations/design-md/,
pinned in integrations/design-md-lock.json) and maps each file's YAML
``colors`` / ``typography`` / ``rounded`` tokens onto one neutral palette
contract that renderers consume (Mission Control first).

Rules this module keeps:
  * Domain colours (severity, watcher kinds) are NOT replaced by a brand.
    Severity meaning outranks brand consistency; only contrast is adjusted.
  * Every text role is pushed to WCAG contrast (4.5:1 body, 3:1 faint/large)
    against its own surface, so a brand palette cannot ship unreadable text.
  * Custom brand fonts are not bundled. The brand family is listed first and
    the system stack follows, so output stays offline and readable.
  * Stdlib only; no YAML dependency (frontmatter is parsed narrowly).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "integrations" / "design-md"
LOCK = ROOT / "integrations" / "design-md-lock.json"

SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'

# Domain semantics kept from Mission Control (contrast-adjusted per surface).
SEMANTIC = {
    "dark": {"critical": "#ff5263", "concerning": "#ff914d", "atRisk": "#f2b544", "stable": "#6ea8ff",
             "model": "#f0b94a", "human": "#ff4f9a", "system": "#a98bff"},
    "light": {"critical": "#d92535", "concerning": "#c9500b", "atRisk": "#9a6200", "stable": "#2563eb",
              "model": "#8a5a00", "human": "#b62e78", "system": "#6e42bb"},
}


class StyleError(ValueError):
    pass


# ---------- colour maths ----------
def _hex(c: str) -> tuple[int, int, int]:
    c = c.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) == 8:
        c = c[:6]
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        raise StyleError(f"bad colour {c!r}")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def _lum(c: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _hex(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _hex(a), _hex(b)
    return _to_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def ensure_contrast(fg: str, bg: str, target: float) -> str:
    """Move fg toward white or black until it reaches target contrast on bg."""
    if contrast(fg, bg) >= target:
        return fg
    pole = "#ffffff" if _lum(bg) < 0.4 else "#000000"
    for i in range(1, 41):
        cand = mix(fg, pole, i / 40)
        if contrast(cand, bg) >= target:
            return cand
    return pole


# ---------- DESIGN.md parsing ----------
def _frontmatter(text: str) -> str | None:
    m = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    return m.group(1) if m else None


def _block(fm: str, name: str) -> list[str]:
    out, inside = [], False
    for line in fm.splitlines():
        if re.match(rf"^{re.escape(name)}:\s*$", line):
            inside = True
            continue
        if inside:
            if line and not line.startswith((" ", "\t")):
                break
            out.append(line)
    return out


def parse_design_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    if fm is None:
        raise StyleError(f"{path.parent.name}: no YAML frontmatter tokens")
    colors = {}
    for line in _block(fm, "colors"):
        m = re.match(r'^\s+([\w.-]+):\s*["\']?(#[0-9a-fA-F]{3,8})', line)
        if m:
            colors[m.group(1)] = m.group(2)
    fonts = []
    for line in _block(fm, "typography"):
        m = re.match(r"^\s+fontFamily:\s*[\"']?([^\"'\n]+)", line)
        if m and m.group(1).strip() not in fonts:
            fonts.append(m.group(1).strip())
    radius = {}
    for line in _block(fm, "rounded"):
        m = re.match(r"^\s+([\w-]+):\s*[\"']?(\d+(?:\.\d+)?)px", line)
        if m:
            radius[m.group(1)] = float(m.group(2))
    desc = ""
    m = re.search(r'^description:\s*"(.*?)"\s*$', fm, re.M)
    if m:
        desc = m.group(1)
    for need in ("primary", "ink"):
        if need not in colors:
            raise StyleError(f"{path.parent.name}: missing colors.{need}")
    return {"colors": colors, "fonts": fonts, "radius": radius, "description": desc}


def _first(c: dict, *keys):
    for k in keys:
        if k in c:
            return c[k]
    return None


def _font_stack(fam: str | None, base: str) -> str:
    if not fam:
        return base
    fam = fam.split(",")[0].strip()
    if fam.lower() in ("inherit", "system-ui", "sans-serif", "monospace"):
        return base
    return f'"{fam}", {base}'


def _fit_text(fg: str, surfaces: list[str], target: float) -> str:
    """Adjust fg until it meets target on every surface it is drawn on."""
    for _ in range(4):
        for bg in surfaces:
            fg = ensure_contrast(fg, bg, target)
        if all(contrast(fg, bg) >= target for bg in surfaces):
            return fg
    return fg


def _on(fill: str) -> str:
    """Readable label colour for text on a solid fill."""
    return "#ffffff" if contrast("#ffffff", fill) >= contrast("#0b0f17", fill) else "#0b0f17"


def finalize(mode: str, pal: dict) -> dict:
    """Make every text-bearing role meet WCAG AA on every surface it sits on.

    Text roles: ink, muted, faint, accent and the semantic colours (used for
    tags/legend labels). Surfaces: panel, surface, raised, and the accent tint
    used by active buttons. Hue is kept; only lightness moves.
    """
    pal = dict(pal)
    # A mid-tone brand surface can make AA impossible for one text colour on all
    # surfaces. Pull secondary surfaces toward the panel until ink can clear 7:1.
    pole = "#ffffff" if mode == "dark" else "#000000"
    for key in ("raised", "bg", "surface"):
        for _ in range(8):
            if contrast(pole, pal[key]) >= 9.0:
                break
            pal[key] = mix(pal[key], pal["panel"], 0.35)
    surfaces = [pal["panel"], pal["surface"], pal["raised"], pal["bg"]]
    pal["ink"] = _fit_text(pal["ink"], surfaces, 7.0)
    for k in ("muted", "faint"):
        pal[k] = _fit_text(pal[k], surfaces, 4.6)
    # Active buttons / brand marks put accent text on a ~16% accent tint; test 22%.
    tint = mix(pal["panel"], pal["accent"], 0.22)
    pal["accent"] = _fit_text(pal["accent"], surfaces + [tint], 4.6)
    pal["accent"] = _fit_text(pal["accent"], surfaces + [mix(pal["panel"], pal["accent"], 0.22)], 4.6)
    for k in ("critical", "concerning", "atRisk", "stable", "model", "human", "system"):
        if k in pal:
            # Severity pills draw the colour as text on its own ~14% tint.
            pal[k] = _fit_text(pal[k], surfaces, 4.6)
            pal[k] = _fit_text(pal[k], surfaces + [mix(pal["panel"], pal[k], 0.2)], 4.6)
    pal["onStable"] = _on(pal["stable"])
    pal["onAccent"] = _on(pal["accent"])
    return pal


def _theme(mode: str, bg: str, panel: str, raised: str, ink: str, muted: str | None,
           border: str | None, accent: str) -> dict:
    surface = mix(bg, "#000000" if mode == "dark" else "#ffffff", 0.35)
    muted = muted or mix(ink, panel, 0.35)
    faint = mix(muted, panel, 0.25)
    border = border or mix(ink, panel, 0.85)
    if contrast(border, panel) < 1.25:
        border = mix(border, ink, 0.18)
    pal = {
        "bg": bg, "panel": panel, "surface": surface, "raised": raised,
        "ink": ink, "muted": muted, "faint": faint, "border": border,
        "grid": mix(border, panel, 0.2), "accent": accent,
        "outline": "#ffffff", "idle": mix(border, panel, 0.1),
    }
    pal.update(SEMANTIC[mode])
    return finalize(mode, pal)


# Mission Control's own palette, as a built-in style (same hexes as the template).
NATIVE = {
    "dark": {"bg": "#0b1422", "panel": "#121d2f", "surface": "#080d18", "raised": "#17253b", "ink": "#f1f5fa",
             "muted": "#acbcd0", "faint": "#7d8fa6", "border": "#28374e", "grid": "#253248", "accent": "#55c9df",
             "outline": "#ffffff", "idle": "#262434", **SEMANTIC["dark"]},
    "light": {"bg": "#edf2f7", "panel": "#ffffff", "surface": "#f8fafc", "raised": "#e8eff7", "ink": "#142338",
              "muted": "#4a5b70", "faint": "#64768c", "border": "#c6d2df", "grid": "#b8c8d9", "accent": "#087f99",
              "outline": "#ffffff", "idle": "#c6d2df", **SEMANTIC["light"]},
}


def native_style() -> dict:
    return {"name": "mission-control", "default_theme": "dark", "description": "Mission Control v3 native palette, contrast-finalized",
            "font": SANS, "mono": MONO, "radius": 8.0,
            "palettes": {m: finalize(m, p) for m, p in NATIVE.items()},
            "source": "creator_tools/styles.py:NATIVE"}


# Built-in "noir": restrained developer-product look (studied from herdr.dev,
# 2026-11). Near-black + white + greys, no brand hue; hierarchy by brightness.
# Accent is near-white so the primary action is the brightest thing on screen.
NOIR = {
    "dark": {"bg": "#0e0f11", "panel": "#131518", "surface": "#0a0b0d", "raised": "#1b1d21", "ink": "#f3f3f4",
             "muted": "#a3a6ad", "faint": "#8a8e96", "border": "#2c2e31", "grid": "#202226", "accent": "#f3f3f4",
             "outline": "#ffffff", "idle": "#24262a", **SEMANTIC["dark"]},
    "light": {"bg": "#f4f4f5", "panel": "#ffffff", "surface": "#fafafa", "raised": "#ececee", "ink": "#0e0f11",
              "muted": "#4d5057", "faint": "#5d6168", "border": "#dcdde0", "grid": "#e4e5e8", "accent": "#0e0f11",
              "outline": "#ffffff", "idle": "#dcdde0", **SEMANTIC["light"]},
}
BUILTINS = ("mission-control", "noir")


def noir_style() -> dict:
    return {"name": "noir", "default_theme": "dark",
            "description": "Restrained developer-product look: near-black, no brand hue, brightness-tier text, Geist + mono",
            "font": f'"Geist", "Inter", {SANS}', "mono": f'"JetBrains Mono", {MONO}', "radius": 10.0,
            "palettes": {m: finalize(m, p) for m, p in NOIR.items()},
            "source": "creator_tools/styles.py:NOIR (studied from herdr.dev)"}


def build_style(name: str) -> dict:
    if name == "mission-control":
        return native_style()
    if name == "noir":
        return noir_style()
    path = LIBRARY / name / "DESIGN.md"
    if not path.is_file():
        raise StyleError(f"unknown style {name!r}; run `creator.py style list`")
    t = parse_design_md(path)
    c = t["colors"]
    primary, ink = c["primary"], c["ink"]
    canvas = _first(c, "canvas", "surface", "background") or "#ffffff"
    brand_dark = _lum(canvas) < 0.2

    # Accent: a near-neutral primary (Vercel/SpaceX black) is not an accent.
    accent = primary
    if contrast(primary, canvas) < 1.6 or _is_neutral(primary):
        accent = _first(c, "link", "accent-blue", "accent", "brand", "primary-deep") or primary
        if _is_neutral(accent):
            accent = "#4f8cff"

    if brand_dark:
        dbg = canvas
        dpanel = _first(c, "surface-1", "surface-card", "surface", "canvas-soft", "surface-soft") or mix(canvas, ink, 0.05)
        draised = _first(c, "surface-2", "surface-elevated", "surface-strong") or mix(dpanel, ink, 0.05)
        dark = _theme("dark", dbg, dpanel, draised, ink, _first(c, "ink-muted", "muted", "mute", "body"),
                      _first(c, "hairline", "hairline-strong"), accent)
        lbg = _first(c, "inverse-canvas", "on-dark") or "#f4f6f8"
        light = _theme("light", mix(lbg, "#e9edf2", 0.4), "#ffffff", mix(lbg, "#dfe5ec", 0.5),
                       _first(c, "inverse-ink") or "#111418", None, None, accent)
    else:
        lpanel = _first(c, "surface-card", "surface-1", "surface") or "#ffffff"
        lbg = _first(c, "canvas-soft", "surface-soft") or mix(canvas, ink, 0.04)
        light = _theme("light", lbg, lpanel if _lum(lpanel) > 0.6 else canvas,
                       _first(c, "surface-strong", "surface-soft") or mix(canvas, ink, 0.07),
                       ink, _first(c, "muted", "ink-muted", "mute", "body", "stone"),
                       _first(c, "hairline", "hairline-soft"), accent)
        dsrc = _first(c, "surface-dark", "charcoal", "ink-deep", "surface-dark-elevated") or ink
        dbg = dsrc if _lum(dsrc) < 0.03 else mix(dsrc, "#000000", 0.7)
        dark = _theme("dark", dbg, mix(dbg, "#ffffff", 0.05), mix(dbg, "#ffffff", 0.09),
                      _first(c, "on-dark", "on-primary") or "#f2f4f7",
                      _first(c, "on-dark-soft"), None, accent)

    r = t["radius"]
    radius = r.get("md") or r.get("lg") or r.get("sm") or 8.0
    fonts = t["fonts"]
    mono = next((f for f in fonts if "mono" in f.lower()), None)
    sans = next((f for f in fonts if "mono" not in f.lower()), None)
    return {
        "name": name,
        "default_theme": "dark" if brand_dark else "light",
        "description": t["description"],
        "font": _font_stack(sans, SANS),
        "mono": _font_stack(mono, MONO),
        "radius": max(0.0, min(radius, 18.0)),
        "palettes": {"dark": dark, "light": light},
        "source": f"integrations/design-md/{name}/DESIGN.md",
    }


def _is_neutral(c: str) -> bool:
    r, g, b = _hex(c)
    return max(r, g, b) - min(r, g, b) < 18


def list_styles() -> list[dict]:
    out = [{"name": n, "builtin": True, "default_theme": build_style(n)["default_theme"],
             "accent": build_style(n)["palettes"][build_style(n)["default_theme"]]["accent"]} for n in BUILTINS]
    for d in sorted(p for p in LIBRARY.iterdir() if p.is_dir()):
        try:
            s = build_style(d.name)
            out.append({"name": d.name, "default_theme": s["default_theme"],
                        "accent": s["palettes"][s["default_theme"]]["accent"]})
        except StyleError as e:
            out.append({"name": d.name, "unsupported": str(e)})
    return out


def style_css(style: dict, prefix: str = "--mc-") -> str:
    """CSS custom-property block for both themes plus font/radius tokens."""
    def block(sel, pal):
        body = "".join(f"  {prefix}{k}: {v};\n" for k, v in pal.items())
        return f"{sel} {{\n{body}}}\n"
    return (
        block(':root, [data-theme="dark"]', style["palettes"]["dark"])
        + block('[data-theme="light"]', style["palettes"]["light"])
        + f":root {{ {prefix}font: {style['font']}; {prefix}mono: {style['mono']}; {prefix}radius: {style['radius']:g}px; }}\n"
    )


def run(action: str, name: str | None = None) -> dict:
    lock = json.loads(LOCK.read_text())
    if action == "list":
        items = list_styles()
        return {"ok": True, "source": lock["source"], "commit": lock["commit"],
                "supported": sum(1 for i in items if "unsupported" not in i), "styles": items}
    if action == "show":
        if name in BUILTINS:
            return {"ok": True, **build_style(name)}
        if not name:
            raise StyleError("show requires --style")
        return {"ok": True, **build_style(name)}
    raise StyleError("choose list or show")
