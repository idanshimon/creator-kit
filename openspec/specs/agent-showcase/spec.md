# agent-showcase Specification

## Purpose
TBD - created by archiving change add-showcase-and-prompt-crawler. Update Purpose after archive.
## Requirements
### Requirement: Frame-exact page recording
The system SHALL record an HTML page that exposes `__ready` and `__advance(ms)` to an H.264 MP4 by advancing the page clock once per output frame, and SHALL refuse an existing output path.

#### Scenario: Deterministic page
- **WHEN** a page advances a clock via `__advance` and reports `__done()` after 2 s at 10 fps
- **THEN** the recorder writes 30 frames (20 until done plus a 1 s hold) as an h264 stream

#### Scenario: Existing output
- **WHEN** the requested MP4 already exists
- **THEN** the command fails and the file is unchanged

### Requirement: Prompt crawl with honest labelling
The system SHALL split a prompt or SKILL.md into decisions, route each to code, model or human, write crawl.json and a standalone viewer to a new directory, and record which method produced the scores.

#### Scenario: Heuristic default
- **WHEN** crawl runs without a scorer flag
- **THEN** no network call is made and the method reads `keyword heuristic, no model call`

#### Scenario: Vague wording
- **WHEN** an instruction contains vague wording
- **THEN** it is not routed to code

### Requirement: Consent-gated model scoring
The system SHALL require `--allow-cloud` before sending instruction text to Azure for scoring, and SHALL select the highest-version `gpt-*-mini` deployment unless a model is named.

#### Scenario: Missing consent
- **WHEN** `crawl --scorer azure` omits `--allow-cloud`
- **THEN** the command fails before loading the inventory or calling Azure

#### Scenario: Model choice
- **WHEN** the inventory holds gpt-4.1-mini, gpt-5-mini and gpt-5.4-mini
- **THEN** gpt-5.4-mini is selected

### Requirement: Cascade escalation with per-call accounting
The system SHALL escalate items whose top answer probability is below 0.6 to a stronger deployment once, route items still below 0.6 to a human, and record every call's tier, model, answer, probability and latency.

#### Scenario: Undecided item
- **WHEN** tier 1 returns 0.5 / 0.5 for an instruction
- **THEN** tier 2 is asked, and the node carries two legs

#### Scenario: Still undecided
- **WHEN** tier 2 also returns a top answer below 0.6
- **THEN** the node routes to human

