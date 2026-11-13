# Setup

## 1. Install the prerequisites

| Tool | Version | macOS | Ubuntu/Debian |
|---|---|---|---|
| Python | 3.10+ | `brew install python@3.13` | `apt install python3 python3-venv` |
| Node + npm | 18+ | `brew install node` | [nodejs.org](https://nodejs.org) or nvm |
| Git | any | Xcode command line tools | `apt install git` |
| FFmpeg + ffprobe | 6+ | `brew install ffmpeg` | `apt install ffmpeg` |
| Bun | 1.x | `curl -fsSL https://bun.sh/install \| bash` | same |
| Google Chrome | current | chrome.com | chrome.com |

Burned-in captions need an FFmpeg built with libass (the `subtitles` filter). Homebrew's
default `ffmpeg` does not include it; everything else works without it. The bootstrap
tells you which one you have.

## 2. Run the bootstrap

```bash
scripts/bootstrap.sh            # everything
scripts/bootstrap.sh --minimal  # only the browser editor + CLI
scripts/bootstrap.sh --check    # report status, change nothing
```

It is safe to re-run. It:

1. checks the prerequisites above;
2. creates `.env` from `.env.example` (all values optional);
3. builds the browser editor (`studio-ui`, `npm ci` against the committed lockfile);
4. clones **HyperFrames** and **OpenMontage** at the exact revisions in
   [upstream-lock.json](upstream-lock.json), installs their dependencies, and adds the
   free Kokoro voice to OpenMontage's virtualenv;
5. downloads the **Archify** release and installs it only if its SHA-256 matches
   [integrations/archify-lock.json](integrations/archify-lock.json);
6. runs `motion doctor`, `diagram doctor` and the unit tests.

It never resets, upgrades or deletes an existing checkout. If a checkout is at a
different revision than the lock, it says so and leaves it alone.

## 3. Prove it works

```bash
scripts/smoke.sh
```

This narrates one line with Kokoro, renders a GSAP title card, records it to MP4, muxes
the audio and checks the result (h264 + aac, length matches the narration). It writes
`productions/smoke-<time>/smoke.mp4` and a frame grab. Open the video and listen: the
script checks structure, not whether it looks and sounds right.

The first run downloads the Kokoro voice model, so it needs network and takes longer.

## 4. Optional: cloud voices and models

Put credentials in `.env` (git-ignored). `creator.py` reads it automatically and never
overrides variables already set in your shell.

**Azure Speech** (natural DragonHD voices, Hebrew and many other languages):

1. In the Azure portal create a *Speech* resource (the free F0 tier is enough to start).
2. Copy *Key 1* and the *Region* (for example `eastus`) into `.env`:
   ```
   AZURE_SPEECH_KEY=...
   AZURE_SPEECH_REGION=eastus
   ```
3. `python3 creator.py narrate --engine azure --allow-cloud --script SCRIPT.md --output productions/x/narration`

If your organization disables key auth on Speech resources, leave both empty and use
Entra sign-in: `az login`, then `creator.py discover --subscription <id>` (see
[MODELS-AND-EDITING.md](MODELS-AND-EDITING.md)).

**Azure OpenAI** (images, planning, transcription): `az login`, then `creator.py discover`
and `creator.py models`. Every inference command needs `--allow-cloud`.

**Paid video/image models in OpenMontage** (FLUX, Kling, Veo …): put `FAL_KEY` in
`OpenMontage/.env`. Optional; nothing in the free path needs it.

## 5. Agent skills

`skills/` holds the kit's agent skills as plain Markdown. [AGENTS.md](AGENTS.md#skills)
explains how to load them in Claude Code, Copilot CLI, Codex or Hermes. HyperFrames
ships its own video-authoring skills in `hyperframes/skills/` after the bootstrap.

## Updating the pinned tools

Upgrades are deliberate, never automatic. To move a dependency: fetch it, read what
changed, check out the new revision, rebuild, run `scripts/smoke.sh` and the tests, then
update `upstream-lock.json` and [CHANGELOG.md](CHANGELOG.md). Archify 3.x removed the
guided views that `--template story` and `--showcase-bridge` rely on, so it stays on 2.16.

## What Git does not hold

`productions/`, `local/` (Studio database, voice models, Azure inventory), `.env` and the
upstream checkouts are all git-ignored. Back up `productions/` yourself.
