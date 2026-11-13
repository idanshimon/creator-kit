# React Bits — creator-kit integration guide

## Scope and evidence

Repository: https://github.com/DavidHDev/react-bits
Docs/catalog: https://reactbits.dev
Source reviewed at revision `e12c22192ac7b4b452c5e2feb9b586d74765d696`.
This guide is source/registry research, not an installed Studio integration or a successful export test. No MCP server or package was installed during this research. Refresh selected source and the license before adopting a newer revision.

React Bits supplies editable React component source and browser asset tools. It is not a video editor, narration engine, caption system or replacement for HyperFrames/OpenMontage. The README advertises 215+ free components; do not treat registry-item totals as component totals: variants, sounds and other entries are separate records. Paid React Bits Pro templates/Agent Kit are a separate offering, not entitlements supplied by the public repo.

## Choose a lane before implementation

1. Interactive React/Next.js page: copy only the selected component variant and its dependencies into the consuming project. Match its existing package manager, React version and styling system.
2. Video/deck assets: prefer a browser-tool image/video/audio export when a baked asset is sufficient, then import that asset through the existing production workflow. Keep foreground text and narration readable.
3. Frame-exact animation: adapt source to the production's explicit-time contract or re-author the effect in the existing GSAP scene. Do not assume an unmodified React component can seek.
4. Portable offline reading HTML: use an embedded still or baked asset. Do not silently add React/CDNs/hidden entrance states to a document that must work offline with content visible by default.

Start with one purposeful effect per scene/section. For serious customer material, subtle title reveal + quiet background is usually better than cursor toys, physics, incessant scrambling or multiple competing animations. Styling is not evidence of a product capability.

## Task → useful components

These names and dependencies were checked against the pinned `public/r/registry.json`. Inspect actual selected source/props before using; dependency choices have changed across revisions.

| Goal | Shortlist | Dependency/behavior note |
|---|---|---|
| Staggered headline | SplitText | `gsap`, `@gsap/react`; uses GSAP SplitText and ScrollTrigger plugins |
| Soft text reveal | BlurText | `motion` (`motion/react` imports) |
| Rotating headline phrases | RotatingText | `motion`; freeze the intended final phrase in exports |
| Typewriter / code title | TextType | `gsap`; align cadence with narration, leave reading time |
| Technical decryption motif | DecryptedText | `motion`; random glyphs/timers need deterministic adaptation |
| Shimmer / gradient heading | ShinyText, GradientText | No additional registry dependencies at this revision; still React components |
| Grounded metric reveal | CountUp | `motion`; sourced final values only, not invented impact metrics |
| Section/card entrances | AnimatedContent, FadeContent | `gsap`; scroll triggers are not video timeline cues |
| Product feature cards | SpotlightCard, TiltedCard | No additional registry dependencies; pointer-driven behavior needs a static fallback |
| Before/after visual | PixelTransition | Hover/click behavior; script the transition explicitly for video |
| Quiet ambient background | Aurora, Silk, Threads | Inspect WebGL/browser requirements; no extra registry dependencies at this revision |
| Technical atmosphere | Particles, Beams, Dither | Budget GPU cost and contrast; no extra registry dependencies at this revision |
| Brand strip / gallery | LogoLoop, CircularGallery | Use authorized logos/screenshots; not a substitute for live app evidence |

Do not install the documentation site's whole `package.json`: Chakra, icons, Three, OGL, physics, shader tooling and other site dependencies are not all needed by an individual component. An empty registry dependencies array does not mean no React/browser runtime, zero GPU cost or universal SSR support.

## Source installation and provenance

Four standard UI variants:

| Variant | Source root |
|---|---|
| JS-CSS | `src/content/` |
| JS-TW | `src/tailwind/` |
| TS-CSS | `src/ts-default/` |
| TS-TW | `src/ts-tailwind/` |

For our TypeScript React UI use TS-CSS unless the consuming app already uses Tailwind; use TS-TW when it does. Do not add Tailwind just for an effect. Read each manifest because some non-UI entries use other suffixes.

