# Third-party software and assets

The MIT license in [LICENSE](LICENSE) covers first-party code only (`creator.py`,
`creator_tools/`, `studio-ui/`, `scripts/`, `tests/`, docs and skills). Everything below
keeps its own license.

## Installed by `scripts/bootstrap.sh` (not stored in this repo)

Revisions are pinned in [upstream-lock.json](upstream-lock.json).

| Project | License | How the kit uses it |
|---|---|---|
| [HyperFrames](https://github.com/heygen-com/hyperframes) | Apache-2.0 | HTML → MP4 renderer, Kokoro TTS command, video-authoring agent skills |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | AGPL-3.0 | Optional production pipelines; its virtualenv hosts the local Kokoro voice. Run as a separate program. If you modify OpenMontage and offer it to others as a network service, the AGPL obliges you to share those changes. |
| [Archify](https://github.com/tt-a1i/archify) | MIT | Interactive architecture diagrams; release ZIP verified against [integrations/archify-lock.json](integrations/archify-lock.json) |
| [GSAP](https://gsap.com) | GSAP Standard "No Charge" License (not MIT) | Animation runtime, read from HyperFrames' dependency tree and checksum-verified by `creator.py motion doctor`. Free for commercial animation; competing no-code visual animation builders need separate permission. Copy: [integrations/gsap-license.txt](integrations/gsap-license.txt) |
| Local voice models (Qwen3-TTS, Chatterbox, Kokoro) | Per model; see [integrations/voice-models.json](integrations/voice-models.json) | Downloaded on first use into git-ignored `local/` |

## Vendored in this repo

| Path | Source | License |
|---|---|---|
| `integrations/design-md/` | [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) at the commit in [integrations/design-md-lock.json](integrations/design-md-lock.json) | MIT ([LICENSE](integrations/design-md/LICENSE)). Token analyses of public brand sites; brand names and trademarks belong to their owners. Use them as style references, not as a claim of affiliation. |

## Credits

The data-story pattern and Fabric static-hosting kit were informed by Sanjay Narendran's
public [CMS Hospital Insights](https://github.com/SanjayNarendran/MS102-public-CMS-Hospital-Insights-fabric-rayfin-GHC) application.
