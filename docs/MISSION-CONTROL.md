# Mission Control Orbital Cockpits (`creator.py mission-control`)

`creator.py mission-control` generalizes a **Mission Control v3**
orbital cockpit (`2D-canvas + D3 radial sectors + concentric severity rings + 7-beat
agent dial + selected-entity watcher satellites + left/right operator rails`) into a
domain-agnostic, zero-CDN HTML & MP4 generator for any governed agentic workflow
(FinOps, cybersecurity SOC, claims triage, supply-chain ops, clinical monitoring).

## Author → Validate → Render (HTML + optional MP4)

Start from [`examples/mission-control/finops-governance.mission.json`](../examples/mission-control/finops-governance.mission.json):

```bash
python3.13 creator.py mission-control validate \
  --input examples/mission-control/finops-governance.mission.json

python3.13 creator.py mission-control render \
  --input examples/mission-control/finops-governance.mission.json \
  --output productions/finops-demo/mission-control.html

# Also record a frame-exact 1080p MP4 choreography stepping through sectors + approval gate:
python3.13 creator.py mission-control render \
  --input examples/mission-control/finops-governance.mission.json \
  --output productions/finops-demo/mission-control-v2.html \
  --dwell 1800 \
  --video productions/finops-demo/mission-control.mp4
```

Add `--style <name>` (see [STYLES.md](STYLES.md)) to re-skin with a DESIGN.md brand palette, and gate the output with `creator.py design-check`.

## What the generated artifact includes

- **Top bar:** Branding, badge (`v3`), live search input, synthetic-telemetry disclosure pill, and **Light / Dark** sRGB theme toggle (`--mc-*` palette owner across CSS and 2D canvas).
- **Cohort scope bar:** `All <noun>` plus one tab per sector, showing whole-cohort vs current-scope counts, critical count, pending human reviews, and model ID.
- **Left rail:** Total watched count + live tick, **Viewing As** persona card (role, italicized core question, operational context, crossing→ack metric), **Cohort Mix** severity bars (`Critical`, `Concerning`, `At-Risk`, `Stable` — click to filter), and searchable entity list.
- **Center 2D orbital canvas:**
  - Fixed starfield + radial glow backdrop (switches cleanly to light surface in Light mode).
  - Sector dividers, labels, and pulsing amber/copper outer fault arcs (`!N`).
  - Concentric severity rings (`critical` closest to center → `concerning` → `at-risk` → `stable` outermost).
  - **Needs-attention cue:** critical items and a `human` watcher with status `waiting` get a calm 2 s ping; the scope bar shows a pinging `N needs you` pill. Reduced motion → steady rings. Android only: one short vibration per new item after the first tap.
  - Center agent hub with the 7-beat dial (`1 Change` → `2 Notice` → `3 Decide` → `4 Approve` → `5 Act` → `6 Adapt` → `7 Prove`) and hex `GATE` marker on the active arm.
  - Selected-entity satellite ring drawing every watcher (`rule`, `model`, `human`, `system`) with live weighted beams and metric callouts displaced clear of the center dial. Callouts are rounded chips tinted with the watcher colour (not panel rectangles); HUD and legend are translucent pills.
  - Map gestures: mouse wheel zooms toward the cursor (60–600%), drag pans, click selects, double-click resets; touch pinch-zooms around the fingers, one-finger pans, tap selects (Pointer Events; `touch-action:none` only on the canvas so the page still scrolls). `+` / `−` / live `%` buttons remain. Proof: `cd studio-ui && node verify-mission-control-zoom.mjs <file.html>`.
- **Right rail:** Selected entity inspector (summary, 2×2 metric tiles, interactive **Approve / Reject** human gate box, and color-coded watcher cards) + 7-beat loop trace.
- **Deterministic `showcase` hooks:** Exposes `window.__ready`, `window.__advance(ms)`, and `window.__done()` to automatically step through `All` → each sector + its highest-score entity → active entity approval when recorded with `creator.py showcase` or `--video`.

## Authoring with real data

`validate` and `render` return `warnings` (non-fatal) for copy that breaks phones or hides
meaning: long title words, long badge/banner/model, sector labels > 12, entity labels > 32,
URLs or tokens > 28 chars in visible text, long watcher values, and placeholder values
like `unleveled`/`unknown`. Treat warnings as defects in the builder that produced the
spec, not in the template. Full rationale: [UI-DECISIONS.md](UI-DECISIONS.md).

