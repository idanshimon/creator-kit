# Walkthrough evidence, review and voice variants

## Build the story from exercised screens

Start with one person's task, not the system's internals. For each beat record: page/route, actual control type and label, entity/run ID, pre-state, action, response/post-state and captured asset. Keep static seed pages distinct from live-stream cohorts; do not imply continuity between unrelated IDs. Annotated screenshots illustrate; real browser recordings demonstrate clicks. A synthetic cursor on an inert chip proves neither approval nor dispatch.

A long-lived stream is not evidence a page cannot be captured. Wait for an explicit DOM/data condition rather than network-idle; use available browser/CDP/desktop recording capabilities. Do not encode failed capture attempts as permanent tool limitations.

## NotebookLM as a critic, not a clinical authority

Upload a controlling brief with the intended end-user persona, rejected-version context, verified screen evidence and explicit unknowns. Check every listed source has actually finished processing. If screenshots were requested, upload actual images or a visual PDF, not only an interpretation of them. Read back the source list to verify counts and titles.

Ask for jargon removal, missing decisions and concrete click sequencing. Independently verify suggestions before changing the product. Do not accept clinical statements such as “these terms are mutually exclusive”, diagnosis inferred from a device trend, or “the patient is safe” merely because an LLM cited the script. A stale reading does not necessarily establish absent connectivity: wording must match what was measured. Demo timeouts are not clinical cutoffs.

## Geometry verification

Use DOM bounding boxes or measured capture regions. Map screenshot coordinates through scale, crop, pan and viewport offsets in code; check both frame bounds and caption occlusion. Guessing positions highlighted a different patient. A dimming spotlight can obscure the very evidence it highlights. Re-capture after product changes, but do not overwrite an approved cut's assets. Automated contrast checks on HTML text do not inspect text baked into screenshot pixels.

Sample all scene types, reveal times, transitions and the click moment from the rendered MP4. Name the samples inspected; never say “watched the video” after inspecting two stills. ffprobe and volume metrics establish technical validity, not wording or voice resemblance.

## Existing voice clone and timing

Use your own existing voice-clone setup (e.g. `creator.py narrate --engine f5|qwen3|chatterbox --ref your.wav`) before generating. Do not upload reference voice recordings to an external service without authorization. Generate separate scene tracks, verify expected count and non-empty duration in code, and transcribe representative lines to compare with the locked script. Transcription proves wording, not speaker likeness.

A voice swap changes narration timing. Derive scene starts/durations from actual WAV durations, then retime animation cues too. Frame-offset translation preserves rough scene positions, not word alignment: confirm phrase-level timing, especially approvals/clicks, using the new audio. Preserve the original composition as the retiming baseline; repeated regex substitutions on already-retimed HTML accumulate errors.

For HyperFrames local TTS, if Kokoro is installed in a dedicated venv, explicitly set HYPERFRAMES_PYTHON to that venv's interpreter. Read current CLI help for text-file/output flags; don't suppress synthesis errors in a batch. Stable unique audio IDs are required by the renderer to discover narration. Validate assets before render and inspect the resulting audio/video afterward.

## Approved-version preservation

Save output, locked script, composition, all referenced audio/images/fonts/vendor files, timing metadata and renderer version. Compute and store checksums. Keep a newly requested voice variant beside the approved original; do not label the new voice itself approved until the user approves it. Verify the archived composition resolves assets relative to its saved location.

A text-only repository with pointers to local audio/images cannot rebuild on another machine. Do not promise exact rebuilding from incomplete assets or floating CDN dependencies. If remote backup is requested, use a permitted artifact store/release/LFS strategy and read it back; avoiding binaries in git is a repository decision, not a universal prohibition. Never delete older cuts merely because a newer render completed.
