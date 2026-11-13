# OpenSpec index

Baseline captured 2026-09-17 from first-party source and executable tests. This is a
backfill of the existing implementation, not a claim that a spec preceded that code.

## Canonical capabilities

- [Evidence data stories and Fabric export](specs/evidence-data-stories/spec.md): validated analytical inputs, offline reading pages and local-only protected-static-hosting kits.
- [Bounded editing](specs/bounded-editing/spec.md): timeline validation, draft/final export, audio and captions.
- [Studio workspace](specs/studio-workspace/spec.md): revisions, registered assets, wire format and render jobs.
- [Access boundaries](specs/access-boundaries/spec.md): loopback/LAN trust, cloud consent and model scope.
- [Repository stewardship](specs/repository-stewardship/spec.md): private source sync, upstream pins, documentation and backup exclusions.
- [Interactive diagrams](specs/interactive-diagrams/spec.md): pinned Archify install, bounded validate/render, verified new HTML.
- [Agent showcase](specs/agent-showcase/spec.md): frame-exact page recording, prompt-crawler, consent-gated model scoring and cascade escalation.
- [Production manifest](specs/production-manifest/spec.md): per-production artifact inventory with checksums, derived videos/cover, and open-decision extraction.
- [GSAP motion authoring](specs/gsap-motion/spec.md): pinned offline runtime, non-overwriting HTML scaffold and deterministic showcase capture.

## Maintenance

Run `openspec validate --all --strict`. For behavior changes, create a change under
`changes/`, write requirements and scenarios, validate, implement, exercise and archive.
Do not mark planned UI controls or cloud adapters as implemented.

See [documentation index](../docs/INDEX.md), and [verification](../docs/VERIFICATION.md). Previously completed changes: `add-archify-diagrams`,
`add-showcase-and-prompt-crawler` (2026-10-08), `add-production-manifest` (2026-10-08), and `add-gsap-motion` (`2026-10-21-add-gsap-motion`, the CLI-generated archive date). Also: `2026-11-03-add-evidence-data-stories`; see `docs/VERIFICATION.md` for implemented scope, local browser/kit proof and the unrelated baseline subtitle-filter error. Upstream upgrades remain a separate reviewed operation.
