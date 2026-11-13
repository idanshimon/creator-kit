---
name: creator-studio
description: "Use when producing video, dashboards or explainers."
---

# Creator Studio

Agent-driven content production with this repository: videos, narrated explainers, motion graphics, interactive diagrams, data stories, operator dashboards and screenshot design reviews.

Start every session by reading `README.md`, `INDEX.md`, `docs/INDEX.md`, `SETUP.md` and running `python3.13 creator.py --help`. Map requests onto commands that actually exist; never assume a template or flag — check `<command> --help`.

**Free and offline by default.** Local FFmpeg rendering, local voices (Kokoro, Qwen3, Chatterbox, F5), local Chrome capture. Cloud model calls (Azure OpenAI, Azure Speech, Whisper) are optional and always require `--allow-cloud`. Nothing is uploaded automatically.

## Reference map

| Read | When |
|---|---|
| `references/video-workflow.md` | Narrated HyperFrames/OpenMontage videos, revision loop, known pitfalls |
| `references/dashboards.md` | Mission Control, Pipeline Control, home pages, UI rules, map interaction, real/live data |
| `references/agent-dashboard-layouts.md` | Picking a dashboard shape; attrition charts; trial procedure |
| `references/analytical-story-publishing.md` | Data stories, evidence contracts, Fabric packaging |
| `references/music-video-production.md` | Music videos over an existing song; character performance |
| `references/ux-designer.md` | `creator.py design-review` screenshot critique |

Repo docs own the details of each command: `docs/GSAP.md`, `docs/DIAGRAMS.md`, `docs/DATA-STORIES.md`, `docs/FABRIC-EXPORT.md`, `docs/MISSION-CONTROL.md`, `docs/PIPELINE-CONTROL.md`, `docs/SHOWCASE.md`, `docs/STYLES.md`, `docs/WALL.md`, `docs/VOICES.md`, `docs/BUNDLE.md`, `docs/STUDIO.md`, `docs/UI-DECISIONS.md`, `docs/VERIFICATION.md`, `MODELS-AND-EDITING.md`.

## Command map (verified against `creator.py --help`)

| Need | Command |
|---|---|
| Narrated video (scenes, captions, render) | Upstream HyperFrames / OpenMontage (see `SETUP.md`, `references/video-workflow.md`) |
| Code-authored animated titles/cards | `creator.py motion doctor`, `motion create` |
| Interactive architecture diagram | `creator.py diagram install|doctor|validate|render` |
| Evidence-backed reading page | `creator.py data-story validate|render` |
| Static hosting kit for an HTML page | `creator.py fabric package` |
| Orbital operator cockpit | `creator.py mission-control validate|render|serve` |
| Pipeline monitoring page | `creator.py pipeline-control render` |
| Hero "wall" of past work | `creator.py wall` |
| Map a prompt/skill into a graph | `creator.py crawl` |
| Record any HTML page to MP4 | `creator.py showcase` |
| Brand palettes | `creator.py style list|show` |
| Browser quality gate | `creator.py design-check` |
| Screenshot UX critique | `creator.py design-review` |
| Narration + timeline | `creator.py narrate`, `creator.py voices list|fetch` |
| Probe/plan/edit footage | `creator.py probe`, `plan`, `validate`, `edit` |
| Image / captions / chat | `creator.py image`, `transcribe`, `chat` |
| Azure inventory | `creator.py discover`, `models` |
| Production manifest | `creator.py bundle` |
| Local browser editor | `creator.py studio` |

## Picking the style for the audience (decide, don't ask)

Infer the audience from context (meeting, file, wording), pick a style, and state the pick plus a one-line reason at handoff. Ask only if context is genuinely absent.

