# AGENTS.md — Creator Kit

You are a coding agent working in Creator Kit, an agent-driven studio for narrated
videos, motion graphics, interactive diagrams and data stories. Read this whole file
before doing anything. It tells you how to set the kit up, how to make things with it,
and the rules that keep the output honest.

## 1. Bootstrap (first session on a machine)

Do these in order. Do not skip the proof in step 5.

1. **Check state.** Run `scripts/bootstrap.sh --check`. It changes nothing and lists
   what is installed and what is missing.
2. **Install missing prerequisites.** The check names each missing tool with an install
   command (Python 3.10+, Node 18+, npm, Git, FFmpeg/ffprobe, Bun, Google Chrome). On
   macOS use Homebrew. Ask the user before installing system packages if you are not
   sure they want you to.
3. **Run the bootstrap.** `scripts/bootstrap.sh`. It installs HyperFrames, OpenMontage
   and Archify at the revisions pinned in `upstream-lock.json`, builds the Studio editor,
   creates `.env` from `.env.example`, and runs the doctors and unit tests. It takes
   several minutes the first time. If a step fails, read the error, fix the cause, re-run;
   it is safe to re-run. Never "fix" it by upgrading a pinned dependency.
4. **Credentials (optional).** The free path needs none. If the user wants Azure Speech
   voices, ask them for their Speech key and region and write them to `.env` as
   `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`. Never invent, guess or print keys, and
   never commit `.env`. SETUP.md section 4 has the portal steps if they need a resource.
5. **Prove it.** Run `scripts/smoke.sh`. Setup is done only when it prints `PASS` and
   `productions/smoke-*/smoke.mp4` exists. Tell the user the path so they can watch it.
6. **Load the skills** (section 3) for the agent you are.

Report what ran and what passed. If something could not be completed (for example no
Chrome, or ffmpeg without libass), say exactly which features that affects.

## 2. What is here

