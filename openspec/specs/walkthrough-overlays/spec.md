# walkthrough-overlays Specification

## Purpose
Provide offline, dependency-free HTML overlays (`<sdlc-loop>` compact stage dial and `<story-rail>` full-column story map) that show which stage a walkthrough chapter or video segment is discussing, without implying task completion. Baseline backfilled 2026-11-22 from `templates/overlays/` and `studio-ui/verify-sdlc-loop.mjs`.

## Requirements
### Requirement: Offline classic-script components
Each overlay SHALL ship as a single classic script with no imports, network requests, fonts or build step, define its custom element at most once, and isolate its styles in Shadow DOM.

#### Scenario: Open the demo from disk
- **WHEN** `templates/overlays/sdlc-loop/demo.html` is opened via `file://` with no server or network
- **THEN** the stage map renders and responds to chapter navigation.

### Requirement: Host-owned narrative stage
The host page SHALL set the narrative stage through `setStage(id)` and `setStage(null)` for overview; the overlay SHALL start in overview, highlight the active stage with a text label and ordinal, and SHALL NOT present the active or final stage as verified completion.

#### Scenario: Backward and repeated navigation
- **WHEN** the host moves forward to a later chapter and back to an earlier one
- **THEN** the highlighted stage matches the chapter's mapped stage, and `setStage(null)` clears the highlight.

#### Scenario: Video sync
- **WHEN** an HTML video seeks backward or plays an unmapped intro
- **THEN** the documented integration resolves the stage from `currentTime` on loadedmetadata, timeupdate, seeked and emptied, yielding the correct stage or overview.

### Requirement: Inspection independent of narration
Selecting a stage to inspect (click, tap, keyboard or picker) SHALL show that stage's detail without changing the narrative stage, and later narrative updates SHALL NOT be blocked by an open inspection.

#### Scenario: Inspect while a chapter is active
- **WHEN** the narrative stage is Plan and the viewer inspects Resolved
- **THEN** the inspection shows Resolved while the current stage remains Plan.

### Requirement: Validated stage lists
`sdlc-loop` SHALL default to Issue, Triage, Plan, Implement, Checks, Review, Merge, Resolved; replacing `stages` SHALL require a non-empty list of unique non-blank IDs and labels, SHALL throw on invalid lists or unknown IDs, and SHALL leave the prior state unchanged on error.

#### Scenario: Invalid input
- **WHEN** the host assigns duplicate IDs or calls `setStage` with an unknown ID
- **THEN** the call throws and the current stage is unchanged.

### Requirement: Accessible responsive presentation
`sdlc-loop` SHALL support keyboard operation (Tab, Enter/Space, Home/End, Escape), follow system light/dark unless `theme` is set, disable transitions under reduced motion, use a picker instead of dial nodes when more than eight stages exist, and fit a 360px-wide touch viewport without horizontal overflow.

#### Scenario: Phone emulation
- **WHEN** verified at 360x740 with touch, dark theme and reduced motion
- **THEN** the map stays inside the viewport, page width does not overflow, and transition duration is zero.

### Requirement: HTML-only scope
Documentation SHALL state that overlays live in the HTML player and are not burned into MP4 exports, and SHALL distinguish the automated `sdlc-loop` browser test from `story-rail`, which has no automated test.

#### Scenario: MP4 opened alone
- **WHEN** a rendered MP4 is played without its HTML host
- **THEN** no overlay is claimed to appear.