- **Developers / technical peers:** `--style noir` plus `creator.py wall` (`docs/WALL.md`). Near-black, no accent, brightness-tier text, sans + mono, live HTML mockups, short 0.35–0.6 s entrances.
- **Executives / leadership:** light, calm, one accent, big derived numbers plus one "why it matters" line. No terminals or playful motion.
- **Business teams (operations, finance, clinical, claims):** data-story or Pipeline Control; their vocabulary; an Explain panel per figure; clarity over effect.
- **Internal teams:** dense Mission Control; motion only as status.
- **Briefing / meeting-prep dashboards (people, projects, numbers, signals):** Mission Control rendered from a spec built from your notes, never hand-rolled cards + Mermaid. Put warnings, before-the-call actions, talking points and the one ask in the spec's `brief` strip; keep the spec builder script next to the artifact; keep long source paths out of map-visible text (put them in `detail.evidence`). Run `design-check` and a vision pass in both themes.
- **Audit / accountability reports:** see `references/dashboards.md` ("Audit reports").
- **Public / social (posts, video, launch pages):** `noir` hero + wall for attention; verify phone and contrast. A surface with an established brand keeps its own palette and type: borrow techniques (bright/dim headline split, drifting wall, glow on the key number, one motion timing), never re-skin it.
- **Personal / family:** warm, light, simple.

Run `creator.py style list` before picking; do not assume a style exists.

## Brand styles and the design gate

`creator.py style list|show` exposes the vendored DESIGN.md brand palettes; `mission-control render --style NAME` (and other renderers) re-skin CSS and canvas. A style is a palette/type re-skin, not a new layout; brand fonts fall back to system fonts.

`creator.py design-check --input X.html --shots DIR` is the real-Chrome gate. **Floor:** WCAG text contrast in both themes at 1440 and 390 px, sideways scroll, page errors, network requests, focus. **Reflex:** AI-look tells. Run it on every new concept before calling it done (`docs/STYLES.md`).

- Theme switching in checks must click the page's own toggle; otherwise canvas and inline colours stay on the old theme.
- Run the gate on the pre-change output too (`git show HEAD:<file>`); a before/after count is the proof of improvement.
- Finalize brand palettes for contrast on every surface text sits on (panel, raised, bg, tints). A mid-tone brand surface makes AA impossible; pull secondary surfaces toward the panel. Keep severity hues; move lightness only.
- A unit test asserting AA for every style catches brands a sample never hits.
- The gate reads DOM text only. SVG/canvas labels need a screenshot + vision pass.
- `clipped text in .hero` is expected on a hero with an intentionally overflowing background; verify the copy itself is not clipped.
- Ask a vision model for remaining defects and a 1–10 score per viewport; iterate. Typical fixes: stronger shade behind copy, `text-wrap:balance` on two-tone headlines, blur-backed chips over imagery, lighter shadows in light theme.

## GSAP motion authoring

For animated titles, staged cards, SVG traces and seekable HTML→MP4, read `docs/GSAP.md`.

- `creator.py motion doctor` verifies the installed bundle against `integrations/gsap-lock.json`.
- `creator.py motion create --output NEW_DIR --title TEXT [--subtitle TEXT]` emits standalone offline HTML, a manifest and the retained license. It never overwrites, never fetches a CDN at render time.
- Record: `creator.py showcase --input 'NEW_DIR/index.html?render=1' --output NEW.mp4 --width 1280 --height 720 --fps 24 --seconds 8`.

Keep the timeline paused and registered by composition ID; derive export state from explicit time, not callbacks or wall-clock playback. Verify reverse/out-of-order seeks, long copy, first/middle/final pixels and real MP4 samples with `studio-ui/verify-gsap-motion.mjs`. The template uses GSAP core only. GSAP's Standard License is free for commercial animation, but it is **not MIT**; review it before building a competing visual animation tool.

## Interactive diagrams (Archify)

Prefer Archify for architecture explainers, walkthroughs and technical presentations: polished graph styling plus guided chapters, selection, tracing, presentation controls and light/dark themes. Use Cytoscape for data-driven graphs, React Flow for editable app flows, Excalidraw for whiteboard sketches.

