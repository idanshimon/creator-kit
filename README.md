<div align="center">

<img src="docs/assets/readme/hero.svg" alt="Creator Kit — animated banner" width="100%"/>

<a href="#-quick-start"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=24&duration=2600&pause=700&color=FF3CAC&center=true&vCenter=true&width=900&lines=Explainer+videos+%F0%9F%8E%AC;Narrated+walkthroughs+in+5+voice+engines+%F0%9F%8E%99%EF%B8%8F;GSAP+motion+graphics+%E2%9C%A8;Mission+Control+cockpits+%F0%9F%9B%B0%EF%B8%8F;Prompt+galaxies+%F0%9F%8C%8C;Source-backed+data+stories+%F0%9F%93%8A;All+local.+Zero+API+keys.+%F0%9F%94%92" alt="what it makes"/></a>

<br/>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-render-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)
![GSAP](https://img.shields.io/badge/GSAP-motion-88CE02?style=for-the-badge&logo=greensock&logoColor=black)
![React](https://img.shields.io/badge/Studio-React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Local](https://img.shields.io/badge/100%25-local_by_default-ff3cac?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-ffd166?style=for-the-badge)

**Describe it to your coding agent. Get back a narrated, animated, verified MP4.**
<br/>Claude Code · GitHub Copilot CLI · Codex · Hermes — any agent that can read Markdown.

</div>

---

## 🎬 The machine

<img src="docs/assets/readme/pipeline.svg" alt="script, narrate, scenes, render, verify, ship" width="100%"/>

Your agent writes the script, voices it, builds the scenes, renders a frame-exact MP4 and then
**checks its own work** (ffprobe, sampled frames, listening to the audio) before calling it done.

---

## 🔥 Made with this kit — every frame below is real output

> Each clip was rendered straight from the files in [`examples/`](examples/) with one `creator.py` command. No hand-editing.

<table>
<tr>
<td width="50%" valign="top">

### 🛰️ Mission Control cockpit
<img src="docs/assets/readme/mission-control.gif" alt="Mission Control orbital cockpit animation" width="100%"/>

Orbital fleet view, a 7-beat agent loop, an approval gate and live detail cards — from one typed JSON file.

```bash
python3 creator.py mission-control render \
  --input examples/mission-control/finops-governance.mission.json \
  --output mc.html --video mc.mp4
```

</td>
<td width="50%" valign="top">

### 🌌 Prompt-Crawler galaxy
<img src="docs/assets/readme/prompt-crawler.gif" alt="Prompt crawler galaxy animation" width="100%"/>

Point it at any prompt or `SKILL.md`. A spider crawls every instruction and sorts it into **code / model / human**, then scores the spec.

```bash
python3 creator.py crawl \
  --input skills/video-production/SKILL.md \
  --output crawl --video --speed 9
```

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🚦 Pipeline Control
<img src="docs/assets/readme/pipeline-control.gif" alt="Pipeline Control animation" width="100%"/>

Turns a CI run log into a flow line, "what changed" cards with baselines, and an agent approval card.

```bash
python3 creator.py pipeline-control render \
  --input examples/pipeline-control/checkout-service.pipeline.json \
  --output pc.html --video pc.mp4
```

</td>
<td width="50%" valign="top">

### 📊 Evidence data stories
<img src="docs/assets/readme/data-story.png" alt="Data story page" width="100%"/>

Reading pages where every number points back to its source. Light and dark themes, no network needed.

```bash
python3 creator.py data-story render \
  --input examples/data-story/synthetic-workshop.json \
  --output story.html
```

</td>
</tr>
</table>

---

## 🧰 The superpowers

| | Power | One-liner |
|---|---|---|
| 🎙️ | **Five voice engines** | Kokoro, Qwen3, Chatterbox, F5 voice clone, Azure Speech → `narration.wav` + a synced `timeline.json` |
| ✨ | **GSAP motion** | Code-authored title cards and motion graphics you can seek frame by frame |
| 🏛️ | **Architecture diagrams** | Interactive Archify diagrams with an optional guided video tour |
| 🎥 | **Record anything** | `creator.py showcase` turns any animated web page (D3, canvas, three.js) into a frame-exact MP4 |
| 🧱 | **Hero wall** | Your past work as drifting columns with hover-pause and lightbox |
| 🎨 | **Brand styles + design QA** | Brand palettes, plus a browser gate for contrast, overflow and "AI-look" tells |
| ✂️ | **Browser Studio** | Cut, trim, speed, fades, music ducking and captions — non-destructive |
| 🔒 | **Safe by default** | Nothing leaves your machine unless you pass `--allow-cloud` |

<details>
<summary><b>🤖 Talk to it like this</b></summary>

> *"Read AGENTS.md and bootstrap this repo."*
>
> *"Make a 60-second narrated explainer of how our checkout pipeline works, dark theme, Kokoro voice."*
>
> *"Crawl my SKILL.md and give me the galaxy video for LinkedIn."*
>
> *"Turn this run log into a Pipeline Control page and record it."*

</details>

---

## ⚡ Quick start

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

## 🗺️ What you can make

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

## 🔧 How it fits together

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

## 📁 Repository map

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

## 🛡️ Safety defaults

- Nothing is uploaded unless you pass `--allow-cloud` on that command.
- Credentials live in `.env` (git-ignored); see [.env.example](.env.example).
- Commands refuse to overwrite existing outputs; pick a new path.
- The Studio listens on 127.0.0.1. `--host` with a private LAN address works but has
  **no login and no TLS**; never expose it to the internet.

## 📜 License

First-party code: [MIT](LICENSE). Upstream tools and vendored assets keep their own
licenses (AGPL-3.0, Apache-2.0, MIT, GSAP Standard License); see [NOTICE.md](NOTICE.md).


<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff3cac,50:784ba0,100:00f5d4&height=120&section=footer&text=Go%20make%20something%20loud&fontColor=ffffff&fontSize=28&animation=twinkling" width="100%"/>

</div>
