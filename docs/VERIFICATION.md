# Verification

How to check that the kit works, and what each check proves. Re-run them after any
source change and on every new machine.

## 1. End-to-end proof on a new machine: `scripts/smoke.sh`

After `scripts/bootstrap.sh`, run:

```bash
scripts/smoke.sh
```

This is the end-to-end proof for a fresh install: it exercises the real CLI and local
tools on your machine. Results recorded here do not prove your own setup works; run it.

## 2. Python unit suite

```bash
env -u PYTHONPATH -u PYTHONHOME python3.13 -m pytest tests -q
# or, stdlib only:
python3.13 -m unittest discover -s tests -v
```

| Area | Modules under `tests/` |
|---|---|
| CLI dispatch and hardening | `test_cli`, `test_hardening`, `test_projects`, `test_assets`, `test_bundle` |
| Editing engine (real FFmpeg fixtures: trim/order, framing, mixed audio, speed, fades, subtitles, no-overwrite, provenance) | `test_editing`, `test_editing_controls` |
| Azure model inventory and adapters (mocked; no live cloud calls) | `test_models` |
| Narration (Azure key and Entra auth paths, SSML, timeline) and local voices | `test_narrate`, `test_local_tts` |
| Studio server (Host/Origin/CSRF checks, revisions, media restrictions, LAN binding) | `test_studio`, `test_studio_lan` |
| Diagrams, showcase, GSAP motion, styles, wall | `test_diagrams`, `test_diagram_templates`, `test_showcase`, `test_motion`, `test_styles`, `test_wall` |
| Data stories and Fabric export kit | `test_data_story`, `test_fabric_export`, `test_fabric_cli` |
| Mission Control and its Ask server | `test_mission_control`, `test_mission_ask` |
| Pipeline control, designer agent | `test_pipeline_control`, `test_designer` |

Run when this kit was prepared: **214 passed, 4 skipped, 97 subtests passed**. Skipped
tests need an optional local prerequisite that was not installed. Mocked adapter tests
do not establish live cloud access.

## 3. Browser harnesses (`studio-ui/verify-*.mjs`)

These drive an installed Chrome/Chromium against locally generated pages, offline, with
temporary workspaces and synthetic media (no personal media, no model calls). Run from
`studio-ui/` after `npm ci` (see [studio-ui/README.md](../studio-ui/README.md)):

| Script | Checks |
|---|---|
| `verify-studio.mjs` | Editor flow: create, upload, split, save, undo/redo, draft render, range streaming, download, restart/reopen, 390px mobile width |
| `verify-browser.mjs` | General page load and layout |
| `verify-data-story.mjs` | Data story controls, values match CLI facts, inert hostile copy, no network requests (`PYTHON=python3.13 node verify-data-story.mjs`) |
| `verify-diagrams.mjs`, `verify-diagram-templates.mjs` | Archify diagram rendering and templates |
| `verify-gsap-motion.mjs` | GSAP preview play/pause/seek, scrubber, layout fit |
| `verify-mission-control-zoom.mjs`, `verify-mission-ask.mjs` | Mission Control zoom/layout and the Ask pane request flow |

Evidence (reports, screenshots) goes to `local/verification/`, which is not committed.

## 4. UI package and specs

```bash
cd studio-ui
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm test
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm run build
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npx tsc -p tsconfig.json --noEmit
cd .. && openspec validate --all --strict
```

Structural spec validity does not certify behavior; the tests above do that.

## Not covered

- Live Azure inference or Speech calls on your account (run them with `--allow-cloud`
  after `python3 creator.py discover`). Azure Speech key auth is unit-tested; Entra
  auth was live-verified by the maintainer. See [VOICES.md](VOICES.md).
- Fresh full OpenMontage/HyperFrames installs or upstream upgrades.
- Listening review of narration quality.
- Browsers other than the Chromium build you run the harnesses with.
- Backup of `productions/` or `local/`; Git does not include them.
