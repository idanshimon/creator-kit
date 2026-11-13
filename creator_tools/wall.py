"""Living wall: a hero of past work as slowly scrolling columns.

Pattern studied from herdr.dev (2026-11): columns of 16:10 tiles drift up/down
in opposite directions, a left-side shade keeps the headline readable, hover or
keyboard focus pauses a column, click opens a blurred lightbox.

Rules:
  * Offline: assets are copied next to index.html; no CDN, no fonts fetched.
  * Never overwrites an existing output directory.
  * Motion is driven by one clock (t ms) so `creator.py showcase` can record it
    frame-exactly via window.__ready / __advance / __done; live view uses rAF.
  * prefers-reduced-motion stops the drift.
  * Stats are only what the caller passes (or derived counts); none invented.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from creator_tools import styles

IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
VID = {".mp4", ".webm", ".mov"}


class WallError(ValueError):
    pass


def collect(src: Path) -> list[Path]:
    if not src.is_dir():
        raise WallError(f"--input must be a directory of images/videos: {src}")
    items = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in IMG | VID
                   and not any(part.startswith(".") for part in p.relative_to(src).parts))
    if len(items) < 3:
        raise WallError(f"need at least 3 images/videos in {src}, found {len(items)}")
    return items


def render(src, output, title: str, subtitle: str = "", cta_label: str = "", cta_href: str = "",
           stats: list[tuple[str, str]] | None = None, style_name: str = "noir", theme: str | None = None,
           columns: int = 4) -> dict:
    src, out = Path(src).expanduser(), Path(output).expanduser()
    if out.exists():
        raise WallError(f"refusing to overwrite existing {out}")
    if not title.strip() or "\n" in title:
        raise WallError("--title must be one non-empty line")
    if cta_href and not cta_href.startswith(("http://", "https://", "#", "./", "/")):
        raise WallError("--cta-href must be http(s), a #anchor or a relative path")
    items = collect(src)
    st = styles.build_style(style_name)
    mode = theme or st["default_theme"]
    columns = max(2, min(columns, 6))

    (out / "assets").mkdir(parents=True)
    tiles = []
    for i, p in enumerate(items):
        name = f"{i:03d}{p.suffix.lower()}"
        shutil.copy2(p, out / "assets" / name)
        tiles.append({"src": f"assets/{name}", "video": p.suffix.lower() in VID, "label": p.stem})

    # Split the title so the second half dims (brightness, not colour, carries hierarchy).
    # "First line | dimmed line" chooses the break; otherwise round the split up.
    if "|" in title:
        a, _, b = title.partition("|")
        head, tail = html.escape(a.strip()), html.escape(b.strip())
        title = f"{a.strip()} {b.strip()}"
    else:
        words = title.split()
        cut = max(1, (len(words) + 1) // 2)
        head = html.escape(" ".join(words[:cut]))
        tail = html.escape(" ".join(words[cut:]))
    stats = stats if stats is not None else [(str(len(items)), "pieces")]
    stat_html = "".join(f"<div><b>{html.escape(v)}</b><span>{html.escape(k)}</span></div>" for v, k in stats)
    cta = (f'<a class="btn" href="{html.escape(cta_href, quote=True)}">{html.escape(cta_label or "Open")}</a>'
           if cta_href else "")

    doc = TEMPLATE
    for k, v in {
        "__CSS__": styles.style_css(st, prefix="--w-"),
        "__THEME__": mode,
        "__TITLE_TEXT__": html.escape(title),
        "__HEAD__": head, "__TAIL__": tail,
        "__SUB__": html.escape(subtitle),
        "__CTA__": cta, "__STATS__": stat_html,
        "__TILES__": json.dumps(tiles).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"),
        "__COLS__": str(columns),
        "__SOURCE__": html.escape(st["source"]),
    }.items():
        doc = doc.replace(k, v)
    (out / "index.html").write_text(doc, encoding="utf-8")
    return {"ok": True, "output": str(out / "index.html"), "tiles": len(tiles), "style": st["name"],
            "theme": mode, "columns": columns}


TEMPLATE = r"""<!doctype html>
<html lang="en" data-theme="__THEME__">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE_TEXT__</title>
<!-- style: __SOURCE__ -->
<style>
__CSS__
*{box-sizing:border-box;margin:0}
html,body{height:100%;background:var(--w-bg);color:var(--w-ink);font-family:var(--w-font)}
.hero{position:relative;height:100vh;min-height:560px;overflow:hidden}
.wall{position:absolute;inset:-4% -4% -4% 40%;display:flex;gap:20px;transform:perspective(1600px) rotateY(-9deg) rotateX(4deg);transform-origin:left center}
.col{flex:1;display:flex;flex-direction:column;gap:20px;will-change:transform}
.tile{flex:0 0 auto;aspect-ratio:16/10;border-radius:var(--w-radius);overflow:hidden;cursor:zoom-in;padding:0;border:0;background:var(--w-raised);
  box-shadow:0 0 0 1px color-mix(in srgb,var(--w-ink) 10%,transparent),0 20px 50px -10px rgba(0,0,0,.6);transition:transform .25s cubic-bezier(.2,.8,.2,1)}
