---
name: video-production
description: Use when making a narrated explainer or social video.
---

# Video Production

Produce narrated explainer, faceless and social videos with this kit: the
first-party `creator.py` CLI plus two pinned upstream engines (OpenMontage and
HyperFrames). Covers engine choice, the narrated-explainer chain, narration
tiers, and the pitfalls and verification gates that recur in real builds.

## Layout

| Path | What |
|---|---|
| `creator.py` | First-party CLI (`python3.13 creator.py --help`): `narrate`, `voices`, `motion`, `showcase`, `bundle`, `design-check`, `plan`, `edit`, `transcribe`, `studio`, … |
| `OpenMontage/` | Upstream agentic production system (talking-head, animated-explainer, documentary-montage, screen-demo, podcast-repurpose, localization-dub…). Python 3.13 venv. Restore at the pinned revision — see `SETUP.md`. |
| `hyperframes/` | Upstream HTML→MP4 renderer (HTML/CSS/GSAP, deterministic). Use **bun**, not pnpm/npm. Pinned in `upstream-lock.json`. |
| `productions/<name>/` | One directory per video. Never author in the repo root or vendor dirs. Inventory with `python3.13 creator.py bundle --production productions/<name>`. |

Requirements: ffmpeg, node, bun, python 3.13 (OpenMontage needs ≥3.10), a local
Chrome for headless capture, and optionally the `whisper` CLI for QA.

## Pick an engine before you build

- **HyperFrames** — burned-in captions, transitions, lint/check gates, many
  scenes built in parallel.
- **Standalone HTML→MP4** — re-cutting visuals against narration you already
  have, ≤8 scenes, or output that must regenerate in CI. Use
  `python3.13 creator.py motion create` (GSAP, offline) and
  `python3.13 creator.py showcase` to record it frame-exact. See the
  `motion-graphics-renderer` skill and `references/standalone-html-mp4-renderer.md`.
- **OpenMontage** — when you want its research→script→assets pipelines and are
  willing to configure provider keys.

## Paid vs free

Free path, zero keys: Kokoro (or Piper) narration, Archive.org/NASA/Wikimedia
footage, HyperFrames or `creator.py showcase` render, ffmpeg post. Open-footage
sources and first model downloads need network access.

Paid layer: one `FAL_KEY` (fal.ai) unlocks FLUX images, Kling/Veo/Seedance video
and MiniMax voice cloning, pay-per-use. Keep keys in a `chmod 600`, gitignored
`.env`. Every other provider key is optional.

## Narrated explainer with HyperFrames

Start from the installed `hyperframes/skills/hyperframes/SKILL.md`; an explainer
follows its `references/types/explainer.md`. (Older per-type skills such as
`faceless-explainer` were retired upstream.) The chain, each step gating the next:

1. **Scaffold** — `HYPERFRAMES_SKIP_SKILLS=1 npx hyperframes init productions/<name> --example blank --non-interactive`
2. **Auth gate** — run `npx hyperframes auth status` and relay the result. Offline
   vs signed-in is the user's choice; ask once, then follow it. Never silently add
   a paid provider.
3. **Ground the source** — verbatim source text (e.g. `capture/extracted/visible-text.txt`)
   plus design tokens (title, colors, fonts).
4. **Storyboard + script** — present audience, message and frame plan before
   building. In collaborative mode get approval once; don't re-ask after the user
   says to finish.
5. **Narrate** — Kokoro for drafts, or `creator.py narrate` (below).
6. **Build scenes** — scenes are context-heavy; a subagent per scene works well.
   Brief each with the composition contract, the design file and its own storyboard
   block; have it write exactly one scene file and run no CLI.
7. **Check and render** — `npx hyperframes check --json`, `snapshot --review`,
   render, then review the MP4 visually and by ear.

Format from destination: YouTube/embed 16:9, feed posts 1:1, Shorts/TikTok/Reels 9:16.

## Pitfalls (each hit in a real build)

- **SCRIPT.md headings must be `## <title> (Frame N)`** with the spoken text
  indented 4+ spaces. `## Frame 1 — hook` matches nothing → silent film, zero voices.
- **Kokoro first-run race** — parallel TTS calls fail while the model downloads,
  often leaving 1 of N voices. Re-run once it is cached. Test one line with
  `npx hyperframes tts "text" --voice af_heart --output t.wav` (text is positional).
- **Kokoro emits no word timings** → captions are skipped. Recover timings with a
  WhisperX/whisper alignment pass over the generated WAVs.
