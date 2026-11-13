# Creator Kit

An agent-driven studio for explainer videos, narrated walkthroughs, motion graphics,
interactive architecture diagrams and data stories. You describe what you want to your
coding agent (Claude Code, GitHub Copilot CLI, Codex, Hermes …); the agent uses this
kit to write the script, narrate it, build the scenes, render an MP4 and check the result.

Everything runs on your machine. The default path is free and needs no API keys. Cloud
services (Azure Speech voices, Azure OpenAI images and planning, paid video models) are
optional, use your own credentials, and only run when you pass `--allow-cloud`.

## Quick start

```bash
git clone <this repo> creator-kit && cd creator-kit
scripts/bootstrap.sh        # installs pinned tools; safe to re-run
scripts/smoke.sh            # renders a short narrated MP4 to prove the chain works
python3 creator.py studio   # browser editor at http://127.0.0.1:4318
```

Using an agent? Point it at [AGENTS.md](AGENTS.md) and say *"read AGENTS.md and
bootstrap this repo"*. It contains the full setup, the rules and the workflows.

Prerequisites: Python 3.10+, Node 18+, npm, Git, FFmpeg/ffprobe, Bun (for HyperFrames)
and Google Chrome (for recording HTML to MP4). `scripts/bootstrap.sh` checks all of them
and tells you what to install. `--minimal` installs only the editor and CLI.

## What you can make

| Goal | Tool | Start here |
|---|---|---|
| Narrated explainer / product walkthrough video | HyperFrames + `creator.py narrate` | [skills/video-production](skills/video-production/SKILL.md) |
| Narration with many voices, synced timeline | `creator.py narrate` (Kokoro, Qwen3, Chatterbox, F5, Azure Speech) | [docs/VOICES.md](docs/VOICES.md) |
| Animated title cards and motion graphics | `creator.py motion` (GSAP) + `creator.py showcase` | [docs/GSAP.md](docs/GSAP.md), [docs/SHOWCASE.md](docs/SHOWCASE.md) |
| Interactive architecture diagram, optional video tour | `creator.py diagram` (Archify) | [docs/DIAGRAMS.md](docs/DIAGRAMS.md) |
| Data story with source-backed charts | `creator.py data-story` | [docs/DATA-STORIES.md](docs/DATA-STORIES.md) |
| Operator dashboards (cockpit, pipeline flow) | `creator.py mission-control`, `pipeline-control` | [docs/MISSION-CONTROL.md](docs/MISSION-CONTROL.md), [docs/PIPELINE-CONTROL.md](docs/PIPELINE-CONTROL.md) |
| Hero wall of past work | `creator.py wall` | [docs/WALL.md](docs/WALL.md) |
| Brand palettes + automatic design QA | `creator.py style`, `design-check` | [docs/STYLES.md](docs/STYLES.md) |
| Cut, trim, speed, fades, music ducking, captions | Browser Studio or `creator.py edit` | [docs/STUDIO.md](docs/STUDIO.md), [MODELS-AND-EDITING.md](MODELS-AND-EDITING.md) |
| Record any web page to frame-exact MP4 | `creator.py showcase` | [docs/SHOWCASE.md](docs/SHOWCASE.md) |

Run `python3 creator.py --help` for the full command list.

## How it fits together

```
your request ──► agent reads AGENTS.md + skills/
                     │
     script ──► creator.py narrate ──► narration.wav + timeline.json
                     │
     scenes ──► HyperFrames compositions / GSAP motion / Archify diagram
                     │
                     ▼
            render (HyperFrames or creator.py showcase) ──► MP4
                     │
                     ▼
     verify: ffprobe + sampled frames + listen ──► productions/<name>/
```

First-party code lives in `creator.py`, `creator_tools/` and `studio-ui/`. Three upstream
open-source projects are installed at pinned revisions by the bootstrap (they are not
copied into this repo): [HyperFrames](https://github.com/heygen-com/hyperframes),
[OpenMontage](https://github.com/calesthio/OpenMontage) and
[Archify](https://github.com/tt-a1i/archify). See [NOTICE.md](NOTICE.md).

## Repository map

| Path | What it is |
|---|---|
| `AGENTS.md` | Instructions for coding agents: bootstrap, workflows, rules |
| `skills/` | Agent skills (plain Markdown, work with any agent) |
| `creator.py`, `creator_tools/` | The CLI (Python standard library only) |
| `studio-ui/` | Browser editor (React) and browser verification scripts |
| `scripts/` | `bootstrap.sh`, `smoke.sh` |
| `docs/` | One page per feature; [docs/INDEX.md](docs/INDEX.md) lists them |
| `examples/` | Synthetic input files for each renderer |
| `templates/` | Reusable starting points (GSAP motion) |
| `integrations/` | Pinned locks, licenses, brand palettes, voice-model registry |
| `openspec/` | Capability specifications |
| `tests/` | Unit tests (`python3 -m unittest discover -s tests`) |
| `productions/` | Your work. Git-ignored; back it up yourself |

## Safety defaults

- Nothing is uploaded unless you pass `--allow-cloud` on that command.
- Credentials live in `.env` (git-ignored); see [.env.example](.env.example).
- Commands refuse to overwrite existing outputs; pick a new path.
- The Studio listens on 127.0.0.1. `--host` with a private LAN address works but has
  **no login and no TLS**; never expose it to the internet.

## License

First-party code: [MIT](LICENSE). Upstream tools and vendored assets keep their own
licenses (AGPL-3.0, Apache-2.0, MIT, GSAP Standard License); see [NOTICE.md](NOTICE.md).
