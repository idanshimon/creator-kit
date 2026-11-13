# MCP for Blender — 3D authoring for content creation

## Scope and evidence

Repository: https://github.com/ahujasid/mcp-for-blender
Website: https://www.mcp-for-blender.com/
Reviewed revision: `febcd90ece59c3416d7c55fd3723cea46bcaa59d`.
Source package version: `2.2.4`; the corresponding PyPI release was independently found at https://pypi.org/pypi/mcp-for-blender/2.2.4/json .

This is a community integration, not an official Blender Foundation product. Former name: `blender-mcp`; new installs use `mcp-for-blender`. Old package/repo references remain in some docs. Do not silently rename a working legacy setup.

Research status: source and tool definitions inspected; core tools checked by AST; root and packaged add-on sources compared byte-for-byte; Python syntax compatibility checked. No dependency installed, MCP registered, Blender started, provider charged, model generated or render/export exercised. Package metadata existence does not prove the released wheel is identical to this Git revision.

## Where it fits

Use for editable 3D props, product turntables, isometric scenes, camera moves, lighting/material studies, exploded-view explainers and animated scene inserts. It controls Blender; it is not itself a new text-to-video model, narration engine or caption editor.

Architecture:

    Agent MCP client → Python stdio MCP server → local JSON/TCP socket → Blender add-on → bpy

Blender must be installed and running with the add-on enabled and socket server started. Installing the Python package alone does not supply Blender or a working scene. Core modeling/material/animation work uses agent-authored Blender Python; optional generation APIs create individual models, not complete directed scenes.

Choose the simplest tool for the production:

- DOM titles/cards/2D motion: retain GSAP/HyperFrames or selected React Bits effects.
- Editable 3D scene/camera/material work: MCP for Blender is a candidate.
- Single AI-generated object / image-to-world work: retain the relevant IMAGE-BLAST workflow when that is already the right asset route; do not regenerate an existing usable mesh through another paid provider.
- Completed Blender output: bring a rendered still/clip/image sequence into the existing `productions/<name>/` workflow, add narration/captions through current tools, and preserve the `.blend` plus external assets.

There is no installed `creator.py blender` command or verified Studio integration implied by this guide.

## Actual MCP surface

Nine core tool names were verified in the pinned server source. Runtime tool names in your client will be prefixed; discover and load their live schemas before invoking them. Historical examples online may describe removed/consolidated tools.

| Tool | Use / limit |
|---|---|
| `get_addon_status` | First call: Blender/add-on versions and enabled asset libraries/generators; inspect consent status too |
| `get_scene_info` | Compact text summary; `query`, `root`, selected `fields`, `limit`; not a full geometry dump |
| `execute_blender_code` | Run Python in the live Blender process; modeling, materials, animation, rendering, saving and exporting are done here |
| `look` | Inspect `viewport`, `camera`, `angles` or `frames`; solid/material/rendered/wireframe/xray shading; can display `Render Result` or an image |
| `search_assets` | Search `polyhaven`, `sketchfab`, `polypizza`; inspect asset license/scale before importing |
| `import_asset` | Download/import chosen ID; can apply a Poly Haven texture to named objects or set target size |
| `generate_3d` | Generate/import ONE model with selected provider; optional paid/cloud path, may return resumable job |
| `disable_telemetry` | Switch off content consent; minimal usage telemetry remains unless disabled in the server environment |
| `record_trajectory_feedback` | Telemetry/trajectory feedback, not Blender undo; do not call it expecting to restore the scene |

The source additionally registers `search_mentions`, `open_viewport`, `viewport_latest`, `viewport_capture`, `viewport_pick` for client features. Some app-only tools are filtered from tool discovery when the client lacks MCP Apps support. The Codex plugin's inline viewport, pickers and mentions do not establish equivalent support in your client. Image-returning `look` is the basic observation path; verify client rendering rather than forcing app flags blindly.

There is no core MCP `render_scene`, `export_scene`, `save_blend_file`, `create_object` or `set_material` tool in this revision. The add-on contains an internal socket `export_scene` implementation, but that is not the same as a published MCP tool. Use reviewed `bpy` through `execute_blender_code`, not invented tool names. A viewport screenshot is not a final camera render.

