---
name: motion-graphics-renderer
description: Use when rendering HTML scenes to an exact-timed MP4.
---

# HTML → MP4 Motion Graphics (free, offline, deterministic)

Render HTML/CSS/JS scenes to MP4 by stepping a virtual clock frame by frame in a
headless browser and piping screenshots to ffmpeg. No subscription, no screen
recording, nothing uploaded — suitable for confidential material.

## When to use

- Branded explainer or demo video you regenerate as numbers change
- Product walkthrough with deliberate camera moves and callouts
- Exact timing synced to narration you already have
- Rendering an existing interactive HTML deck to video

Use HyperFrames (see the `video-production` skill) when you want its
storyboard/caption/transition pipeline. Use this when you want direct control.

## Kit commands

```bash
python3.13 creator.py motion doctor                      # verify the pinned local GSAP runtime
python3.13 creator.py motion create ...                  # new standalone GSAP composition (see --help, docs/GSAP.md)
python3.13 creator.py showcase --input page.html --output out.mp4 [--seconds 20] [--scale 2] [--poster p.png]
python3.13 creator.py design-check --input page.html     # contrast/overflow/offline/error gate
python3.13 creator.py narrate --script SCRIPT.md --output productions/<name>/narration --engine kokoro
```

`showcase` is frame-exact when the page implements `window.__ready = true`,
`window.__advance(ms)` (draws one frame) and optionally `window.__done()`;
otherwise `--realtime` takes wall-clock screenshots (not frame-exact). Compositions
from `motion create` already implement the contract. See `docs/SHOWCASE.md`.

## The core idea — never screen-record

If you write your own renderer, a scene exposes two globals:

```js
window.DURATION = 58.31;            // seconds
window.seek = function(t){ ... };   // paint the exact state at time t
```

The renderer loads the page, calls `seek(t)` per frame, screenshots, and pipes to
ffmpeg. Rendering can take minutes; output timing is exact. `seek` must be
**pure** — derive all state from `t`, never accumulate between calls. A ~60-line
Playwright skeleton is in
`../video-production/references/standalone-html-mp4-renderer.md`.

## Sync to real narration

Never guess scene lengths. Read the true per-line durations and make them the
scene windows (`creator.py narrate` writes them to `timeline.json`):

```bash
for f in narration/voice/*.wav; do ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"; done
```

Cumulative sums become `start`/`end`. Concatenate and mux:

```bash
ffmpeg -y -f concat -safe 0 -i cat.txt -ar 24000 -ac 1 -c:a pcm_s16le out/narration.wav
ffmpeg -y -i out/silent.mp4 -i out/narration.wav -c:v copy -c:a aac -b:a 192k -shortest out/video.mp4
```

**Gaps must match on both sides.** If you insert a gap between scene windows,
insert the same silence into the narration (`ffmpeg -f lavfi -i anullsrc=r=24000:cl=mono -t 0.35 …`),
or audio drifts by `gap × (lines-1)`. Confirm `ffprobe(narration.wav)` equals
`window.DURATION` exactly before muxing.

Narration engines: kokoro (free default), azure (`--allow-cloud`, with
`AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` or Entra inventory), and f5/qwen3/chatterbox
for local cloning from your own reference WAV (`--ref`). For professional work use
Azure DragonHD voices, cast per narrator; expect ~18% longer runtime than Kokoro
and rebuild the timeline. Details: `../video-production/references/azure-speech-narration.md`.

If you call HyperFrames' Kokoro TTS directly, set `HYPERFRAMES_PYTHON` to the venv
that has `kokoro-onnx`; without it every call fails while exiting 0. Check each
`.wav` is non-empty rather than trusting the exit code.

## Static decks: one still per slide

If slides are static (captured with animations disabled), every frame inside a
slide is identical. Capturing at 30 fps means ~10,000 screenshots and an hour for
a 6-minute cut. Instead capture one PNG per slide and let ffmpeg hold it:

```
file '/abs/s01.png'
duration 11.000
...
file '/abs/s15.png'     # repeat the LAST entry with no duration, or ffmpeg drops it
```

`ffmpeg -f concat -safe 0 -i list.txt -vsync cfr -r 30 -c:v libx264 -pix_fmt yuv420p …`
— same output in under a minute. Only capture per frame when something moves.

## Slide boundaries feel like stalls — crossfade with `xfade`

Decks switch slides with `display:none` → hard cut, then sit static through the
dwell: *jump, then freeze*. Capture one still per slide and let ffmpeg crossfade:

```js
const XF = 0.7;        // crossfade length
const LEAD = XF / 2;   // start half a transition early so the midpoint lands on the new line
const clip = TL.map((s, i) => {
  const win = s.end - s.start;
  if (i === 0)     return win + LEAD;
  if (i === n - 1) return win + XF - LEAD;
  return win + XF;
});
let filter = '', prev = '[0:v]', acc = 0;
for (let i = 1; i < n; i++) {
  acc += clip[i - 1] - (i === 1 ? 0 : XF);
  const offset = acc - XF;
  const label = i === n - 1 ? '[vout]' : `[v${i}]`;
  filter += `${prev}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${offset.toFixed(3)}${label};`;
  prev = `[v${i}]`;
}
```

