# evidence-data-stories Specification

## Purpose
TBD - created by archiving change add-evidence-data-stories. Update Purpose after archive.
## Requirements
### Requirement: Validated analytical story input
The CLI SHALL validate a domain-neutral story document with figure identities, finite numeric series, actual period labels, source links, extract identity and separately labeled human interpretation before rendering.

#### Scenario: Invalid analytical data
- **WHEN** a figure has missing source periods, nonfinite values, invalid source URL, duplicate identity or zero predicted denominator for a pooled ratio
- **THEN** validation and rendering fail without creating output.

### Requirement: One fact model and extract-bound evidence
The renderer SHALL derive displayed latest values, comparisons and pooled ratios from the validated figure inputs, expose calculation/source/period/query evidence, and distinguish unverified evidence from supplied verification bound to the exact input digest.

#### Scenario: Stale verification
- **WHEN** a supplied verification digest differs from the computed figure digest or its declared result contradicts the values
- **THEN** validation fails rather than presenting a verified badge.

### Requirement: Standalone reading experience
The renderer SHALL produce a new standalone offline HTML reading page with narrative navigation, accessible charts, figure-local Explain controls, light/dark themes, escaped author text and responsive layout, without a network dependency or output overwrite.

#### Scenario: Figure explanation on a narrow screen
- **WHEN** a reader opens a figure explanation on a mobile viewport
- **THEN** its source, period, calculation and verification state remain readable without page-level horizontal overflow.

### Requirement: Local protected Fabric export kit
The CLI SHALL package an explicit self-contained HTML into a new local Rayfin deployment kit with protected static hosting, disabled backend data/storage/functions, exact CLI dependency version and build integrity manifest, without invoking cloud actions or dependency installation.

#### Scenario: Runtime assets or existing destination
- **WHEN** the HTML depends on external or relative runtime assets, or the destination already exists
- **THEN** packaging refuses and preserves existing content.

### Requirement: Deployment and evidence boundaries
Documentation SHALL provide the upstream upload commands and prerequisites while distinguishing locally built export kits from installed CLI, authenticated hosting and real Fabric deployment, and warn that static extracts do not inherit per-viewer model RLS.

#### Scenario: Local kit completion
- **WHEN** local packaging and build checks pass
- **THEN** output is reported as a deployment kit, not as a deployed or secured live application.
