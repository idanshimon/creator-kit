# Repository Stewardship

## Purpose
Keep the private first-party studio reproducible and discoverable without confusing source sync with media backup or vendor upgrades.

## Requirements

### Requirement: Keep the source repository private
The publishing workflow MUST verify the intended GitHub owner, private visibility and remote branch SHA before reporting a successful sync.
Credentials, local inventory, SQLite workspaces, production media and generated dependencies/builds remain excluded from this source repository.

#### Scenario: Sync completion
- **WHEN** source changes are pushed
- **THEN** the remote main SHA is compared with local HEAD and repository visibility is read back as private

### Requirement: Track upstream provenance without accidental vendoring
The repository MUST record upstream URLs, licenses and installed revisions in upstream-lock.json while excluding upstream checkout directories.
Updating first-party documentation does not automatically update upstream software. Existing vendor modifications must not be reset to satisfy a pin.

#### Scenario: Newer upstream version exists
- **WHEN** upstream HEAD differs from the recorded revision
- **THEN** documentation reports it as an available update, not as installed or tested

### Requirement: Keep documentation aligned with executable behavior
The repository MUST index its canonical specs, architecture, setup, operational boundaries and verification evidence.
Historical verification remains dated; no obsolete no-GUI/no-Git statement is presented as current. Claims about live models, media review and remote sync require evidence at those respective layers.

#### Scenario: New editor capability
- **WHEN** a first-party capability changes
- **THEN** its spec, user documentation and relevant verification mapping are updated together