Inputs are `-loop 1 -t <clip> -i still.png` per slide.

- `xfade` offsets are **absolute on the chain output**, not per input. Getting it
  wrong yields the right total length with every transition misplaced.
- The transition must **straddle** the audio boundary, not follow it.
- Verify by sampling mid-fade (boundary − `XF/2`): both slides should be ghosted.
  A clean single slide means the crossfade silently didn't happen.

## Rendering an existing interactive deck — three silent failures

1. **`newPage({viewportSize})` is ignored → 1280×720.** `browser.newPage()` takes
   `viewport`; `viewportSize` is a context option. Verify from the PNG header:
   `python3 -c "import struct;d=open('frames/f000000.png','rb').read(33);print(struct.unpack('>II',d[16:24]))"`
2. **Deep-link params are often 0-indexed** while your timeline is 1-indexed, so
   `?s=1` shows slide two. Read the deck's JS, then check the on-slide `N / total`
   counter in a still — it's the only ground truth.
3. **Presenter affordances get baked in** (keyboard hints, progress bars, hover
   states). Hide them per navigation with `page.addStyleTag(...)`.

## Product-walkthrough scenes

Capture the live app at 2× DPR, then do camera work in CSS — better than a screen
recording and deterministic.

```js
const pg = await br.newPage({viewport:{width:1600,height:1000}, deviceScaleFactor:2});
await pg.goto(URL,{waitUntil:'networkidle'}); await pg.waitForTimeout(2500);
await pg.screenshot({path:'assets/shots/overview.png'});
```

Ken-Burns by mapping a source rect to the frame, and draw the spotlight with the
*same* transform so it tracks the zoom. Clamp the target rect to 16:9 inside the
source image, or the pan runs past the edge into black bands:

```js
function fit(cx,cy,w){
  const IW=1600, IH=1000, AR=1920/1080;
  w=Math.min(w,IW); let h=w/AR; if(h>IH){h=IH;w=h*AR;}
  let x=Math.max(0,Math.min(cx-w/2,IW-w)), y=Math.max(0,Math.min(cy-h/2,IH-h));
  return {x,y,w,h};
}
```

Pin callouts to the edge opposite the highlighted element so they don't cover it.

## Design tokens and typography

Put every color/type value in one `:root` block so a rebrand is a few hex changes.
Name colors by meaning (`--ok`, `--warn`, `--human`), not appearance. To avoid
the generic AI look: heavy geometric sans for headlines, a serif italic for the
one emotional phrase per scene, small letter-spaced uppercase for labels,
tabular numerals for figures. `python3.13 creator.py style` maps DESIGN.md brand
styles to render palettes.

## Concatenating parts

```bash
ffmpeg -y -i partA.mp4 -i partB.mp4 -filter_complex \
  "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -c:v libx264 -crf 17 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k \
  -movflags +faststart out/full.mp4
```

## Pitfalls

- A fixed-size body in a smaller viewport pins content to one edge — same root
  cause as the viewport bug.
- Await `document.fonts.ready` before frame 1 or it renders in a fallback face.
- After a killed render, `fs.rmSync(frames)` can throw `ENOTEMPTY`; use
  `{ recursive: true, force: true, maxRetries: 10, retryDelay: 200 }` and check for
  orphaned browser processes.
- Helper scripts resolve `playwright` from their own location; keep them in the
  production dir, not a temp dir.
- `timeout` isn't on macOS by default; don't wrap CLI calls in it.
- Don't search the whole home directory for model files; it hangs. Target known
  cache paths.
- `volumedetect` prints across several stderr lines; a narrow grep can return
  nothing and look like silence. Use `-f null -` and also check `n_samples`.

## Verification (all of these)

1. `ffprobe`: 1920×1080, h264 + aac, expected frame count and duration.
2. Extract frames with `ffmpeg -ss` and **look at them** (yourself or with a vision
   model) — 4–6 spread across the timeline, plus each boundary. A clean log proves
   nothing visual.
3. Check the **last second** — late reveals past the scene end silently never play.
4. Prove the audio isn't silence:
   `ffmpeg -i out.mp4 -af volumedetect -f null - 2>&1 | grep -E 'mean_volume|n_samples'`.
   Narration lands around −20 dB; digital silence ≈ −91 dB.

## Semantics beat polish

Check what each animation *says*. In one build, agents converging into a data
vault read as "already breached" before the narration said so, spending the
reveal early; stopping them outside told the true story. Render one still per
scene and ask "what does this frame claim?" before a full render.