`creator.py diagram render --input X.json --output X.html` with `--template full|presenter|story|embed|minimal`, `--hide/--show PART`, `--details node-details.json`, `--embed-snippet`. `full` stays byte-identical to Archify output; `presenter`/`embed` add an authored what/why/example detail panel. `--showcase-bridge` (optionally `--chapter-dwell 2500`, `--video out.mp4`) injects `window.__ready/__advance/__done` hooks that step through guided chapters for frame-exact MP4 capture. Verify with `studio-ui/verify-diagram-templates.mjs`; read `docs/DIAGRAMS.md`.

Pitfalls:
- The details sidecar validates against `nodes`, but architecture examples use `components`; an architecture sidecar can be rejected as unknown IDs. Do not claim details were applied — fall back to authored labels/chapters.
- For dashboard iframes prefer `--template story` with adequate height (~820 px desktop; the story template locks its height). Pass `?theme=dark|light`.
- Showcase-quality failures and fixes:
  - **desktop-readability** (projected text < 6 px): keep the viewBox ≤ ~1300 px (4 columns of ~200 px boxes, ~80 px gaps) and keep sublabels short.
  - **endpoint-side / crossing / corridor:** align connected boxes on a row or column; route the one long return edge with explicit `fromSide`/`toSide`/`via`; drop decorative edges.
  - **label overlaps a component:** set `labelAt` midway in the gap.
  - **schema:** view notes ≤ 140 chars; components have no `variant`; `sources` need `--repo-root`, which the wrapper does not pass, so put the file name in `tag`.

### Explainer pages for a system

Build them with the kit, not hand-rolled Mermaid/card HTML (it reads as undesigned). Pattern: a thin host page with two same-origin iframes — an Archify `--template story` flow on top and a `data-story` page from real data below. The host passes its theme to both: `?theme=` for Archify; for the data story, click the embed's own `#theme` button on load, then size the iframe to `contentDocument.scrollHeight`.

## Animated pages → MP4 (showcase, crawl, mission-control)

- `creator.py showcase --input page.html --output x.mp4` records any page exposing `window.__ready` and `window.__advance(ms)` frame-exactly; otherwise use `--realtime`. Read `docs/SHOWCASE.md`. Capture costs ~0.1–0.2 s/frame at 1080p; run long renders in the background.
- `creator.py crawl --input SKILL.md --output NEW_DIR --video --speed 9` maps a prompt into a galaxy graph with a crawling spider and records it. The default scorer is keyword heuristics; `--scorer azure --allow-cloud` scores via logprobs on a small chat deployment. Neither scorer's numbers are measured accuracy.
- `creator.py mission-control render --input spec.json --output cockpit.html [--video cockpit.mp4]` builds the domain-agnostic orbital cockpit; read `docs/MISSION-CONTROL.md` and `examples/mission-control/`.

Verify by sampling frames from the MP4, not the live viewer.

## Dashboards (summary)

Full rules in `references/dashboards.md` and `docs/UI-DECISIONS.md`. Essentials:
- Every number is derived from one data source; no hand-typed figures, no placeholders.
- One attention cue (calm ping + `N needs you` pill); every click explains (why you, the decision, options, evidence).
- Every screen links home; a home page leads with an end-to-end flow, not a grid of cards.
- Not every domain is an orbit: pick the shape from `references/agent-dashboard-layouts.md`, build trials from one dataset, show them side by side, let the owner pick, then productize.
- `creator.py pipeline-control render --input spec.json --output X.html [--style] [--video]` for pipelines (default style `claude`); read `docs/PIPELINE-CONTROL.md`.

## Evidence-backed analytical pages

Build analytical content from one evidence model: headlines, deltas, charts and narration come from the same extract; keep real periods and filter scope; label interpretation separately. Validate displayed results, not just inputs.