Canonical registry config (merge into, never replace, the consuming app's `components.json`):

```json
{"registries":{"@react-bits":"https://reactbits.dev/r/{name}.json"}}
```

Upstream-documented commands, to run through `terminal` only after inspecting the target project and package manifest:

```bash
npx shadcn@latest add @react-bits/SplitText-TS-TW
npx jsrepo@latest add https://reactbits.dev/r/SplitText-TS-CSS
```

These commands fetch current registry content; they do NOT pin the source reviewed here. For reproducibility, prefer downloading/copying the chosen files from the pinned Git revision, retain the license, inspect imports and install only required packages using the app's package manager and lockfile. Record repo URL, revision, source paths, variant, modifications and dependency versions in the production manifest. Do not overwrite Studio/HyperFrames lockfiles or silently upgrade their pinned GSAP.

Manifest lookup: `https://reactbits.dev/r/SplitText-TS-TW.json`. Direct live-registry reads returned HTTP 403 from the research environment; immutable GitHub-hosted manifests were successfully retrieved and checked instead. If the site blocks retrieval, use the official repository's `public/r/<Name>-<Variant>.json` and pinned source files; do not treat an HTML denial page as JSON or claim the CLI install succeeded.
Pinned source example: `https://raw.githubusercontent.com/DavidHDev/react-bits/e12c22192ac7b4b452c5e2feb9b586d74765d696/src/ts-default/TextAnimations/SplitText/SplitText.tsx`.

Concrete docs pitfall: the generic manual-install example only says `npm install gsap`, but pinned SplitText imports `@gsap/react` too and its manifest lists both. Trust selected source imports + registry metadata over a simplified installation paragraph. Check GSAP/plugin licensing separately; React Bits' license does not replace dependency licenses.

## Browser asset tools

Capabilities below are documented by upstream; selected export implementation was inspected, but exports were not exercised in this research.

| Tool | URL | Fit in our workflow |
|---|---|---|
| Background Studio | https://reactbits.dev/tools/background-studio | Tune backgrounds/presets, export code, high-resolution image or MP4/WebM; use as a quiet bed behind authored content |
| Center Stage | https://reactbits.dev/tools/center-stage | Place a real screenshot/recording in phone/laptop/browser product-shot scenes; upstream advertises 4K images/video, GIF and share links |
| Shape Magic | https://reactbits.dev/tools/shape-magic | Shape/SVG/text marks with chrome/glass/neon materials; export SVG/PNG/favicon/video/React |
| Texture Lab | https://reactbits.dev/tools/texture-lab | Stylize images/video/camera with ASCII/halftone/glass/glitch effects; export image/video/GIF |
| Sound Lab | https://reactbits.dev/tools/sound-lab | UI stingers/clicks/transitions, tune effects, export WAV/MP3/OGG or component code; not narration or a full music generator |

Center Stage's source exporter renders explicit sample times and negotiates available codecs; advertised MP4 does not guarantee H.264, and 4K presets do not prove a device actually exports 4K. Probe actual dimensions, codec, duration and audio. Background Studio checks browser video-encoding support. Sound Lab can write WAV directly; MP3/OGG have additional encoding paths. Prefer WAV as an editing intermediate.

For every asset: save original export plus chosen settings, retain its source/license provenance, inspect dimensions/duration/alpha/loop seam, sample real output pixels/audio, then import into `productions/<name>/`. Avoid needless re-encoding. Add narration/captions/music/muxing through existing verified tools; do not assume a product-shot video preserves the source recording's audio.

Use synthetic or cleared screenshots/media in hosted tools. Source availability is not a privacy audit: do not assume local-only processing or upload confidential customer records based on a README. Do not create a public share link for private material. Inspect actual network/storage behavior if sensitive media must be used.

Center Stage polish must not be described as recorded interaction unless the underlying input is a real exercised application capture. Texture transformations must not obscure evidence, important numbers or controls.

## Deterministic video adaptation

The inspected sources show why a working web preview is not yet a frame-exact production:

- SplitText: waits for fonts, builds internal GSAP timelines, and defaults to view-triggered playback. `trigger="load"` changes the trigger, not ownership of the timeline. Delay is stagger in milliseconds; duration is seconds. Do not guess the same units for every component.
- CountUp: `useInView` and Motion `animate` drive internal playback. `startWhen` and `trigger` are start gates, not a pure seek API. Derive displayed value from render time when adapting.
- DecryptedText: random glyph selection, intervals/timeouts, intersection events and optional hover/click effects require seeded/indexed randomness and explicit-time state (or use a baked clip).
- Aurora at this revision: raw WebGL2, no OGL import; exposes `time`, `paused`, `intro`, `mouseInteraction`, `dpr`. The shader uses `time * speed * 0.1` when time is supplied, but intro/pointer state has its own RAF evolution. A promising adapter sets `paused`, `intro={false}`, `mouseInteraction={false}`, fixed `dpr` and explicit `time`, awaits React commit/draw, then verifies equal-time pixels. This is a source-derived adaptation recipe, NOT a tested exporter.

Use the existing production contract (`window.__ready`, `window.__advance(ms)`, `window.__done()` for `creator.py showcase`, or `window.seek(t)` for the standalone renderer). Confirm whether a hook expects absolute time or elapsed increments in the renderer implementation; hook names alone do not define semantics. A wrapper must commit React state and complete canvas draws before capture, and must not let an independent RAF race the capture clock.

For HyperFrames, use its established composition/timeline contract. React source cannot simply be pasted into a normal HTML frame. Prefer a baked asset or re-author the small effect with the already-pinned GSAP rather than importing a new React runtime into every frame.

## License gate — not plain MIT

Read the actual pinned `LICENSE.md`, not GitHub's generic license label or marketing shorthand. This revision is **MIT + Commons Clause License Condition v1.0** (copyright 2026 David Haz).

The text permits use within personal/commercial applications, websites or products and requires copyright/permission notices in copies or substantial portions. It prohibits selling, sublicensing or redistributing the components themselves, alone, bundled or ported. It also restricts redistribution of the tools/sounds and offering the tools or a substantially similar copy as a hosted service. Exports may be used within applications/sites/products, but may not be sold or redistributed on their own as, for example, sound/background/texture/template packs.

Practical rule: incorporate a selected effect or exported asset into an authored production; do not mirror the library, ship a reusable asset pack, or copy its tools into our Studio and assume that is permitted. A hosted Background Studio/Center Stage clone requires separate review/permission. Retain notices and examine Texture Lab/Shape Magic third-party notices when using their adapted code. Do not label the repo OSI-open-source or plain MIT. Paid Pro assets have separate terms/access; do not scrape around them.

## Optional agent discovery

React Bits uses the **shadcn MCP server**, not a proprietary React Bits MCP service. The docs configure the above registry in the consuming project and connect the client to `npx shadcn@latest mcp`. Registry HTTP reads/manual source inspection are sufficient for research and do not require installing MCP.

Install MCP servers only through your agent client's supported, user-approved connection flow; do not paste another client's config snippets into it. This guide records capability, not installed connection state.

## Verification checklist for actual use

1. Source revision, variant, imports/dependencies and retained notices recorded; review dependency diff and production-specific license scope.
2. Build/typecheck the consuming app; inspect browser console; verify SSR/client boundaries and clean unmount (timers, listeners, WebGL resources). Some reviewed components have `use client`; check the selected file rather than assuming the entire library is SSR-safe.
3. Verify light/dark, narrow width, keyboard/touch fallback, reduced-motion and text contrast. Provide a CSS/static fallback when WebGL is missing; Aurora otherwise returns without drawing.
4. Await fonts and assets before measuring or recording text. Ensure text settles before the scene ends, captions remain clear and effects do not imply unsupported metric/capability claims.
5. For deterministic adapters, test first/middle/final states plus repeated/reverse/out-of-order equal-time seeks. Use fixed viewport/DPR/fonts/random seed and compare resulting pixels, not only JS state.
6. For baked exports, probe the actual file and visually inspect every scene, final seconds and loop boundary; verify audio separately. A preview, declared export preset or valid file alone is not proof of final quality.

## Primary sources

All GitHub paths below are relative to the immutable reviewed revision:
https://github.com/DavidHDev/react-bits/tree/e12c22192ac7b4b452c5e2feb9b586d74765d696

- `README.md`: scope, browser tools, installation and separate Pro offering.
- `LICENSE.md`: Commons Clause restrictions and use of exports.
- `package.json`: documentation-site dependency/build footprint, not an install-everything recipe.
- `src/docs/Installation.jsx`, `src/docs/McpServer.jsx`: CLI/registry/client setup.
- `public/llms.txt`: searchable catalog; includes Pro marketing, not just public-source components.
- `public/r/registry.json`, `public/r/SplitText-TS-TW.json`, `public/r/Aurora-TS-CSS.json`: component IDs, variants and declared dependencies.
- `src/ts-default/TextAnimations/{SplitText,CountUp,DecryptedText}/`: actual timing/trigger/import behavior.
- `src/ts-default/Backgrounds/Aurora/Aurora.tsx`: explicit time, RAF, WebGL2 and fallback behavior.
- `src/tools/background-studio/{BackgroundStudio.jsx,components/MediaExport.jsx,hooks/useStageFrame.js}`: export UI, encoding checks and frame bridge.
- `src/tools/center-stage/{CenterStage.jsx,export/exporters.js}`: product shots, sampled-time export and codec negotiation.
- `src/tools/sound-lab/export/encode.js`: WAV/MP3/OGG encoding paths.
