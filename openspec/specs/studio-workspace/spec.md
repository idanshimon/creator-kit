# Studio Workspace

## Purpose
Describe the implemented local React editor, Python HTTP API and SQLite project store.

## Requirements

### Requirement: Save explicit optimistic revisions
The Studio MUST persist saved project revisions and reject stale mutations with HTTP 409.
Undo/redo traverse the saved revision chain; unsaved browser edits are not durable revisions. The service stores media paths and is not a relocatable multi-user database.

#### Scenario: Competing saves
- **WHEN** two clients save using the same expected revision
- **THEN** only the first matching save succeeds and the later request is rejected

#### Scenario: Restart and reopen
- **WHEN** the server restarts with the same workspace
- **THEN** saved projects, revision history and registered media remain available

### Requirement: Translate the UI plan into the renderer contract
The UI MUST convert asset-ID/in/out clip state into version-1 path/start/end plans before persistence.
`studio-ui/src/lib/wire.ts` owns this mapping. UI clip IDs and preset names do not leak into the server plan. Studio accepts only registered asset paths and rejects subtitle imports; subtitle editing remains CLI-only.

#### Scenario: Missing asset mapping
- **WHEN** a UI clip has no registered source asset
- **THEN** serialization fails rather than persisting an arbitrary path

### Requirement: Preserve original uploaded media
The Studio MUST copy supported video uploads to its workspace and serve only registered media IDs.
The upload cap is 256 MiB. Media responses support byte ranges and HEAD. HTTP uploads are bounded but buffered in memory; this is not a streaming large-file service.

#### Scenario: Arbitrary path request
- **WHEN** a request attempts to serve a filesystem path instead of a registered media ID
- **THEN** the server rejects it

### Requirement: Expose real revision-bound render jobs
The Studio MUST render snapshots of saved plans and expose queued, running, succeeded or failed state.
There is one worker and at most three queued/running jobs. Successful jobs expose playable media and download links. Interrupted jobs are marked failed on restart, not silently resumed.

#### Scenario: Stale export
- **WHEN** a successful export was made from an older project revision
- **THEN** the UI labels it stale while retaining access to the original result

### Requirement: Distinguish source preview from composition
The UI MUST identify its source preview separately from a rendered export.
The editor supports select, trim, split, duplicate, reorder, remove and clip controls. It does not present the source player as a live composited multitrack preview.

#### Scenario: Narrow-screen controls
- **WHEN** the editor is opened at a 390px viewport with a saved timeline
- **THEN** the toolbar does not force horizontal page overflow and export controls remain reachable by scrolling

#### Scenario: Rendered review
- **WHEN** a draft job succeeds
- **THEN** the export panel offers its actual video for playback rather than merely showing the selected source
