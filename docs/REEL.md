# Reel: short-form social video templates

`creator.py reel` renders a vertical or feed video for TikTok, Reels, Shorts or LinkedIn from
a small JSON spec. It builds one self-contained `index.html` (no CDN, no network, no wall
clock) and records it frame by frame with the showcase recorder.

```bash
python3.13 creator.py reel --spec examples/reel/kinetic.json --output productions/my-reel [--gif] [--safe-zones]
```

Output directory (the command refuses to overwrite any of these):

| File | What it is |
|---|---|
| `index.html` | The scene. Open `index.html#play` for a live preview or `index.html?t=2.5` for a still at 2.5 s |
| `reel.mp4` | H.264, yuv420p, exact spec duration. Has AAC audio when narration audio is given |
| `poster.png` | Cover frame, taken when the first beat is fully on screen |
| `preview.gif` | With `--gif`: 10 fps, 320 px wide (480 px for 16:9), roughly 2 MB per 10 s |

## Templates

| Template | Format it imitates | Beat fields |
|---|---|---|
| `kinetic` | Hook with word-by-word punch captions. `mode: "karaoke"` shows the whole line dim and lights each word as it is spoken | `text`, `mode`, `size` |
| `pov` | "POV:" text-on-screen story. Beat 1 is the premise, later beats stack as caption labels | `text`, `tag` (default `POV:`); spec `align` |
| `countdown` | Top-N list. Numeral rolls N..1 with a rank rail | `title`, `text`, `rank`; spec `title`, `kicker` |
| `before-after` | Split wipe. Beat 1 = before, beat 2 = after, later beats = captions. Image panels settle at 50/50; text panels wipe fully | `label`, `text`, `lines[]`, `media` |
| `carousel` | "Things I wish I knew" swipe cards with page count and dots | `kind: "cover"`, `title`, `text`, `tag` |
| `stat` | Number reveal. Counts up, keeps prefix/suffix/decimals; `%` values get a ring | `value`, `label`, `text` |
| `quote` | Quote card. Words resolve from blur, emphasis gets an underline sweep, author lands last | `text`, `author`, `role` |
| `phone` | Screenshot or terminal in a phone mockup with zoom punch-ins and a focus ring | `text`, `zoom: {x, y, scale}`, `scroll` (0..1, image screens); spec `screen` |

Any template can end on `{"kind": "end", "text": ..., "sub": ..., "cta": ...}`, a shared CTA card.
Wrap words in `*asterisks*` for the accent colour. Each beat takes `duration` in seconds;
defaults depend on the template (kinetic 1.8 s, countdown 3 s, quote scales with word count).

## Spec

```json
{
  "template": "kinetic",
  "format": "9:16",
  "platform": "cross",
  "style": "noir", "theme": "dark", "accent": "#f2b544",
  "title": "Creator Kit", "handle": "@creatorkit",
  "progress": true, "loop": true, "fps": 30,
  "background": "media/bg.jpg",
  "screen": "media/screenshot.png",
  "narration": {"timeline": "narr/timeline.json", "audio": "narr/narration.wav"},
  "beats": [{"text": "Stop editing videos *by hand.*", "duration": 2.2}]
}
```

- **Formats:** `9:16` 1080x1920 (default), `1:1` 1080x1080, `4:5` 1080x1350, `16:9` 1920x1080. `--format` overrides the spec.
- **Style:** any palette from `creator.py style list`. When a palette's accent has no hue (noir, Vercel-like), the highlight becomes the palette's amber. The highlight is contrast-checked to at least 4.5:1 on the background.
- **Media:** images only (png, jpg, webp, gif, svg), resolved relative to the spec and inlined as data URIs. For a screen recording, export stills or use the `terminal` screen: `"screen": {"title": "zsh", "terminal": ["$ cmd", "✓ done"]}`.
- **Loop:** with `loop: true` the content fades in from and out to the bare background, so the last frame matches the first.

## Safe zones

All text is laid out inside the safe box, with a 28 px gutter, a strip for the progress bar
and a strip for the handle. `--safe-zones` draws the platform UI areas (red) and the safe box
(green) over the video. Use it for review renders, not for posting.

9:16 profiles (top, right, bottom, left px on 1080x1920), chosen with `--platform`:

| Profile | t | r | b | l |
|---|---|---|---|---|
| `cross` (default) | 250 | 170 | 560 | 80 |
| `tiktok` | 220 | 140 | 480 | 60 |
| `reels` | 250 | 120 | 560 | 65 |
| `shorts` | 260 | 180 | 560 | 50 |
| `none` | 72 | 72 | 72 | 72 |

The figures come from published guides checked in 2026-11 (vidova.ai, revid.ai, solidlabs.com).
They are production guides, not platform guarantees. Paid ads reserve more space: Meta asks for
35% at the bottom. Feed formats (1:1, 4:5, 16:9) have no overlaid UI and use an even margin.

Every headline is auto-fitted. Its font shrinks until it fits its box and no single word is
wider than the line, so text is never clipped.

## Narration sync

Pass a `timeline.json` from `creator.py narrate` (spec `narration.timeline` or `--timeline`).
Beat *i* takes slide *i*'s `start`/`end`. Word timings are spread over the slide's
`speech_duration` by word length, which drives the kinetic and quote reveals. To use exact
word times from an aligner, give a beat its own `words: [{"s": 0.0, "e": 0.3}, ...]` in
absolute seconds, one entry per word. Audio (`narration.audio` or `--audio`) is muxed as
AAC, padded or trimmed to the video length.

## Determinism

The page implements the showcase contract: `window.__ready`, `window.__advance(ms)` and
`window.__done()`. Every frame is a pure function of `t`. There is no `Date`, no timers and
no `Math.random`, and the grain is a static SVG noise tile. The recording length is set from
the spec, not from `__done`. A 10 s 1080x1920 reel takes about 60–90 s to record.

## Files

- `creator_tools/reel.py`: spec validation, timing, palette, HTML build, record, mux, poster, GIF
- `templates/reel/runtime.js`, `reel.css`: stage, background, safe box, progress bar, end card, clock
- `templates/reel/<template>.js`: one file per template
- `examples/reel/<template>.json`: one synthetic example each