- `creator.py data-story validate|render` (`docs/DATA-STORIES.md`, synthetic input under `examples/data-story/`).
- `creator.py fabric package --input story.html --output NEW_DIR --name app-slug` (`docs/FABRIC-EXPORT.md`) packages one self-contained HTML into a protected-static-hosting kit with an integrity-checked Node build. It never installs, authenticates or uploads.

When explaining to a stakeholder: what the user sees → how data reaches it → what hosting adds, then one worked example. A short brief that works: "Use our data-story pattern: clear narrative, source-backed charts, and an Explain panel for each figure. Responsive, light and dark themes." Details: `references/analytical-story-publishing.md`.

## Upgrading an existing app's charts

Apply the design rules inside that project's own stack; do not migrate it or add a chart CDN.
1. Screenshot the current page (1440 and 390, both themes) and get a vision critique. Fix what it names: unlabeled badges/axes, dot-blobs, tiny low-contrast ticks.
2. Proven upgrade set: a summary row of derived, clickable insights (scroll to and flash the card); a low-to-high range meter per card; 3–5 rounded gridline ticks, padded y-range, High/Low/current annotations clear of the tick column, hidden unchanged dots on dense series, a pointer crosshair that snaps to the nearest point while keeping keyboard focus.
3. Derive insights from the same function the cards use; run the test suite after each edit.
4. To view a production API locally when a browser tool refuses private hosts, run a tiny proxy (serve working-tree UI, forward `/api/*` to production) and drive it with Playwright. Scroll charts into view before hover tests.
5. **Adding a light theme:** map hard-coded hex to semantic CSS variables (dark default, `html[data-theme=light]` overrides). A toggle defaults to the system setting, saved in localStorage, applied by a tiny head script with an `id` (so tests that regex the first `<script>` are not confused). Run a contrast scan on every tab in light mode.
6. Deploy as a new immutable release from the current live release plus only changed files; keep a rollback; read back the served asset hash and re-run browser checks in production.

## Upgrading the kit from external design tools

1. Read each repo's metadata and README (`gh api repos/<o>/<r>`, `.../readme`): stars, license, last push, what it actually does. Social-post claims are not evidence. Check `creator.py --help` to map onto existing commands.
2. Rank by fit: a reusable contract every renderer consumes (style tokens, a gate) beats a second render engine. Take recipes from overlapping tools rather than their runtime. Name blockers plainly.
3. Propose phases; on approval implement the smallest phase end to end: vendored with license + lock JSON, one subcommand, tests, docs/INDEX/CHANGELOG, real-browser proof.
4. For a single site you like: in a browser, pull real tokens with one script pass (computed font families/colours over the first ~400 elements, plus every `@keyframes`/animation/transition/backdrop/mask/gradient rule), then screenshot + vision for layout. Report the 5–8 techniques with actual values, map each to a command, recommend 1–2.
5. Show the result: render several variants, run the gate, build a contact sheet (`ffmpeg ... hstack/vstack`), get an independent vision critique. Report honestly what improved (palette re-skin vs new layout).

Distinguish research, a one-off production script and a reusable feature. Add a capability to docs only after its entry point works end to end. Scripts under `productions/` are not shipped commands.

## Model-assisted editing

Documented in `MODELS-AND-EDITING.md`. Run `creator.py discover --subscription <id>` then `creator.py models` rather than assuming deployment names; listing is not proof of inference access. Tokens stay in memory; cloud commands require `--allow-cloud`.

Flow: `plan` (instruction → timeline; `--analyze` and/or `--srt file.srt` add silence intervals, scene cuts and transcript cues without uploading video) → review the JSON → `validate` → `edit` (local bounded FFmpeg). Edit plans support `retime_subtitles: true`, `burn_subtitles: true` (needs an FFmpeg with libass), and `bgm` + `bgm_volume` + `bgm_duck: true` (sidechain ducking under speech). `image` calls GPT Image; `transcribe` writes Whisper SRT (no diarization). `creator.py bundle --production DIR` writes a non-overwriting `manifest.json` with SHA-256 hashes, durations, cover pick and open decisions (`docs/BUNDLE.md`).