.tile:hover,.tile:focus-visible{transform:scale(1.03);outline:2px solid var(--w-ink);outline-offset:2px}
.tile img,.tile video{width:100%;height:100%;object-fit:cover;display:block}
.shade{position:absolute;inset:0;pointer-events:none;background:
  linear-gradient(90deg,var(--w-bg) 0%,var(--w-bg) 38%,color-mix(in srgb,var(--w-bg) 70%,transparent) 50%,color-mix(in srgb,var(--w-bg) 20%,transparent) 62%,transparent 72%),
  linear-gradient(180deg,var(--w-bg) 0,transparent 14%,transparent 86%,var(--w-bg) 100%)}
.copy{position:relative;z-index:2;max-width:640px;padding:18vh 0 0 clamp(24px,6vw,96px)}
h1{font-size:clamp(38px,5.2vw,68px);line-height:1.06;letter-spacing:-.035em;font-weight:650}
h1 .tail{display:block;color:var(--w-muted)}
.sub{margin-top:22px;font-size:18px;line-height:1.55;color:var(--w-muted);max-width:60ch}
.btn{display:inline-block;margin-top:28px;padding:12px 22px;border-radius:999px;background:var(--w-accent);color:var(--w-onAccent);text-decoration:none;font-weight:600;
  transition:transform .15s}