| Path | Role |
|---|---|
| `creator.py`, `creator_tools/` | First-party CLI, Python standard library only. `python3 creator.py --help` |
| `studio-ui/` | Browser editor (`python3 creator.py studio`, http://127.0.0.1:4318) and browser verification scripts (`verify-*.mjs`, `design-check.mjs`) |
| `skills/` | Agent skills for this kit |
| `docs/` | One page per feature, indexed in `docs/INDEX.md` |
| `examples/` | Synthetic inputs for every renderer; copy them to start |
| `templates/motion/gsap/` | GSAP composition template used by `creator.py motion create` |
| `integrations/` | Locks, licenses, brand palettes (`design-md/`), voice-model registry |
| `hyperframes/`, `OpenMontage/`, `archify/` | Upstream tools installed by the bootstrap. Git-ignored. **Do not edit them**; they are pinned dependencies |
| `productions/<name>/` | Where every piece of work goes. Git-ignored |
| `local/` | Studio database, downloaded voice models, Azure inventory. Git-ignored |

## 3. Skills

Load the kit's skills before producing anything:

| Skill | Use it for |
|---|---|
| `skills/creator-studio/` | Router: which tool for which job, design rules, style choice, verification |
| `skills/video-production/` | Narrated explainer and walkthrough videos, end to end |
| `skills/motion-graphics-renderer/` | Self-contained HTML motion scenes rendered to exact-timed MP4 |
| `skills/creator-arsenal/` | Extra building blocks: React Bits visuals, Blender 3D assets, evidence-backed walkthroughs |

After the bootstrap, HyperFrames adds its own skills in `hyperframes/skills/`
(`hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`,
`reverse-any-video`, `style-sampling`, `slideshow` …). Start video authoring at
`hyperframes/skills/hyperframes/SKILL.md`.

How to load them:
- **Claude Code**: `mkdir -p .claude/skills && for s in skills/* hyperframes/skills/*; do ln -sfn "$PWD/$s" ".claude/skills/$(basename "$s")"; done`
- **GitHub Copilot CLI / Codex / others**: read the relevant `SKILL.md` at the start of a
  task (they are plain Markdown), plus any `references/` file it points to.
- **Hermes**: `for s in skills/*; do ln -sfn "$PWD/$s" ~/.hermes/skills/creative/"$(basename "$s")"; done`

## 4. Making a video (the standard workflow)

1. **Agree the story.** Ask what it is for, who watches, how long. Write `story.md` in
   `productions/<name>/` with three short storyline options; the user picks one.
2. **Spec and script.** Write `SPEC.md` (canvas, scenes, timing, caption keep-out) and
   `SCRIPT.md`. Script format is strict: each scene is `## Title (Frame N)` and the
   spoken text sits on 4-space-indented lines under it. Any other heading shape parses
   as zero lines and produces a silent film.
3. **Narrate.**
   `python3 creator.py narrate --script productions/<name>/SCRIPT.md --output productions/<name>/narration --engine kokoro`
   (free, local). Better local voices: `--engine qwen3 --voice Ryan`. Cloud:
   `--engine azure --allow-cloud`. Several speakers: `--cast '{"HOST":"af_heart","GUEST":"am_michael"}'`
   with a `**Speaker:** NAME` line under the scene heading. Output: `voice/*.wav`,
   `narration.wav` and a zero-delta `timeline.json`, which is the master clock for the scenes.
4. **Build scenes.** `(cd hyperframes && npx hyperframes init ../productions/<name>/film --skip-skills --skill=hyperframes)`,
   then one composition per scene in `compositions/`. Scene work is context-heavy: give
   each scene to its own subagent if you can, with the project path, scene id, canvas
   size, keep-out area and its SPEC block.
5. **Check and review.** In the film folder, `npx hyperframes check --json` must report
   0 errors (warnings are acceptable). Run `npx hyperframes snapshot --review` and look
   at the frames.
6. **Render.** `npx hyperframes render`.
7. **Verify the real MP4** (section 6), then give the user the file path.

Other outputs follow the same pattern; read the matching doc first:
motion title → `docs/GSAP.md`; record a page → `docs/SHOWCASE.md`; diagram →
`docs/DIAGRAMS.md`; data story → `docs/DATA-STORIES.md`; dashboards →
`docs/MISSION-CONTROL.md` / `docs/PIPELINE-CONTROL.md`; cut and trim existing footage →
`docs/STUDIO.md` or `creator.py plan/edit` in `MODELS-AND-EDITING.md`.

## 5. Rules

- **Work in `productions/<name>/`.** Never write into the upstream checkouts.
- **New output paths.** Commands refuse to overwrite; choose a new folder or filename.
- **Cloud is opt-in.** Anything that sends data to a cloud service needs `--allow-cloud`
  on that command and the user's agreement. Do not add paid usage silently.
- **Secrets stay in `.env`.** Never print, log or commit keys. `.env` is git-ignored.
- **Numbers come from data.** In data stories and dashboards every figure is derived from
  the input file; never hand-type a number into a page.
- **Do not claim what you did not check.** "Rendered" means an MP4 exists and you
  inspected it. A clean lint or a valid ffprobe does not prove it looks or sounds right.
- **Ask before** installing system packages, deleting anything in `productions/`, or
  changing a pinned version.
- **Studio is local.** Keep it on 127.0.0.1. LAN mode has no login and no TLS.

## 6. Verifying output

```bash
ffprobe -v error -show_entries stream=codec_name,codec_type -of csv=p=0 out.mp4   # expect h264 + aac
ffmpeg -v error -ss <T> -i out.mp4 -frames:v 1 frame.png                         # sample frames
```

Look at frames from the start, middle and especially the **end** of each scene (late
reveals are what usually break). Listen to the audio. For HTML pages run
`python3 creator.py design-check --input page.html --shots productions/<name>/shots`
and look at the screenshots in light and dark themes.

## 7. Known pitfalls

1. **Script headings** must be `## Title (Frame N)`; otherwise no narration.
2. **First Kokoro run** downloads the model; parallel calls can fail once. Re-run.
3. **Every scene root needs `data-duration`** on its `data-composition-id` element.
4. **Clips on the same track cannot overlap in time**; move one to another track index.
5. **Kokoro gives no word timings**, so no auto captions from it alone. Use a Whisper
   pass (`creator.py transcribe`, cloud) or align the WAVs locally.
6. **Animations after the scene's real end never play.** Narration sets the scene length;
   after narrating, check that the last tween in each scene starts before its duration.
7. **Changing a narration line changes its length.** Re-narrate, re-check that scene's
   late reveals, re-render, and update any on-screen text that must match the voice.
8. **Burned-in captions need FFmpeg with libass**; Homebrew's default ffmpeg lacks it.
9. **Archify stays on 2.16**; 3.x removed the guided views the story template uses.

## 8. Testing the kit itself

```bash
python3 -m unittest discover -s tests            # unit tests (no network)
(cd studio-ui && npm test && npm run build)      # editor
scripts/smoke.sh                                 # end-to-end on this machine
```

Browser checks in `studio-ui/verify-*.mjs` use Chrome; set `CHROME_PATH` and
`CREATOR_PYTHON` if yours are not at the default locations.
