# Creator models and video edits

Local agent/CLI extension, outside both vendored repositories. The CLI needs no web
server; the optional `studio` command now serves a React browser editor over local HTTP.
No public endpoint or cloud resource creation is required. Python standard library
plus existing Azure CLI, FFmpeg and ffprobe. See [Studio operations](docs/STUDIO.md)
and use `python3.13 creator.py --help` (Python 3.10+).

## Model discovery and auth

Pass your subscription explicitly; discovery does not change the active Azure account:

```bash
python3 creator.py discover --subscription '<subscription-name-or-id>'
python creator.py models --capability chat
python creator.py models --capability image
python creator.py models --capability transcription
```

Inventory is `local/azure-inventory.json`, gitignored and refreshable. It covers
Cognitive Services account deployments only, not undeployed catalog entries, Azure ML
endpoints, or third-party providers. It records errors per account. An empty deployment
list in a failed account is NOT proof of absence. Model capability is classified by name;
`inference_verified:false` means inventory is not a live inference probe. Chat/image/SRT
adapters have distinct contracts; not every classified deployment accepts every adapter.

Entra bearer tokens are minted by Azure CLI per call, held in process memory, never
printed or saved. No API keys are requested. You need an existing `az login` session with
inference permission; management read access alone is insufficient. No automatic paid
retries on failure or 429. Images default to one 1024px low-quality generation.

Model IDs below are placeholders of the form `<account>/<deployment>`; run
`python3 creator.py models` to find yours:

```bash
python creator.py chat --model <account>/<chat-deployment> \
  --prompt 'Suggest a clear closing line for a video editing tutorial.' --allow-cloud

python creator.py image --model <account>/<image-deployment> \
  --prompt 'A minimalist cyan circle on a navy background, no text.' \
  --output productions/my-project/assets/hero.png --allow-cloud

python creator.py transcribe --model <account>/<whisper-deployment> \
  --input /absolute/path/narration.wav --output /absolute/path/captions.srt --allow-cloud
```

Transcription currently uses **Whisper SRT**, not the separate diarization model.
Supported uploads must be local and under 25 MiB. `transcribe` sends the media to Azure;
`chat`/`image` send prompts. Every cloud command requires `--allow-cloud` explicitly.
Outputs never overwrite an existing file. Image and transcription outputs have provenance
sidecars naming the model and checksums, without credentials.

## Reviewable model-assisted editing

```bash
python creator.py probe /absolute/path/source.mp4
python creator.py plan \
  --input /absolute/path/first.mp4 /absolute/path/second.mp4 \
  --model <account>/<chat-deployment> \
  --prompt 'Take seconds 1–3 of the second clip first, then seconds 0–2 of the first. Output 720x1280, fit contain, keep audio.' \
  --output productions/my-edit/plan.json --allow-cloud

# Read/review plan.json before rendering; a plan call does not render.
python creator.py validate --plan productions/my-edit/plan.json
python creator.py edit --plan productions/my-edit/plan.json \
  --output productions/my-edit/renders/video.mp4
```

**The model sees technical metadata and your instructions, NOT video frames or a
transcript.** It cannot identify a person, pick a highlight, or remove spoken filler by
meaning. Content-dependent requests are instructed to return an actionable error. No
claim of semantic understanding is made. For content analysis use the existing
OpenMontage analysis/transcription tools; transcript-to-timeline integration is future work.

The same timeline can be written by a human or agent without a cloud model:

```json
{
  "version": 1,
  "clips": [
    {"path": "/absolute/path/second.mp4", "start": 1, "end": 3},
    {"path": "/absolute/path/first.mp4", "start": 0, "end": 2}
  ],
  "width": 720,
  "height": 1280,
  "fit": "contain",
  "mute": false,
  "volume": 1
}
```

The executor is intentionally bounded: local sources only, explicit ranges, fixed
operations, no generated shell commands or arbitrary filtergraphs, maximum 100 clips
and 600 seconds, output dimensions even and <=3840. Models can only reference sources
explicitly supplied to `plan`. Resolution changes are contain/center-cover, not face
tracking.

