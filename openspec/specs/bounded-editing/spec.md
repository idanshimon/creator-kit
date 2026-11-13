# Bounded Editing

## Purpose
Describe the local deterministic renderer in `creator_tools/editing.py` and its version-1 timeline contract.

## Requirements

### Requirement: Validate local bounded timelines
The renderer MUST validate version-1 plans before invoking FFmpeg and reject unsupported keys, non-finite numbers, invalid ranges and nonlocal sources.
Limits are 100 clips, 600 seconds after speed adjustment, even output dimensions no greater than 3840 and per-clip speeds from 0.25 through 4.0. This is input restriction, not an OS sandbox.

#### Scenario: Out-of-bounds source range
- **WHEN** a clip extends beyond its probed source duration
- **THEN** validation rejects the plan without rendering

#### Scenario: Excessive effective duration
- **WHEN** slowing a clip makes the total output exceed 600 seconds
- **THEN** validation rejects the plan

### Requirement: Execute selected editing operations
The renderer MUST apply trim, order, concatenation, contain or center-cover framing, global and per-clip audio controls, speed and global fades to the exported media.
Speed uses pitch-preserving audio tempo adjustment. Fades are bounded to half the effective duration. No face tracking, transitions or multitrack composition are implemented in this adapter.

#### Scenario: Double-speed clip
- **WHEN** a four-second segment uses speed 2
- **THEN** the rendered segment lasts approximately two seconds within encoder tolerance

#### Scenario: Muted clip
- **WHEN** a clip is muted in a mixed-audio timeline
- **THEN** that output interval contains silence

### Requirement: Preserve inputs and distinguish output profiles
The renderer MUST preserve source media, refuse existing output paths and distinguish draft from final exports.
Draft limits the longest side to 640 without upscaling. Final retains requested dimensions. Successful output has provenance containing input/output checksums and effective timing.

#### Scenario: Existing output
- **WHEN** an export targets an existing file
- **THEN** the renderer refuses instead of replacing it

### Requirement: Embed and optionally retime or burn in reviewed local subtitles
The CLI renderer MUST embed supplied SRT or VTT as a selectable mov_text track, and SHALL support deterministic timeline retiming (`retime_subtitles: true`) and libass burn-in (`burn_subtitles: true`) when requested on the plan.
When `retime_subtitles` is true, source cues overlapping each clip window are clamped, scaled by `1/speed`, and shifted to that clip's cumulative timeline offset before muxing or burn-in.

#### Scenario: Captioned local plan
- **WHEN** a valid reviewed plan includes a subtitle file
- **THEN** the output exposes a subtitle stream containing its text

#### Scenario: Retimed and burned-in captions across cuts
- **WHEN** a valid plan sets `retime_subtitles: true` and `burn_subtitles: true` on a trimmed clip
- **THEN** cues outside the clip window are dropped, kept cues are shifted to timeline zero, and libass renders them onto the video stream

### Requirement: Optional background music bed with sidechain ducking
The CLI renderer SHALL accept an optional local `bgm` audio/video path, `bgm_volume` (0..2, default 0.25), and `bgm_duck` (bool, default true) to loop and mix a background bed under the concatenated clip audio using `sidechaincompress` when ducking is enabled.

#### Scenario: Sidechain ducked BGM
- **WHEN** a plan specifies `bgm` with `bgm_duck: true` over a voiced clip
- **THEN** the background bed is compressed under the voice track compared to `bgm_duck: false`
