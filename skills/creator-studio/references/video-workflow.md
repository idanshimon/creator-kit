# Narrated video workflow (HyperFrames / OpenMontage)

Install per `SETUP.md`. Author under local-only `productions/<name>/`.

## Flow

Start from HyperFrames' own `skills/hyperframes/SKILL.md`: its "What to read" table routes each film type to `references/types/<type>.md`. Then:

`story.md` (three storylines; the requester picks) → `SPEC.md` → one sub-composition per scene in `compositions/` → `npx hyperframes check --json` → `snapshot --review` + `REVIEW.md` → render.

Scaffold with `npx hyperframes init <dir> --skip-skills --skill=hyperframes`. The usage beacon (`hyperframes events`) is telemetry: set `HYPERFRAMES_NO_UPDATE_CHECK=1` and skip it for confidential work. Scene building is context-heavy: use one subagent per scene, briefed with project dir, scene id, canvas, caption keep-out zone and its SPEC block.

For narration you can also use `creator.py narrate` (see SKILL.md, Voices).

## Pitfalls (all hit in practice)

1. **SCRIPT.md headings must be `## Title (Frame N)`.** `## Frame 1 — hook` parses as zero lines → silent film. Spoken text goes on a 4-space-indented line under each heading.
2. **First Kokoro run races:** the model downloads on first call and parallel TTS calls fail. Re-run the audio step once.
3. **Every frame root needs `data-duration`** on the `data-composition-id` element, or transition injection fails.
4. **Same-track overlaps fail assembly:** two `class="clip"` on the same `data-track-index` with overlapping windows. Move one to its own lane.
5. **Offline Kokoro gives no word timings** → captions skipped. Recover timings with a WhisperX pass over the WAVs, or use a timed TTS.
6. **Lint warnings are shippable** (`google_fonts_import`, `studio_missing_editable_id`); 0 errors is the gate.
7. **Reveal timings must fit the synced frame duration, not the storyboard estimate.** Duration sync shrinks a frame to its real narration length; tweens scheduled after the new end never play and the element is silently missing. Check the last `tl.fromTo(...)` offset < the synced `data-duration`.
8. **Verify frames with `npx hyperframes snapshot --at <T>` + a vision model.** Times are in assembled-timeline seconds. To see a frame's final state, snapshot near its end, not its midpoint.

## Revising a finished video

- **On-screen copy with matching narration must change in both places.** Update the `SCRIPT.md` line and regenerate that audio (`npx hyperframes tts "<text>" --voice af_heart --output assets/voice/NN.wav`), re-run the audio step so metadata picks up the new duration, then re-sync → assemble → inject → render.
- **A changed line changes its duration**, re-triggering pitfall 7 on that frame. Re-check late reveals and any clip whose start + duration now exceeds the frame.
- **Verify from the actual MP4.** Snapshots cap near the timeline end. Extract the true final frame with `ffmpeg -y -ss <T> -i renders/video.mp4 -frames:v 1 final.png` and look at it. Reviewers go frame by frame; confirm each changed frame visually.
