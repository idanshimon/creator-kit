# Access Boundaries

## Purpose
Record real local, LAN and Azure boundaries without implying user authentication or a hosted security boundary.
## Requirements
### Requirement: Default to loopback and bound explicit LAN sharing
The server MUST default to loopback and reject public, wildcard and non-IPv4 binds.
Explicit RFC1918 IPv4 binding permits trusted LAN access with no login and no TLS. Host/Origin checks and CSRF protection are not identity authorization; any permitted peer can obtain the session token.

#### Scenario: Default launch
- **WHEN** the studio command omits host
- **THEN** it binds 127.0.0.1 rather than all interfaces

#### Scenario: Public exposure request
- **WHEN** host is 0.0.0.0 or a public IPv4 address
- **THEN** startup rejects the bind

### Requirement: Validate request origin and write token
The HTTP API MUST check its Host allowlist, reject mismatching supplied Origin headers and require its CSRF token on mutations.
An absent Origin is accepted when other checks pass. These defenses do not make the LAN server safe on untrusted networks or behind a public tunnel.

#### Scenario: Missing mutation token
- **WHEN** a write omits the session CSRF token
- **THEN** the server returns HTTP 403

### Requirement: Require explicit cloud inference consent
The CLI MUST require --allow-cloud for chat, plan, image, transcribe, `narrate --engine azure` and `crawl --scorer azure` before loading inference inventory or making the inference call.
Discovery is an explicitly invoked Azure management query, not an inference operation. Tokens are minted through Azure CLI and held in memory. The browser Studio has no cloud-operation routes.

#### Scenario: Cloud flag omitted
- **WHEN** a user invokes plan without --allow-cloud
- **THEN** the command fails with an actionable consent message before contacting inference

#### Scenario: Crawl model scoring without consent
- **WHEN** `crawl --scorer azure` omits `--allow-cloud`
- **THEN** the command fails before reading the inventory or sending instruction text

#### Scenario: Azure narration without consent
- **WHEN** `narrate --engine azure` omits `--allow-cloud`
- **THEN** the command fails before reading the inventory or sending script text

### Requirement: Represent model capabilities and evidence honestly
The model tools MUST distinguish discovered deployments from inference-tested models and metadata planning from semantic video analysis.
The planner sends instructions and technical metadata, not video frames/transcripts. Only supplied sources may appear in the generated plan. Image uses the GPT Image adapter; transcription is Whisper SRT, not diarization. Embedding, video, realtime and unknown are discovery classifications, not implemented generation adapters.

#### Scenario: Invented plan source
- **WHEN** a model-generated plan names a source not supplied by the user
- **THEN** it is rejected before rendering

