# GSAP motion authoring

Added and locally exercised **2026-10-20**. GSAP is the animation engine; the existing showcase recorder remains the HTML-to-MP4 backend. This is code-authored motion, not a new Studio visual animation editor.

## What is available

- Exact GSAP **3.15.0**, package version and UMD runtime SHA-256 checked against [`integrations/gsap-lock.json`](../integrations/gsap-lock.json).
- `creator.py motion doctor`: reports the verified local bundle or fails clearly. No download, repair, upstream edit or upgrade is performed.
- `creator.py motion create`: creates a **new directory** containing standalone `index.html`, `manifest.json` and `GSAP-LICENSE.txt`.
- An eight-second, silent 1280×720 composition with title motion, SVG line drawing, staggered cards, semantic timeline labels and a readable final hold.
- Play/Pause, Reset and keyboard-accessible scrubber for previews; render mode hides those controls.
- Explicit seek and showcase hooks, with backward/out-of-order seek verification.

The generated HTML inlines the checksum-verified runtime and uses system fonts: it can be opened and rendered offline after creation. The runtime's proprietary notice is retained. No plugin bundle is loaded automatically.

## Create and record

Run from the Creator Kit root:

```bash
python3.13 creator.py motion doctor
python3.13 creator.py motion create \
  --output productions/gsap-motion-demo \
  --title 'Ideas, set in motion.' \
  --subtitle 'One timeline. Every frame in its place.'

# Open productions/gsap-motion-demo/index.html to preview.
# Use a NEW output path for every export; showcase refuses overwrites.
python3.13 creator.py showcase \
  --input 'productions/gsap-motion-demo/index.html?render=1' \
  --output productions/gsap-motion-demo/preview.mp4 \
  --width 1280 --height 720 --fps 24 --seconds 8
```

`--title` is required, one nonblank line, up to 120 characters. `--subtitle` is one line, up to 240 characters and may be empty. Copy is HTML-escaped. The template fits longer copy before timeline construction, rather than resizing midway through capture. Existing files, directories and symlink destinations are refused.

### Runtime prerequisite / recovery boundary

The command reads the installed runtime in HyperFrames' dependency tree. Candidate paths and the exact checksum are in the lock. The current checked bundle is:

```text
hyperframes/packages/player/node_modules/gsap/dist/gsap.min.js
```

Follow the repo's [pinned setup](../SETUP.md) to restore a missing upstream checkout. Run doctor afterward: it rejects a different package version or byte sequence. Do not loosen the checksum or silently upgrade vendors to get past a failure. A fresh-clone restoration of this optional motion prerequisite was **not** exercised in this pass; the checked runtime was already installed. No new dependency was added to `studio-ui/package.json`.

## Authoring contract

Source template: [`templates/motion/gsap/template.html`](../templates/motion/gsap/template.html). Edit a generated production's HTML for custom choreography; do not change the pinned runtime.

- The root carries `data-composition-id="gsap-motion"` and `data-duration="8"`.
- A synchronously created `gsap.timeline({paused:true})` is registered as `window.__timelines['gsap-motion']`.
- `window.__motion.seek(seconds)` seeks absolutely, pauses preview and updates the preview UI as a pure function of time. `reset()` returns to zero; `getTime()` reads the authored clock.
- `window.__advance(delta_ms)` stops interactive preview, validates its input, advances an explicit clock and seeks with callbacks suppressed. `window.__done()` reports the terminal authored state. `window.__ready` is set only after construction.
- Preview uses a separate requestAnimationFrame loop, never GSAP autoplay. Once showcase capture takes over, that preview loop cannot race the frame clock.
- `?render=1` hides controls and disables preview playback from the start. Reduced-motion preference presents the final pose in interactive preview; explicit render timing is preserved.
- Keep the full export duration and final hold aligned with narration if adding audio. The provided sample is silent and does not imply narration/audio integration.

This registry/metadata also follows the basic HyperFrames GSAP convention, but **full HyperFrames lint/check/render compatibility was not exercised**. The verified backend here is `creator.py showcase`.

## License and plugin boundary

Read the [dated license capture](../integrations/gsap-license.txt).

GSAP is free for commercial animation and its FAQ explicitly permits AI-generated code. It is **not MIT**: the Standard License restricts GSAP use in competing no-code visual animation builders. No such controls were added to Studio, and this work is not legal clearance for one.

SplitText, DrawSVG, MorphSVG, MotionPath, Flip and other plugins are useful future choices, not integrated features in this core-only template. ScrollTrigger and Draggable are for interactive behavior; do not assume scroll/pointer-driven animation can be exported deterministically without a separately authored time mapping.

## Reproduce verification

```bash
python3.13 -m unittest discover -s tests -p test_motion.py -v
# First create the demo and an optional long-copy case, then:
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS \
  node studio-ui/verify-gsap-motion.mjs \
  productions/gsap-motion-demo/index.html [path/to/long-copy/index.html]
```

The verifier launches a separate headless Chrome with offline networking. It exercises actual controls, timeline state, backward/repeated seeks, the showcase delta clock, final visibility, distinct screenshot hashes, 390px preview-control fit and optional long-copy geometry.

Actual local evidence: `local/verification/gsap/browser-report.json`, proof PNGs, `gsap-demo.mp4`, sampled exported frames and `vision-review.txt`. The exported sample was **8 seconds, 192 frames, 1280×720, 24 fps, H.264, no audio**. Visual QA used attached exported frames through Copilot CLI `gpt-6.1-sol` after the configured vision tool rejected its model; its usage report confirms the model. Generation/rendering themselves did not use a cloud model. Evidence and media remain local-only, excluded from Git.