- **Kokoro venv** — `kokoro-onnx` lives in the OpenMontage venv; point
  `HYPERFRAMES_PYTHON` at that interpreter or every call fails while exiting 0.
  Check each WAV is non-empty, never the exit code.
- **Scene roots need `data-duration`** on the same element as
  `data-composition-id`; the transitions step fails with a misleading
  "no root" message otherwise.
- **Same-track clips cannot overlap** — give a full-bleed background and a grid
  layer separate `data-track-index` lanes.
- **Late reveals** scheduled past a scene's synced duration silently never play.
- BGM via MusicGen pulls ~2 GB of torch; prefer a royalty-free bed.
- Run long installs and renders in the background with a completion notification
  so you don't lose track of them.

## Narration tiers

Kokoro `af_heart` is a **draft** voice — free, offline, audibly synthetic. For
anything judged or client-facing:

```bash
python3.13 creator.py narrate --script SCRIPT.md --output productions/<name>/narration \
  --engine azure --allow-cloud --cast '{"HOST":"en-US-Andrew:DragonHDLatestNeural"}'
```

Needs `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, or Entra via `--inventory`
(see `docs/VOICES.md`). Local alternatives: `--engine kokoro` (default free path),
and `--engine f5|qwen3|chatterbox` for offline voice cloning — bring your own
reference WAV with `--ref` (qwen3 also needs `--ref-text`). Manage local models
with `python3.13 creator.py voices list|fetch`.

`narrate` writes `voice/*.wav`, `narration.wav` and a zero-delta `timeline.json`.
**Switching engines shifts every duration** (~+18% Kokoro→Azure): rebuild the
timeline and re-render; never ship the old cut. Details, casting table and auth
traps: `references/azure-speech-narration.md`.

## Effects, 3D and reference videos

- Title reveals, counters, backgrounds, device frames: see
  `creator-arsenal/references/react-bits.md`. Prefer baked assets or re-authoring
  the effect in the GSAP timeline; React hooks and RAF loops don't obey a video
  clock. Prove repeated/reverse/out-of-order seeks before frame-exact capture.
- Editable 3D props and camera moves: `creator-arsenal/references/mcp-for-blender.md`.
  Render baked frames, then add narration with this pipeline.
- Learning a technique from someone's video: sample frames, not just the
  transcript — `references/learning-technique-from-video.md`.

## Real app walkthroughs — record before illustrating

1. Capture the working application, not slides that imitate it. Use a synthetic
   workspace and decide the allowed writes per chapter; never use real user data
   as demo fodder.
2. Probe the whole interaction sequence before generating narration. Assert the
   fixture state and locate controls by specific accessible names, not generic
   selectors.
3. Test navigation-only tours separately and assert no mutating API calls. Claim
   touch behaviour only with a touch-enabled context and real taps.
4. Freeze narration before the final timed capture. Cache by text+voice+settings,
   measure the emitted audio, and get real word timings for captions — word
   counts are not timing evidence. Keep raw clips and each scene's ready offset.
5. Put captions in a band outside the app viewport so they never cover inputs or
   controls.
6. Freeze and fingerprint inputs for the final render. Deliver the MP4 and
   captions; for an embedded player, verify duration, playback, byte ranges and
   caption download.

## Verify the exported artifact

1. **Structural** (`ffprobe`): h264 + aac, correct width/height,
   `nb_frames == round(DURATION*fps)`.
2. **Visual**: pull frames from the finished MP4 for every scene, just after each
   boundary, and the final 2–3 seconds; review them yourself or with a vision model.
   Lint + ffprobe passing proves validity, not quality — see
   `references/visual-review-and-design-quality.md`.
3. **Narration**: transcribe the final muxed video independently and compare
   numbers, negations and the ending to the script, e.g.
   `whisper final.mp4 --model base.en --language English --fp16 False --condition_on_previous_text False --output_format json --output_dir qa/asr`
   or `python3.13 creator.py transcribe` (cloud, needs `--allow-cloud`). Report it
   as an automated wording check, not proof of natural delivery.

Local tool notes: Playwright may lack a bundled browser — launch with
`chromium.launch({channel:'chrome'})`. Some ffmpeg builds lack drawtext/libass;
render caption PNGs with PIL and `vstack` them under the clip.

## Publishing boundary

Building privately is not clearance to publish. Before any public post of a video
about real client work: no client or colleague names, no internal metrics or
attribution, synthetic data only, then a final scrub pass.
