# Walkthrough — narrated product tours from screenshots or URLs

`creator.py walkthrough` turns a short JSON spec into a narrated product walkthrough:
animated arrows that draw in toward a target, a spotlight that dims everything else,
a zoom/pan camera punch-in, a gliding cursor with click ripples, numbered step badges,
callout bubbles and lower-third captions with word highlighting, timed to the narration.

```bash
python3 creator.py walkthrough \
  --spec examples/walkthrough/pipeline-control.walkthrough.json \
  --output productions/my-tour --gif
```

Output (`--output` must not exist; nothing is overwritten):

| File | What |
|---|---|
| `SCRIPT.md` | Narration script generated from step `narration` (`## Step N (Frame N)` contract) |
| `narration/` | `narration.wav` + `timeline.json` from `creator.py narrate` |
| `assets/step-NN.png` | Screenshot per step (copied, or captured with headless Chrome) |
| `walkthrough.html` | Deterministic, self-contained page (no CDN) implementing the showcase contract |
| `walkthrough.mp4` | 1920×1080 H.264 + AAC, same length as the narration |
| `poster.png` | Thumbnail |
| `walkthrough.gif` | `--gif`: looping README preview, ≤ `--gif-max-mb` (6 MB), ~800–900 px, captions burned in |
| `manifest.json` | Paths, ffprobe result, GIF size |

## SDLC walkthroughs

For the HTML companion or video player, use the [standard SDLC stage map](../templates/overlays/sdlc-loop/README.md). Drive it from chapters or the video clock; inspection is not evidence that work finished. The walkthrough CLI does not add this overlay to an MP4.

## Spec

```json
{
  "title": "Pipeline Control tour",
  "width": 1920, "height": 1080,
  "viewport": [1440, 900],
  "steps": [
    {"image": "pipeline-control.png",
     "target": {"x": 444, "y": 233, "w": 70, "h": 162},
     "annotations": ["arrow", "spotlight", "zoom", "badge", "cursor", "click"],
     "arrow_style": "hand",
     "callout": "22.8 min, was 7.1",
     "caption": "optional on-screen text (defaults to narration)",
     "narration": "Integration is the bottleneck...",
     "dwell": 0.6}
  ]
}
```

- Each step uses **either** `image` (path relative to the spec) with `target` in image
  pixels, **or** `url` (http(s), `file://`, or a local HTML path) with a `selector`.
  URL steps are captured with headless Chrome at `viewport`; the target rectangle comes
  from the DOM (`getBoundingClientRect`), so arrows are grounded in the real element.
- `selector` is a CSS selector, or `text=Exact label` to pick the innermost element with
  that text (for SVG labels the enclosing `<g>` is used).
- `annotations`: any of `arrow spotlight zoom click badge callout cursor`
  (default: arrow, spotlight, zoom, click, badge, cursor). `callout` text shows a bubble at
  the arrow's tail. `arrow_style`: `hand` (curved, double stroke) or `clean`.
- Consecutive steps on the same screenshot pan the camera without a crossfade.

## Narration

Kokoro (local, free) is the default. Other engines pass through to `narrate`:
`--engine azure --allow-cloud`, `--engine f5`, `--voice`, `--speed`. To re-render
visuals without re-synthesizing, pass `--narration <existing narrate output dir>`.
`--html-only` stops after `walkthrough.html` (open it and call `__seek(seconds)` in the
console to scrub).

## Timing (per step, from its narration start)

cursor glides 0.2–1.4 s · zoom in 0.35–1.25 s · spotlight 0.45–0.95 s · badge pops 0.6 s ·
arrow draws 0.95–1.55 s · click ripple at 1.55 s and every 1.3 s · callout 1.45 s ·
zoom out and fade over the last 0.65 s (the last step stays zoomed). Captions show ≤ 11
words at a time. Each word lights up in proportion to its share of the step's speech
duration, which is an estimate rather than forced alignment. The caption moves to the
top when the zoomed target would sit under it.

## Verify

```bash
ffprobe -v error -show_entries stream=codec_name:format=duration -of csv=p=0 out/walkthrough.mp4
ffmpeg -i out/walkthrough.mp4 -af volumedetect -vn -f null - 2>&1 | grep mean_volume
```

Extract one frame per step (`timeline.json` slide `start` + ~2.4 s) and check that each
arrow points at the intended element before you publish.
