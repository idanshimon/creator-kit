# Changelog

## 2026-11-16 — Archify 3.2

- Archify 2.16.0 → 3.2.0 (new lock; redesigned reader, Route/Lens, node index, five more diagram types upstream).
- Chapters: Archify 3 no longer draws `meta.views`, so the kit adds its own chapter bar (All, chapters, Play, note;
  `window.CreatorChapters`) on `Archify.focus.setMany`, styled with Archify's theme variables. `story`,
  `presenter`, `full` and `--showcase-bridge` / `--video` use it.
- New `outline` part hides Archify 3's node index (hidden in every template except `full`).
- Wrapper sets the `meta.output` Archify 3 requires and runs it from the private temp dir.
- Verified: 241 unit tests, `verify-diagrams.mjs`, `verify-diagram-templates.mjs`, and a 1080p `--video` render whose frames show All → 1 → 2 → 3.

## 2026-11-13 — First release

- CLI (`creator.py`): narration (Kokoro, Qwen3-TTS, Chatterbox, F5, Azure Speech with key
  or Entra), GSAP motion, frame-exact page recording (`showcase`), Archify diagrams, data
  stories, Mission Control and Pipeline Control dashboards, living wall, 74 brand styles
  with `design-check`, edit plans with captions and music ducking, optional Azure OpenAI
  adapters.
- Browser Studio editor (`studio-ui`) with revisions, undo/redo, draft/final renders.
- `scripts/bootstrap.sh` installs everything at pinned revisions; `scripts/smoke.sh`
  proves narration → motion → MP4 end to end.
- Agent skills in `skills/` and a full bootstrap guide in `AGENTS.md`.
