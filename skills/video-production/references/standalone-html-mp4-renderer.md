# Standalone HTML→MP4 renderer (no HyperFrames, no paid hosted tool)

A ~60-line Playwright + ffmpeg renderer that produces the same class of output as
a hosted animation tool. Built and verified end-to-end in a real session
(1920×1080 h264+aac, exact frame counts, narration synced).

**Use this instead of the HyperFrames chain when:**
- You want full control of the design and don't need captions/transitions tooling
- You're re-cutting an EXISTING production's visuals against narration you already have
- The scene count is small (≤8) and per-frame subagent delegation is overkill
- Output must be scriptable/regenerable in CI

**Keep using HyperFrames when:** you need burned-in karaoke captions, the
transitions injector, the lint/check gates, or the multi-worker frame pipeline.

Reference implementation: write your own `render.js` from the skeleton below, or use `python3.13 creator.py showcase`, whose frame-exact contract is `window.__ready` + `window.__advance(ms)` + optional `window.__done()` (see `docs/SHOWCASE.md`). `creator.py motion create` scaffolds a GSAP composition that already implements it (`docs/GSAP.md`).
Keep helper scripts (`render.js`, an SRT-to-timeline script, a GIF script) in
`productions/<project>/` so the production folder stays self-contained.

## Core idea — step a virtual clock, do NOT screen-record

Screen recording drops frames and drifts. Instead: load the page, then per frame
call `window.seek(t)`, screenshot, pipe the PNG to ffmpeg. Rendering can take as
long as it needs; output timing is exact.

Scene contract is two globals:

```js
window.DURATION = 58.31;   // seconds
window.seek = function(t){ /* derive ALL visual state purely from t */ };
```

`seek` must be **pure** — never accumulate state between calls. That purity is
what makes `nb_frames == round(DURATION*fps)` hold exactly.

## Renderer skeleton

```js
const { chromium } = require('playwright');
const ff = spawn('ffmpeg', ['-y','-f','image2pipe','-framerate',String(fps),'-i','-',
  '-c:v','libx264','-pix_fmt','yuv420p','-crf','16','-preset','medium',
  '-movflags','+faststart', out]);

const browser = await chromium.launch({ args:['--force-color-profile=srgb','--disable-lcd-text'] });
const page = await browser.newPage({ viewport:{ width:W, height:H }, deviceScaleFactor:1 });
await page.setViewportSize({ width:W, height:H });          // see pitfall 1
await page.goto('file://'+path.resolve(input), { waitUntil:'networkidle' });
await page.evaluate(() => document.fonts && document.fonts.ready);  // else frame 1 uses fallback font

for (let f = 0; f < total; f++) {
  await page.evaluate(tt => window.seek(tt), f/fps);
  const buf = await page.screenshot({ type:'png' });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));  // backpressure
}
ff.stdin.end();
```

## PITFALLS (hit for real)

1. **`viewportSize` is NOT a valid `newPage` option.** `newPage({ viewportSize:{...} })`
   is silently ignored → you get the 1280×720 default. The render *succeeds* and
   the design still looks fine in a thumbnail, so this hides. Use `viewport:` and
   follow with an explicit `setViewportSize`.
2. **A fixed 1080px-tall body inside a short viewport pins content to the bottom
   of frame.** Same root cause as (1); the symptom looks like a CSS bug and isn't.
3. **Always `ffprobe` after every render** — `width`, `height`, `nb_frames`,
   `duration`. Expect `nb_frames == round(DURATION*fps)`. This is the check that
   caught the 720p bug; eyeballing a scaled screenshot did not.
4. Without the `drain` await, long renders stall or drop frames.

## Re-cutting visuals against narration you ALREADY have

Do **not** regenerate voice just to change visuals. A prior production's
`audio_meta.json` carries per-line `duration_s`; cumulative sums are your scene
boundaries. Key the `SCENES` array to them, then:

```bash
ffmpeg -f concat -safe 0 -i list.txt -c:a pcm_s16le narration.wav
ffmpeg -i silent.mp4 -i narration.wav -c:v copy -c:a aac -b:a 192k -shortest video.mp4
```

Gate: `ffprobe` must show **both** an h264 and an aac stream.

## SRT → named scene timeline

An SRT-to-timeline script should group captions on pauses > `--gap` seconds so scene boundaries
land on natural breaths, and emit a `SCENES` array with names + durations.
Named scenes are the revision handle — address a fix as "move `conversation` to
bottom center", not "the fourth shot".

## GIF export (slides / Teams / README)

Two-pass palette; single-pass banding is obvious.

```bash
ffmpeg -i in.mp4 -vf "fps=15,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" pal.png
ffmpeg -i in.mp4 -i pal.png -lavfi "fps=15,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" out.gif
```

## Honest trade-off

A hosted design tool wins on **taste per minute** — it makes design decisions you
would otherwise have to specify. This renders exactly what you wrote; the design
judgment is yours. For a one-off pretty animation, hosted is faster. For branded
demo assets regenerated often, version-controlled, and fully offline (no customer
data leaving the machine — matters for regulated work), this wins.