For captions, add `"subtitles": "/absolute/path/captions.srt"` (or `.vtt`) to a
**reviewed local plan**. By default the renderer embeds a selectable `mov_text` subtitle track.
If the subtitle file has source-clip timestamps and your plan trims, reorders, or changes clip
speed, set `"retime_subtitles": true` to deterministically clamp, scale (`1/speed`), and shift
cues onto the edited timeline. Set `"burn_subtitles": true` to also render burned-in captions
onto the video stream via FFmpeg's `libass` `subtitles` filter.

For a background audio bed, add `"bgm": "/absolute/path/bed.wav"` (with optional
`"bgm_volume": 0.25` in `0..2` and `"bgm_duck": true`). When `bgm_duck` is true (default),
the bed is automatically attenuated under speech via `sidechaincompress`.

For content-aware edit planning, pass `--analyze` and/or `--srt captions.srt` to `creator.py plan`
(or `creator.py probe --analyze --srt captions.srt`). That feeds deterministic FFmpeg
`silencedetect` intervals, scene-cut timestamps, and parsed subtitle cues into `source_metadata`
without uploading raw video bytes.

For multi-voice broadcast narration, run `creator.py narrate --script SCRIPT.md --output productions/<name>/narration --engine azure --cast '{"TIM":"en-US-Andrew:DragonHDLatestNeural"}' --allow-cloud` (or `--engine f5` for offline voice clone, `--engine kokoro` for local draft). It handles Entra `Bearer aad#<resource-id>#<token>` regional auth, SSML entity escaping, >=20 KiB error-body gating, and builds a zero-delta `narration.wav` + `timeline.json`.

The vendored OpenMontage already offers richer face tracking, transitions,
silence removal, PiP and audio mixing; use it rather than
adding a redundant editing package.

## Speed, fades and draft exports

The version-1 schema also supports per-clip `speed` (0.25–4), `volume` (0–2) and
`mute`, plus top-level `fade_in` / `fade_out` seconds (each at most half of the
effective output duration). Total duration accounts for speed. Audio speed adjustment
preserves pitch. These are real renderer operations, not model-only suggestions.

`creator.py edit --profile draft` limits the longest side to 640 without upscaling;
`--profile final` retains requested dimensions. Output paths must still be new.
`models --capability` also accepts embedding, video, realtime and unknown; those are
inventory classifications only and have no corresponding first-party inference adapters.

## Tests and limits

```bash
python -m unittest discover -s tests -v
```

Tests use generated technical fixtures, not personal or customer media.
Live proof artifacts live in `local/verification/`. Unit mocks test adapter contracts;
only actual Azure outputs establish live access. A generated plan is not a rendered
video; a valid codec alone is not visual quality proof.

The browser timeline editor is now implemented; see [Studio](docs/STUDIO.md). There is
no newly integrated text-to-video generation model, OpenTimelineIO interchange or
authenticated hosted multi-user service. Existing
OpenMontage paid providers remain optional and separate. The five-project OSS comparison
is research, not a claim that those projects have been installed.

## Screenshot-grounded UX/UI designer agent

`creator.py design-review --model RESOURCE/DEPLOYMENT --brief brief.txt --images screen1.jpg screen2.png --output new-review.json --allow-cloud` reviews one to three explicit screenshots and proposes two light/dark palette alternatives with rendering and UX recommendations. It never edits or deploys application code. Select an actually deployed vision-capable chat model; inventory alone does not establish inference compatibility. The JSON captures real returned model/usage and screenshot hashes. Existing outputs are refused. Only PNG/JPEG signatures under4MiB are accepted.

Review outputs are suggestions, not accessibility certification. Apply required domain colour meanings, calculate text contrast, and inspect actual rendered materials/phone geometry before accepting a design. Shader lighting can turn mathematically correct amber into muddy brown; neutral geometry with unlit semantic caps can fix the renderer rather than randomly changing thresholds or colours.

For reasoning-heavy models, the agent requests low reasoning effort so bounded output is not exhausted before the review; incomplete responses are rejected rather than silently treated as valid.