## Click-through detail (every click explains)

Clicking a dot, a worklist row, a watcher chip, a watcher row or a loop step opens a detail sheet
(right side on desktop, bottom sheet on phones; Esc, × or the backdrop closes it). **What can I
click?** in the top bar explains the screen. Content comes from optional, escaped fields:

```json
"detail": {
  "title": "Full item title",
  "why_you": "Why a person is needed (risk level, the agent stopped, low confidence).",
  "decision": {"question": "One plain question", "how": "Where the answer goes",
               "options": [{"label": "Approve", "effect": "What happens", "recommended": true, "url": "https://…"}]},
  "sections": [{"title": "What the agent found", "text": "…", "items": ["…"]}],
  "timeline": [{"t": "11-06 15:20", "text": "Issue opened", "url": "https://…"}],
  "evidence": [{"label": "run 42236531824", "url": "https://…"}]
}
```

Watchers take `detail: {text, url}`; `agent.beat_help` (one line per beat) explains each loop step.
Only `http(s)` URLs survive validation. A critical item without `why_you` or `decision` is a lint
warning: at scale the owner must see *why* and *what to decide* without opening another tool.
When `decision` is present, the inspector shows **Your decision → Decide…** instead of the demo
Approve/Reject buttons; options link to where the answer is recorded (an issue, a ticket).
Proof: `cd studio-ui && node probe-detail.mjs <file.html> <outdir>` (desktop click + phone tap,
help sheet, Esc) and `node probe-select.mjs <file.html>` (every item selectable).

## Briefing strip (`brief`, optional)

For meeting-prep and other briefings, put the must-see items above the cockpit instead of hiding them in a detail sheet:

```json
"brief": {"lead": "Customer RECORDS this call. Do not say: pricing, …",
          "items": [{"label": "Before 9:00", "text": "Open the diagrams", "entity": "DIAG", "tone": "warn"},
                    {"label": "Open with 4 questions", "lines": ["…", "…"], "entity": "CALL"}]}
```

`lead` renders as one red alert line; up to 8 `items` render as cards (`text` and/or numbered `lines`). An item with `entity` is a button that selects that entity and opens its detail sheet. All text goes through `textContent`. With a brief the page scrolls: the cockpit keeps a full viewport (min 640px) below it. The canvas re-measures with a `ResizeObserver`, so anything that changes the stage height (a brief, a host's injected nav strip) no longer leaves an over-tall canvas clipped by its panel.

## Ask agent (`mission-control serve`)

Serve a rendered page with a working **Ask** pane backed by the GitHub Copilot CLI:

```bash
python3.13 creator.py mission-control serve \
  --page cockpit.html --spec cockpit.spec.json \
  --workdir ./my-notes \
  --context-dir notes/<topic>/context --context-dir notes/<topic> \
  [--port 8766] [--no-workiq] [--model ID] [--log ask-log.jsonl]
```

- Binds `127.0.0.1` only (random free port unless `--port`). Checks `Host`; `POST /ask` also needs a same-origin `Origin`, `Content-Type: application/json` and `X-MC-Ask: 1`. Not user authentication: any process running as your user on the machine can call it.
- Each question runs `copilot -p <prompt> --output-format json` (argv list, no shell) with cwd = first `--context-dir`, `--add-dir` for the other context dirs and the folders of files the spec cites (found automatically), `--available-tools view grep glob workiq-ask_work_iq` (no shell, no edit, no write), other MCP servers disabled, and WorkIQ attached as an MCP stdio server (`workiq mcp`).
- The prompt carries the agent rules (plain short English, cite file path / WorkIQ item, "not in record" instead of guessing, read-only, data stays local), the full spec JSON and the selected item.
- Every question, the tools it called (with arguments) and the answer go to the JSONL log (default `<page>.ask-log.jsonl`): that is the evidence WorkIQ was actually called.
- `GET /src?p=<path>` returns an allowed source file as sandboxed plain text, so answer links are clickable; anything outside the context dirs/cited files is 404.
- Data path: questions and the files the agent reads go to GitHub Copilot (your Copilot account) and WorkIQ (M365); nothing else leaves the machine.
- Proof: `cd studio-ui && node verify-mission-ask.mjs http://127.0.0.1:PORT/ OUTDIR --file page.html --q "..."` asks through the real form, screenshots dark/light/phone and the static-file state.
