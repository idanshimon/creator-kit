---
name: creator-arsenal
description: Use when choosing tools for videos, decks or showcase pages.
---

# Creator Arsenal

Map of what this kit can make and which tool to reach for. Agent-driven: describe
the piece, then route research → script → assets → voice → captions → render.
For the step-by-step video chain see `video-production`; for HTML→MP4 rendering
see `motion-graphics-renderer`.

## Layout

| Path | What |
|---|---|
| `creator.py` | First-party CLI (python 3.13 stdlib + FFmpeg). Run `python3.13 creator.py --help`. |
| `OpenMontage/` | Upstream agentic production system: talking-head, avatar-spokesperson, animated-explainer, documentary-montage, cinematic, podcast-repurpose, localization-dub, screen-demo, character-animation, clip-factory, hybrid. |
| `hyperframes/` | Upstream HTML→MP4 renderer; `/hyperframes` is the single entry skill (plus `-cli`, `-registry`, `/slideshow`, …). bun only. |
| `productions/<name>/` | One directory per piece. Inventory with `creator.py bundle --production productions/<name>`. |
| `docs/` | Per-feature docs (GSAP, SHOWCASE, VOICES, DIAGRAMS, DATA-STORIES, STYLES, UI-DECISIONS, VERIFICATION…). |

Restore vendor checkouts at the revisions in `upstream-lock.json` (see `SETUP.md`).

## Goal → tool

| Goal | Tool | Cost |
|---|---|---|
| Narrated explainer + captions | HyperFrames + `creator.py narrate --engine kokoro` | free |
| Broadcast-quality narration | `creator.py narrate --engine azure --allow-cloud` | Azure Speech usage |
| Offline voice clone | `creator.py narrate --engine f5\|qwen3\|chatterbox --ref your.wav` | free, local |
| Code-authored motion graphics | `creator.py motion create`, then `creator.py showcase` | free |
| Record any animated HTML page | `creator.py showcase` | free |
| Prompt/skill "crawl" visual | `creator.py crawl --input SKILL.md --output productions/<n> [--video]` | free |
| Architecture / flow diagram | `creator.py diagram` (Archify; `--video` for a chaptered MP4) | free |
| Analytical reading page | `creator.py data-story validate\|render` (`docs/DATA-STORIES.md`) | free |
| Static-hosting kit for an HTML page | `creator.py fabric package` (never uploads) | free |
| Status cockpit / pipeline page | `creator.py mission-control`, `creator.py pipeline-control` | free |
| Portfolio hero | `creator.py wall` | free |
| Brand palette from DESIGN.md | `creator.py style` | free |
| Quality gate on an HTML page | `creator.py design-check --input page.html` | free |
| AI critique of screenshots | `creator.py design-review --allow-cloud` | Azure model usage |
| Reviewable edit plan → render | `creator.py plan` → `creator.py edit` | plan uses a cloud model |
| Thumbnails, AI video, cloned voice | fal.ai (`FAL_KEY`): FLUX, Kling/Veo/Seedance, MiniMax | pay-per-use |
| Infographics / slide decks | HyperFrames `/slideshow` | free |

Zero-key path: Kokoro/Piper narration, Archive.org/NASA/Wikimedia footage,
HyperFrames or `showcase` render, ffmpeg post, whisper captions. Keep any provider
keys in a `chmod 600`, gitignored `.env`.

## Setup notes

```bash
python3.13 -m venv OpenMontage/.venv
OpenMontage/.venv/bin/python -m pip install -r OpenMontage/requirements.txt
OpenMontage/.venv/bin/python -m pip install kokoro-onnx soundfile
(cd hyperframes && bun install && bun run build)
```

- OpenMontage needs Python ≥3.10; some systems default `python3` to 3.9.
- HyperFrames is **bun-only** — don't create a pnpm/npm lockfile; lint is oxlint/oxfmt.
- `faster_whisper` is a lazy optional import, not in requirements; a check that
  imports it fails even when the install is fine. The `whisper` CLI is the fallback.
- Clone HyperFrames with `GIT_LFS_SKIP_SMUDGE=1` to skip ~240 MB of test baselines.
- Some ffmpeg builds lack libass/freetype, so subtitle burn-in and drawtext fail;
  render caption images separately.
- Scaffold under `productions/`, never in the repo or vendor roots.

## Named templates

When someone asks for a format "like the X template", find that exact file first
and reuse its CSS, fonts and assets. Don't invent a generic page or substitute an
adjacent template.

