# production-manifest Specification

## Purpose
Give each production a single `manifest.json` that inventories its artifacts (path, type,
size, sha256, mtime), derives videos/cover, and surfaces open decisions awaiting a human,
without network or cloud and without overwriting an existing manifest.
## Requirements
### Requirement: Per-production manifest
The system SHALL write a `manifest.json` for a production directory that inventories every
artifact file under it — each with a relative path, a type classified by extension, byte size,
sha256 checksum and ISO-8601 modification time — plus a `generated_at` timestamp, and SHALL
refuse to overwrite an existing manifest path.

#### Scenario: Inventory with checksums
- **WHEN** `bundle` runs on a production directory containing a file
- **THEN** the manifest lists that file with its correct sha256, byte size and type

#### Scenario: Existing manifest
- **WHEN** the target manifest path already exists
- **THEN** the command fails, the file is unchanged, and the user is told to pass `--output`

### Requirement: Derived videos and cover
The system SHALL list video artifacts with a duration read from ffprobe when ffprobe is
available and null otherwise, and SHALL choose a cover image by rule, preferring `poster.png`.

#### Scenario: Cover selection
- **WHEN** the directory contains `poster.png` and other PNGs
- **THEN** the manifest `cover` is `poster.png`

#### Scenario: No images
- **WHEN** the directory contains no image files
- **THEN** the manifest `cover` is null

### Requirement: Open decisions extraction
The system SHALL surface open decisions in the manifest: from any `crawl.json`, the nodes whose
route is `human` with their text, section and scores; and from any `*.provenance.json` whose
`review_required` is true, the pending review.

#### Scenario: Human-routed crawl node
- **WHEN** a `crawl.json` holds a node routed to `human`
- **THEN** that node appears in `open_decisions` with its text, section and scores

#### Scenario: Provenance awaiting review
- **WHEN** a `*.provenance.json` has `review_required` true
- **THEN** it appears in `open_decisions` as a pending review