.btn:hover{transform:translateY(-1px)}
.stats{display:flex;gap:36px;margin-top:40px}
.stats b{display:block;font-size:30px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stats span{font-size:13px;color:var(--w-muted)}
.hint{position:absolute;right:24px;bottom:20px;z-index:2;font:12px var(--w-mono);color:var(--w-ink);background:color-mix(in srgb,var(--w-panel) 85%,transparent);backdrop-filter:blur(8px);border:1px solid var(--w-border);border-radius:999px;padding:6px 12px}
.toggle{position:absolute;top:18px;right:20px;z-index:3;background:color-mix(in srgb,var(--w-panel) 85%,transparent);backdrop-filter:blur(8px);color:var(--w-ink);border:1px solid var(--w-border);border-radius:999px;padding:6px 12px;font:13px var(--w-font);cursor:pointer}
[data-theme=light] .tile{box-shadow:0 0 0 1px var(--w-border),0 14px 30px -14px rgba(20,22,26,.25)}
.lightbox{position:fixed;inset:0;z-index:50;background:rgba(6,7,8,.92);backdrop-filter:blur(10px);display:none;place-items:center;padding:4vw}
.lightbox.open{display:grid;animation:lbin .35s cubic-bezier(.2,.8,.2,1)}
.lightbox img,.lightbox video{max-width:92vw;max-height:86vh;border-radius:var(--w-radius);box-shadow:0 30px 80px rgba(0,0,0,.7)}
.lightbox p{color:#e8e8ea;font:13px var(--w-mono);margin-top:12px;text-align:center}
@keyframes lbin{from{opacity:0;transform:translateY(6px)}}
@media (max-width:760px){.hero{min-height:760px}.wall{inset:auto -10% -6% -10%;height:44%;transform:none}.copy{padding-top:9vh}
  .shade{background:linear-gradient(180deg,var(--w-bg) 0%,var(--w-bg) 56%,color-mix(in srgb,var(--w-bg) 30%,transparent) 66%,transparent 76%)}.stats{gap:24px;margin-top:28px}}
@media (prefers-reduced-motion:reduce){.tile,.btn{transition:none}}
</style>
</head>
<body>
<header class="hero">
  <div class="wall" id="wall" aria-label="Gallery of work"></div>
  <div class="shade"></div>
  <button class="toggle" id="theme" type="button"></button>
  <div class="copy">
    <h1><span>__HEAD__</span> <span class="tail">__TAIL__</span></h1>
    <p class="sub">__SUB__</p>
    __CTA__
    <div class="stats">__STATS__</div>
  </div>
  <div class="hint">Click any tile ↗</div>
</header>
<div class="lightbox" id="lb" role="dialog" aria-modal="true" aria-label="Preview"><div id="lbBody"></div></div>
<script>
(()=>{
const TILES=__TILES__, COLS=__COLS__;
const wall=document.getElementById('wall');
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const cols=[];
for(let c=0;c<COLS;c++){
  const el=document.createElement('div');el.className='col';
  const mine=TILES.filter((_,i)=>i%COLS===c); const set=mine.length?mine:TILES;
  for(const pass of [0,1]) for(const t of set){            // doubled list = seamless loop
    const b=document.createElement('button');b.className='tile';b.type='button';
    b.setAttribute('aria-label',t.label);if(pass)b.tabIndex=-1,b.setAttribute('aria-hidden','true');
    const m=document.createElement(t.video?'video':'img');m.src=t.src;
    if(t.video){m.muted=true;m.loop=true;m.playsInline=true;m.autoplay=!window.__render;}else{m.alt='';m.loading='lazy';}
    b.appendChild(m);b.onclick=()=>open(t);el.appendChild(b);
  }
  el.dataset.dir=c%2?'down':'up';el.dataset.speed=String(0.018+0.004*(c%3)); // px per ms
  let paused=false;el.addEventListener('pointerenter',()=>paused=true);el.addEventListener('pointerleave',()=>paused=false);
  el.addEventListener('focusin',()=>paused=true);el.addEventListener('focusout',()=>paused=false);
  wall.appendChild(el);cols.push({el,get paused(){return paused},off:0});
}
function step(ms){for(const c of cols){if(c.paused&&!window.__render)continue;
  const half=c.el.scrollHeight/2; if(!half)continue; c.off=(c.off+ms*+c.el.dataset.speed)%half;
  const y=c.el.dataset.dir==='up'?-c.off:-(half-c.off); c.el.style.transform=`translateY(${y}px)`;}}
const lb=document.getElementById('lb'),body=document.getElementById('lbBody');let openedAt=0;
function open(t){body.innerHTML='';const m=document.createElement(t.video?'video':'img');m.src=t.src;if(t.video){m.controls=true;m.autoplay=true;}
  const p=document.createElement('p');p.textContent=t.label;body.append(m,p);lb.classList.add('open');openedAt=performance.now();}
lb.addEventListener('click',e=>{if(performance.now()-openedAt<450)return;if(e.target===lb||e.target===body)lb.classList.remove('open')});
addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('open')});
const tb=document.getElementById('theme');const root=document.documentElement;
const label=()=>tb.textContent=root.dataset.theme==='dark'?'Light':'Dark';label();
tb.onclick=()=>{root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';label()};
// showcase hooks (frame-exact recording); live view uses rAF.
window.__ready=true;window.__advance=ms=>{window.__render=true;step(ms)};window.__done=()=>false;
if(!reduce){let last=performance.now();const tick=n=>{if(!window.__render)step(Math.min(64,n-last));last=n;requestAnimationFrame(tick)};requestAnimationFrame(tick);}
})();
</script>
</body>
</html>
"""
