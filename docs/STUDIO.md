# Studio operations

## Launch

Build `studio-ui/dist/` first (see [setup](../SETUP.md)), then:

```bash
python3.13 creator.py studio
python3.13 creator.py studio --port 4319 --workspace /absolute/private/workspace
```

Default: `127.0.0.1:4318`, workspace `local/studio`. Stop the foreground service with
Ctrl+C. Do not point an experimental server at the normal workspace during tests.

## Editing loop

1. New project; import MP4/MOV/M4V/WebM/MKV/AVI, at most 256 MiB each.
2. Add to timeline, then select a source. Source preview is **not** a composed preview.
3. Set in/out, split, duplicate, reorder/remove. Adjust speed (0.25–4), per-clip
   volume/mute, output framing, global audio and fades.
4. Save a named revision. Undo/redo operate on saved versions, not individual unsaved
   keystrokes. Unsaved edits are guarded on navigation but are not persisted drafts.
5. Draft renders at most 640px on the longest side; Final retains requested dimensions.
6. Review/download the actual export. An older revision's output is labeled stale.

At most three jobs may be queued/running, with one worker. A full queue or a stale
revision returns 409. Reload a stale project before deciding how to reapply edits.

## Security and LAN

Loopback is the default. Explicit `--host` accepts a specific RFC1918 IPv4 address;
public/wildcard addresses are rejected. This option is for trusted LAN peers only:

```bash
# Example address only: replace with your host's actual private IPv4.
python3.13 creator.py studio --host 192.168.1.20
```

**No login, user separation or TLS exists.** Any reachable peer can read `/api/state`,
obtain its CSRF token, inspect the workspace and make authorized-format edits. Host,
Origin, CSRF and CSP checks defend request boundaries, not user identity. No public
tunnels, router forwarding or shared untrusted-network deployment.

Media IDs are registered; arbitrary file serving is rejected. FFmpeg inputs are
protocol/demuxer restricted but not sandboxed: import trusted media. Uploads are
buffered in memory within the cap, not streamed to support unlimited files.

## Recovery and backup

The workspace contains `studio.sqlite3`, `media/` and `exports/`. Preserve them together.
Stop the server before copying the complete workspace. Stored plans contain absolute
paths, so restore to the same location; cross-path workspace migration is not built.
Interrupted jobs become failed on restart; render again deliberately.

Git does not include this workspace or productions; back them up separately.

## Current limits

- No Studio subtitle import (CLI selectable SRT/VTT only).
- No multitrack drag/resize, waveforms, music ducking or transition editor.
- No automatic retiming of captions after cuts/speed changes.
- No semantic highlight selection or cloud controls in the UI.
- No simultaneous-user authorization; optimistic concurrency is conflict detection.
- Chromium-based desktop browser exercised; cross-browser/platform behavior is not certified.