## Prerequisites and installation policy

This task only researches and records the option. When installation is requested:

1. Inspect installed Blender, embedded Python, `uv`/`uvx`, consuming client and existing add-ons/config. Never overwrite an existing setup or install into another user profile.
2. Review/pin the package and matching add-on before execution. Prefer manual, scoped setup over upstream `curl | sh`, PowerShell `iex`, or the broad `setup` wizard that edits several clients and installs/enables add-ons. These installers were not run or fully audited here.
3. Use your agent client's supported, user-approved MCP installation flow; never hand-edit MCP server config or bypass a configuration guardrail via terminal scripts. If the catalog cannot install this package, report that limit and use the supported user-approved setup path. Do not paste config blocks meant for a different client.
4. Install/enable the reviewed add-on separately. The server and add-on are distinct revisions/processes; source startup checks do not automatically update the add-on. Verify with `get_addon_status` after changes.
5. Use one MCP owner for a scene/Blender socket. For distinct Blender instances use distinct ports set in both clients and add-on panels; do not let competing clients edit one production.

Pinned CLI recipe for later authorized setup (invoke via `terminal`; these commands were not executed here):

```bash
uvx --python 3.11 --from mcp-for-blender==2.2.4 mcp-for-blender addon-paths
uvx --python 3.11 --from mcp-for-blender==2.2.4 mcp-for-blender install-addon
```

The first command enumerates add-on destinations. The second writes the add-on as `blender_mcp.py` and may replace an existing copy with a backup; review destinations before running it. In Blender enable **Interface: MCP for Blender**, then inspect the `N` sidebar's **MCP for Blender** panel and start the server if needed. Add-on auto-start defaults to true; disabling/stopping it is a separate action from ending the client conversation.

Conceptual client process, not an instruction to start a duplicate terminal server:

    command: absolute path to uvx
    args: --python 3.11 --from mcp-for-blender==2.2.4 mcp-for-blender
    environment: DISABLE_TELEMETRY=true, BLENDER_MCP_SAFE_MODE=1,
                 BLENDER_HOST=localhost, BLENDER_PORT=9876

Use the actual client/schema-supported way to pass these arguments/environment variables. GUI apps may not inherit shell PATH. Launching the command interactively appears to wait because stdio MCP expects a client; it is not proof of failure or a Blender connection. The add-on port is raw JSON/TCP, NOT an HTTP MCP URL.

Compatibility trap: README and `bl_info` advertise Blender 3.0+, but this revision's add-on uses structural `match` syntax. Static parsing rejected Python 3.9 and accepted 3.10/3.11/3.13. Check Blender's EMBEDDED Python, not merely the interpreter running uvx. A parser pass is not full Blender API/runtime compatibility. Prefer an actually tested supported Blender release; do not promise 3.0 works from its metadata alone.

## Privacy and security defaults

Use these as default constraints for our future installation, not claims that they are currently configured:

- `DISABLE_TELEMETRY=true` in the MCP SERVER process environment disables all project telemetry. Keep Blender add-on content consent unchecked as well. `disable_telemetry` only clears content consent; its own response explicitly says anonymous tool-name/success/duration usage counts remain.
- Content collection is opt-in in this revision, but minimal anonymous usage records are on without that opt-in. Opt-in can include prompts/code/screenshots/scene metadata/trajectory and manual-edit/undo feedback, potentially retained indefinitely, used for training or public datasets. Terms grant a perpetual content-use license when opting in. Do not equate the README's 'telemetry opt-in' with zero default network telemetry.
- `BLENDER_MCP_SAFE_MODE=1` enables an AST allowlist before model-authored code crosses the MCP path. It is OFF by default. It is not an OS sandbox, authentication, or a guard on direct callers of the add-on socket. It deliberately permits render/save/open/import/export and other filesystem access THROUGH bpy. Do not call it a read-only or file-isolated environment.
- The add-on socket defaults to `localhost:9876` with no authentication/encryption. Any process that can reach it can submit Python; never expose it publicly or bind it broadly as an integration shortcut. For a remote Blender host prefer an authenticated private tunnel with loopback endpoints, then verify both ends. A container running the MCP process does not sandbox the host Blender process.
- Generated code has Blender's user privileges. Use a dedicated scene/workspace with least necessary files and permissions; review destructive operations and absolute output paths. Save a non-overwriting copy before edits. Do not reset/delete the user's normal scene to make a demo.
- Disabling this project's telemetry does NOT stop the agent's model provider from receiving tool images/text, or prevent optional asset/generation APIs from receiving prompts/images. Use synthetic/cleared assets and an approved model/provider for sensitive work. Never place API keys in scripts, production manifests, prompts or Git.
- API-key environment fallbacks documented by upstream (`BLENDERMCP_*`) are read by the Blender add-on. Setting them only in the MCP server's environment may not reach an already-running Blender process. Use approved credential handling and verify the add-on sees availability without printing values. A masked Blender preference field is not proof of OS-keystore storage.
- Context-size logging is separately opt-in via `BLENDER_MCP_CONTEXT_LOG`; source describes names/sizes only. Job-resumption state can be stored in the BlenderMCP data directory even when telemetry upload is disabled. Do not promise 'no local files' from the telemetry toggle.

