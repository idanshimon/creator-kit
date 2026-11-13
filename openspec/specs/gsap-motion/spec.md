# gsap-motion Specification

## Purpose
Provide checksum-pinned, offline GSAP motion authoring with deterministic HTML-to-MP4 capture, preserved user outputs, and explicit licensing/verification boundaries.
## Requirements
### Requirement: Pinned read-only GSAP runtime
The studio SHALL verify the installed GSAP version and runtime checksum against its recorded lock before generating a motion composition, without modifying upstream dependencies.

#### Scenario: Runtime missing or modified
- **WHEN** the pinned bundle is unavailable or its version/hash differs
- **THEN** doctor/create fails explicitly and does not silently fetch or upgrade GSAP.

### Requirement: Non-overwriting offline composition
The motion command SHALL create a new standalone offline HTML composition with escaped author copy, retained GSAP notices and no automatic cloud use.

#### Scenario: Existing destination
- **WHEN** the output directory or file already exists
- **THEN** the operation refuses without replacing its contents.

### Requirement: Deterministic seekable capture
The generated composition SHALL construct a paused finite timeline synchronously, register it by composition ID, provide showcase clock hooks, and preserve deterministic visible poses under forward, backward and repeated seeks.

#### Scenario: Revisit a proof time
- **WHEN** an animation seeks to its end and then back to an earlier time
- **THEN** its visible state at that time matches a fresh seek and does not depend on suppressed callbacks.

### Requirement: Verified scope and licensing
Documentation SHALL distinguish source review, tested first-party capture, untested plugins, full HyperFrames compatibility and the Standard License visual-builder restriction.

#### Scenario: Optional plugin or visual editor
- **WHEN** the core-only template is available
- **THEN** the studio does not claim optional plugins are integrated or a competing visual builder has license clearance.
