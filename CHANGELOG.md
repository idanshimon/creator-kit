# Changelog

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