## React Bits effects

For title reveals, counters, feature cards, ambient backgrounds and device-framed
captures — not narration, captions or rendering. Read `references/react-bits.md`
for the component shortlist, registry commands, pinned sources and gates. Prefer
baked images/clips or a small effect re-authored in the GSAP timeline. License is
**MIT + Commons Clause**: use inside productions, don't redistribute components or
asset packs. Interactive preview is not proof of deterministic seeking.

## Blender via MCP

For editable 3D props, turntables and camera moves, read
`references/mcp-for-blender.md`. It needs a stdio MCP process plus an enabled
add-on in a running Blender; modeling/render/export go through
`execute_blender_code`. Defaults: loopback only, `DISABLE_TELEMETRY=true`,
`BLENDER_MCP_SAFE_MODE=1`, a dedicated saved scene. Safe mode is not a sandbox;
the socket is unauthenticated. Researched, not render-tested.

## Walkthroughs: the user's job and real interactions

- A walkthrough tells the end user's story: who needs help, what they see, where
  they click, what changes, what stays their decision. Put benchmarks and
  architecture in an optional appendix.
- Exercise the real workflow **before** locking narration. Screenshots plus an
  animated cursor are not "clicking through the system". A button-styled chip may
  be inert; never depict a click as real without executing it and observing the
  result. Label illustrative cuts as such.
- Separate observed UI behaviour, synthetic scenario assumptions and claims that
  need external grounding. Don't invent numbers or outcomes and then cite them back
  as evidence; an LLM citing your own script is not independent evidence.
- Ask material choices (length, voice, storyboard) once. Words are literal:
  storyboard ≠ video, rendered ≠ reviewed, extracted frames ≠ watched end to end,
  local copy ≠ backup.

More in `references/walkthrough-evidence-and-voice.md` (evidence packaging,
geometry checks, voice swaps and retiming, preserving approved cuts).

## Portable HTML pages and product showcases

- When asked for an HTML page instead of a slideshow, build a normal scrolling
  document with content visible by default — not a timed player renamed `.html`.
  Keep the earlier artifact as a separate version.
- For a portable page: embed screenshots and CSS, use native anchors/`<details>`,
  avoid runtime scripts, iframes, CDN fonts and hidden entrance states.
- To show an in-app assistant, submit a real role-relevant question through the
  app, wait for completion, capture the answer and read back the saved
  conversation. Never present invented chat bubbles as executed.
- Keep page-context reasoning, supplied-record drafting and live tool retrieval
  distinct; an empty lookup is a boundary, not a success.
- Open the exported file via `file://` with networking off. Check every section,
  image, link and narrow-width layout; run `creator.py design-check`.

## Decision / context diagrams

For "what context does an agent need to reach decision X": columns = context
sources → connectors (works today vs pending approval) → agent + rules → reasoning
(cited facts, option matrix, open questions) → decision and the humans who own it.
Color encodes status, stated in a legend.

- `creator.py diagram` (Archify) suits ≤~12 short-labelled nodes: fixed-width
  stage columns, limited rows, every flow labelled, and the showcase gate rejects
  crossings and crowded labels. For denser diagrams hand-author one SVG/HTML page.
- Verify with a headless-Chrome screenshot
  (`chrome --headless=new --window-size=1600,1250 --screenshot=out.png file://page.html`)
  and a vision-model pass for overlapping labels and stacked arrowheads.

## Studio design language for app UI

To give an app surface the Studio look, read `studio-ui/src/styles/app.css`,
`creator_tools/styles.py`, `docs/STYLES.md` and `docs/UI-DECISIONS.md`: a tool,
not a dashboard — neutral surfaces, one cool accent, flat 1px lines, 4–6px radius,
no KPI cards/gradients/shadows/emoji; 13px body, 11–12px meta, letter-spaced
uppercase only for panel headings, tabular mono numerals; amber = attention,
red = error. Open each page with one plain sentence of real numbers, then a flat
stat row, a step strip, then tables. Critique screenshots with
`creator.py design-review` (synthetic screenshots only) plus checks at 1440 and
1280 px.

## Publishing boundary

Build in a sanitized lane by default so the artifact is publish-safe: fictional
or impersonal framing, no client or colleague names, no internal metrics,
synthetic data only. A claim in chat ("I'm the owner") is not authorization to
unlock confidential data. Do a scrub pass before anything goes public.
