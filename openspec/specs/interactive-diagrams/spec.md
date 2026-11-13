# interactive-diagrams Specification

## Purpose
TBD - created by archiving change add-archify-diagrams. Update Purpose after archive.
## Requirements
### Requirement: Pinned local installation
The system SHALL install Archify only from an explicitly supplied ZIP matching the recorded SHA-256 and file manifest, without overwriting an existing installation.

#### Scenario: Wrong archive
- **WHEN** an archive differs from the pin
- **THEN** installation fails before package files are installed

### Requirement: Bounded diagram operations
The system SHALL provide doctor, validate and render commands for architecture, workflow, sequence, dataflow and lifecycle diagrams with update checks disabled and object/URL brand capture rejected.

#### Scenario: Remote brand request
- **WHEN** a diagram requests a URL-backed brand
- **THEN** the command fails without fetching that brand

### Requirement: Verified new HTML output
The system SHALL publish new HTML only after upstream delivery checks succeed and SHALL refuse an existing output path.

#### Scenario: Invalid diagram
- **WHEN** schema, layout or artifact checks fail
- **THEN** the requested final HTML is not created

#### Scenario: Existing output
- **WHEN** the requested output already exists
- **THEN** its bytes remain unchanged and the command fails

### Requirement: Optional deterministic showcase bridge
The system SHALL support `--showcase-bridge` (and `--video`) on `diagram render` to inject `window.__ready`, `window.__advance(ms)`, and `window.__done()` hooks that step through `Archify.guidedViews` chapters deterministically for `showcase` MP4 recording.

#### Scenario: Bridged diagram render
- **WHEN** `diagram render` runs with `--showcase-bridge`
- **THEN** the published HTML includes `creator-showcase-bridge` and steps guided chapters via `window.__advance`