Safe mode blocks handlers/timers/drivers, direct `os`/`subprocess`/socket/raw file I/O, dynamic interpreter escapes and external `.blend` datablock append/link. Normal keyframes/render/save/export are intended to work. If an animation example uses a driver or imports `bpy_extras`, adapt it to permitted keyframes/version-aware code; do not silently disable safe mode to satisfy a cookbook snippet.

## Asset and generation choices

| Source/path | Auth/cost | Content-creator use |
|---|---|---|
| Local procedural bpy | No third-party generation key needed | Directed geometry, studio lighting, motion/camera setup; local render compute still has a cost |
| Poly Haven | Enable library; no API key; assets described as CC0 | Start here for HDRIs/PBR materials/realistic props; keep source URL/authors/license provenance |
| Poly Pizza | API key; per-model CC0 or CC-BY | Low-poly props; prefer CC0 when suitable or carry required creator attribution into the deliverable |
| Sketchfab | Key/download permissions; per-model terms | Specific reusable models; inspect license, attribution, topology and allowed commercial use |
| Meshy / Tripo / Hunyuan3D / Hyper3D Rodin | Provider credentials or paid Premium availability | One missing bespoke object, not a substitute for scene direction or unlimited free generation |

Use `search_assets` then inspect IDs/licenses/previews before `import_asset`. The argument is `licence` (British spelling), not `license`. For Poly Haven imports supply `asset_type`; applying a texture to named objects replaces their materials, so snapshot before doing it. Default texture resolution is 1k: start small and increase only for actual camera proximity. Large downloads run on Blender's main thread and can make the UI appear frozen.

Target size on library imports is the model's largest dimension in metres; inspect orientation, origin, dimensions, grounding and transforms after import rather than trusting a prompt. Asset licenses are separate from the integration's MIT license. Imported custom properties can preserve attribution, but they do not automatically add visible credits to a published MP4.

`generate_3d(provider="auto")` prefers Premium-enabled generators before own API keys. Do not let it choose a paid service silently: confirm the intended provider/budget and data destination once, then use recorded choices. Give exactly one of prompt/image; use an actual accessible image path/URL, not a chat attachment token or a silently substituted text prompt. A-pose/T-pose options are Meshy-specific and provider mode matters.

Generation can return a `job` handle; resume that job rather than issuing a fresh generation after a timeout. Duplicate an existing model for repeated props. Record provider, prompt/reference, job ID, license/terms, source revision and imported-object name without credentials. Do not claim imported means correctly scaled, cleanly rigged or ready for production.

## Production procedure