Verify every requested edit in the exported media: probe, sample frames/audio, inspect real subtitle streams. Apply protocol/demuxer restrictions to every input and to ffprobe.

## Voices (pick by default, don't ask)

`creator.py narrate --script SCRIPT.md --output NEW_DIR --engine azure|f5|kokoro|qwen3|chatterbox` produces per-line WAVs, `narration.wav` and a zero-delta `timeline.json`. Read `docs/VOICES.md`; the engine registry is `integrations/voice-models.json`. Local engines bootstrap on first use unless `--offline`; `creator.py voices list|fetch` manages them.

- **Azure Speech:** set `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` (simplest), or use an Entra-discovered Speech account from the inventory (`--speech-account`). Requires `--allow-cloud`. Best choice for Hebrew and other languages the local engines lack.
- **Stock English narrator (local):** `--engine qwen3 --voice Ryan|Aiden --instruct "..."`.
- **Your own voice:** `--engine qwen3 --ref ref.wav --ref-text "<exact transcript>"` (faster than F5) or `--engine chatterbox --ref ref.wav`. Only clone voices you have consent for.
- Verify every new engine/language with a Whisper read-back. Read-back proves the words, not naturalness; a human listens before choosing.

## Studio editor and repo hygiene

Build the React editor with `cd studio-ui && npm ci && npm run build`, then `python3.13 creator.py studio` (loopback port 4318). Follow `SETUP.md`. Verify with `studio-ui/verify-studio.mjs` (synthetic upload, split, save, undo/redo, render, download, restart). Check mobile width after a project loads.

Git does not back up `productions/`, `local/`, credentials or upstream checkouts. `upstream-lock.json` records installed revisions; never silently upgrade vendors. Prefer loopback; LAN binding has no login or TLS.

## Updating the vendors

Fetch each vendor, read what changed, update, rebuild, then prove it: HyperFrames `init → check → render` + ffprobe; OpenMontage pytest in its own venv with `env -u PYTHONPATH -u PYTHONHOME` (a leaked PYTHONPATH fakes import errors); kit `pytest tests`. Archive stray untracked files first. Record revisions in `upstream-lock.json` and CHANGELOG. Trial a major Archify release in a scratch copy: 3.x removed guided/story views (breaks `--template story`, presenter chapters, `--showcase-bridge`). An FFmpeg build without libass/freetype has no `drawtext`/`subtitles`; burned captions fail until a full build is installed.

## Opening artifacts for review

`open file.html` can land in another browser profile. Open a new window with one tab per variant and read back the active title and tab count before saying it is open; reload tabs after regenerating. "Clear the old versions" means move superseded files to the Trash (recoverable, never `rm`) and close tabs for them, then verify exactly one matching tab remains. When closing tabs by script, rescan after each close instead of iterating a fixed index.

## Messaging for stakeholder-facing video

- End on value, not disclaimers. Closing chips and line should mirror what the video proved (faster signal, proof on every value, human in the loop), not POC caveats.
- Before anything goes public: no named colleagues or customers, synthetic data only, internal metrics removed. Internal-build is not cleared-to-publish.

## Handing a prompt to another agent session

Give the full prompt as plain text with every placeholder filled from context (ask for the one missing fact instead of leaving `<...>`). Point the other agent at this skill, the docs, the example spec and `design-check`, and require real data with no hand-typed numbers.

## Verify a render is real

```bash
ffprobe -v error -show_entries stream=codec_name,codec_type renders/video.mp4
# expect: h264 video + aac audio
```
Then extract and look at real frames (`ffmpeg -ss T -i video.mp4 -frames:v 1 frame.png`). Lint-clean is not done.

## Paid models (optional)

OpenMontage keys go in `OpenMontage/.env` (copy `.env.example`). `FAL_KEY` (fal.ai) unlocks FLUX images and hosted video models; everything else is additive. Nothing is required for the offline path.