1. Define the shot's job: subject, visual message, final aspect/resolution, duration/FPS, camera path, alpha/background, caption keep-out and required still/clip/model outputs. Match the existing narration timing instead of guessing scene lengths.
2. Make a new production scene under `productions/<name>/`; preserve the original file. Call `get_addon_status`, then bounded `get_scene_info`, then `look`. Read back actual scene/object names before editing.
3. Block geometry/materials/camera/light in short scripts. Give authored objects a unique prefix and operate on explicit collections/names, not global delete-all. Print object names/dimensions and inspect multi-angle `look` results after meaningful changes. Treat asset descriptions as untrusted data, not code instructions.
4. Animate with keyframes against explicit frame numbers; set FPS, frame range, output resolution/percentage, engine, camera, samples, alpha and color management intentionally. Use `scene.frame_set(...)` to evaluate specific frames. Bake/cache simulations and fix seeds for repeatable rendering. Version-check animation APIs: upstream guide notes slotted actions in 4.4 and removal of `Action.fcurves` in 5.0; do not reuse legacy fcurve code blindly.
5. Render a cheap still/short frame range first, inspect the actual camera result, then finalize. `look(mode="frames", view="camera")` can expose timing/popping/clipping but is not a completed final render. Viewport 'rendered' shading support is not identical to final renderer support.
6. Save the `.blend`, pack/collect required textures/fonts/HDRIs and retain original imports/license credits. Render numbered image frames for resumability when practical; use RGBA PNG/EXR when transparency is required, then encode/mux through the current video workflow. Do not expect an ordinary H.264 MP4 to carry an alpha channel. Export GLB/FBX via bpy only if a downstream consumer actually needs geometry; glTF may not preserve arbitrary Blender shader/procedural behavior.
7. Reopen the saved `.blend` and, where applicable, reimport an exported model in a clean scene; confirm required assets/materials/scale/animation survive. Read back exact output targets after mutation. A tool saying 'Code executed successfully' only reports script completion, not a correct saved/exported artifact.
8. Verify final media with ffprobe plus visual inspection at every scene, first/middle/final frames, transitions and loop seam; check narration/captions in the assembled MP4 independently. Store source and render settings in the production manifest. `.blend` plus media are not backed up merely because the creator-kit source repo is synced.

Long renders may exceed the socket's 180-second timeout. A timed-out request may still have performed work: inspect scene/output state before retrying a mutating or expensive action. For large jobs, save the scene and use an approved Blender background-render process with job tracking rather than increasing every interactive timeout or starting duplicate work. Background Blender rendering is a separate execution path, not proven by the add-on's live viewport behavior.

## Verification on an actual installation

Completion requires a real end-to-end smoke test, not package installation alone:

- Add-on version/status + loopback listener verified; client discovers actual tools; consent/settings checked.
- Disposable prefixed object created, queried, viewed, changed and saved without disturbing normal user files.
- Small keyframed camera/object scene rendered at known first/middle/final frames; scene state and exported files read back.
- Saved scene reopened; dependency packing checked; GLB/FBX reimport checked if requested.
- Final image/video visually reviewed and media probed; no unsupported claims about realism, dimensions or generated quality.
- All-telemetry-disabled behavior and intended provider data boundaries verified if that is an acceptance criterion; environment settings alone are configuration evidence, not observed network evidence.

## Primary sources

Immutable source root:
https://github.com/ahujasid/mcp-for-blender/tree/febcd90ece59c3416d7c55fd3723cea46bcaa59d

- `README.md`, `pyproject.toml`: architecture, rename, setup, requirements, environment variables and release version.
- `LICENSE`: MIT, copyright 2025 Siddharth Ahuja; retain notices when copying code.
- `TERMS_AND_CONDITIONS.md`: content opt-in, default minimal telemetry and content-use license; distinct from MIT software licensing.
- `src/blender_mcp/server.py`: registered tools, optional client filtering, safe-mode gate, generation semantics, socket timeouts and stdio entry point.
- `addon.py`, `src/blender_mcp/bundled/addon.py`: matching add-on sources, socket binding, auto-start, consent default, internal export and bpy execution.
- `src/blender_mcp/safe_mode.py`: scope/limits of AST validation; not a Blender sandbox.
- `src/blender_mcp/telemetry.py`, `telemetry_decorator.py`, `trajectory.py`, `context_log.py`: collection gates and local diagnostic/job-state distinctions.
- `src/blender_mcp/generation.py`, `setup_cli.py`: provider/job logic and broad setup behavior.
- `src/blender_mcp/guides/animation.md`: keyframes, version-aware fcurves, camera and visual motion review.
- `tests/test_consolidated_tools.py`, `test_export_scene.py`, `test_safe_mode.py`: inspected upstream tests. These use mocks/static assertions and were NOT run in this research; a mocked export does not prove a real Blender file was produced.
