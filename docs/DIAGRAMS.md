# Interactive diagrams with Archify

Archify is Creator Kit's **standalone interactive diagram tool**, alongside—not
inside—the video editor. It renders typed JSON into an explorable HTML file with
component selection, relationship tracing, guided chapters and presentation controls.
It does not discover architecture from source code, generate narration, create an MP4,
or add an HTML clip to the Studio timeline.

## Installed version and recovery

Upstream: https://github.com/tt-a1i/archify (MIT), release **v2.16.0**, source commit
`c826e6c3a7abad19c0f3cd1ca57207d54b1ad8de`.

The release archive and every installed file are pinned in
[`integrations/archify-lock.json`](../integrations/archify-lock.json). The ignored
`archify/` directory is a release package, not a git clone. No npm install is needed;
Node >=18 and Python >=3.10 are required. Restore it with the command below (or `scripts/bootstrap.sh`).

On a new machine, explicitly download the pinned release (network required):

```bash
curl -fL --max-time 120 \
  https://github.com/tt-a1i/archify/releases/download/v2.16.0/archify.zip \
  -o "$TMPDIR/archify-v2.16.0.zip"
python3.13 creator.py diagram install --archive "$TMPDIR/archify-v2.16.0.zip"
python3.13 creator.py diagram doctor
```

Use a chosen temporary directory if `TMPDIR` is unset. Substitute your Python 3.10+
executable. Installation checks SHA-256 before extraction, checks every file, rejects
unsafe archive paths, and refuses an existing `archify/` directory. It neither downloads
nor updates implicitly. For an upgrade, review and test a new pin first; preserve the
old installation rather than forcing a replacement.

## Author → validate → render → review

Run from the repository root:

```bash
python3.13 creator.py diagram validate \
  --input examples/diagrams/creator-kit.architecture.json
python3.13 creator.py diagram render \
  --input examples/diagrams/creator-kit.architecture.json \
  --output productions/archify-demo/creator-kit.html
```

Open the output in a browser. Render refuses an existing output; choose a new versioned
filename for revisions. Both commands default to `--quality showcase`; select `standard`
explicitly if a simpler quality profile is appropriate. The output is published only
after upstream `deliver` succeeds. The JSON receipt includes source/output hashes and
retains `visual_review_required: true`: passing layout checks is not visual inspection.

Supported `diagram_type` values: `architecture`, `workflow`, `sequence`, `dataflow`,
`lifecycle`. Read the corresponding `archify/schemas/<type>.schema.json`, examples and
`archify/references/authoring-contract.md`; they differ (workflow has its own schema
version). Start from an example, preserve stable node and relationship IDs, and author
`meta.views` with focus IDs and grounded explanatory notes. Do not hand-edit the rendered
HTML as the primary source; edit JSON and render again.

The first-party example describes this integration and cites its code. Customer-specific
sources and outputs belong under `productions/<name>/`, not the generic tracked example.

## Presentation templates

The original Archify viewer stays the default (`--template full`, byte-identical to
upstream delivery). Other templates layer a wrapper-owned style/script onto the same
output; the source JSON and the upstream renderer are unchanged.

| Template | What the reader sees |
|---|---|
| `full` | Original Archify UI: toolbar (theme, style, present, export), guided chapters, PATH/MAP/LENS, semantic passport, cards. |
| `presenter` | Title, guided chapters, diagram, zoom and cards. Clicking a component opens a **detail panel** (what it does, why it matters, example, receives from / sends to; ID behind *Technical details*) instead of the semantic passport. Docked on the right at >=1000px, sheet below that. Selection does not move the camera. |
| `story` | Guided chapters (play, chapter tabs, stops) + graph only, fitted and auto-height for an `<iframe>`; click opens the detail panel. Toolbar, PATH/MAP/LENS, cards hidden. |
| `embed` | Graph only, fitted to its frame, plus zoom. Click opens the detail panel as a bottom sheet. For `<iframe>` in articles. |
| `minimal` | Graph only, static. No controls, nothing opens. For screenshots. |

Wrapper templates (`presenter`, `story`, `embed`, `minimal`) are offline: they strip the upstream
Google Fonts link and add a visible `:focus-visible` ring on SVG nodes (both were `design-check`
Floor failures). `full` stays byte-identical to upstream. Authoring lessons for passing delivery
(viewBox width, straight edges, `labelAt`, no `sources` via the wrapper): [UI-DECISIONS.md](UI-DECISIONS.md#diagrams-archify).

Fine-tune with repeatable `--hide PART` / `--show PART`; parts are `toolbar header
chapters cards nav zoom passport details`. Turning `details` on always hides the
passport.

Detail text comes from an optional sidecar JSON keyed by node id
(`{"node":{"what":"…","why":"…","example":"…"}}`). Unknown ids, unknown fields and
blank text fail the render. A node without authored detail shows its own label,
sublabel, the guided-view notes that mention it and its real connections; nothing is
generated.

```bash
python3.13 creator.py diagram render \
  --input productions/morrow-beginner/morrow-beginner.workflow.json \
  --details productions/morrow-beginner/morrow-beginner.details.json \
  --template embed --embed-snippet \
  --output productions/morrow-beginner/templates/morrow-embed.html
```

`--embed-snippet` adds a ready `<iframe>` tag to the JSON receipt. Browser proof for all
templates: `(cd studio-ui && node verify-diagram-templates.mjs)` (writes screenshots and
`report.json` under `local/verification/archify-templates/`).

## Review and repeatable evidence

After rendering the example:

```bash
# Package verified by doctor; disable upstream's update check on direct calls too.
ARCHIFY_UPDATE_CHECK_DISABLED=1 node archify/bin/archify.mjs \
  visual-check productions/archify-demo/creator-kit.html --json
(cd studio-ui && env -u NODE_OPTIONS -u NODE_ENV -u NODE_PATH node verify-diagrams.mjs)
```

`visual-check` needs installed Chrome; it writes screenshots and a containment report
beside the artifact. Inspect screenshots yourself; its receipt intentionally leaves
visual review pending. The first-party browser harness uses the existing Studio
`playwright-core` dependency and installed Chrome (`CHROME_PATH` override), blocks HTTP(S),
then checks actual node selection, downstream reachability, guided chapters, theme
switching and 390px horizontal containment. It writes evidence under
`local/verification/archify/`. Mobile containment is not a promise of presentation-sized
text on a phone; use zoom/presentation mode and inspect at the actual delivery size.

## Safety and storage boundaries

- Wrapper calls verify the installed file manifest, disable update checks, clear Node
  overrides and forward only a small runtime environment allowlist—not API keys.
- Object/URL-backed brand capture is rejected. Bundled brand IDs are allowed.
- The wrapper does not expose arbitrary commands, brand downloads, repository-evidence
  reads, preview servers or auto-open. It is **not an OS sandbox**; the process retains
  the user's filesystem permissions.
- Local generation needs no model/API credentials. The upstream HTML viewer may fetch
  Google Fonts when opened; do not call the default artifact completely network-free.
- Generated HTML contains JavaScript. Open only trusted authored artifacts.
- Source pin, adapter, tests, example JSON and docs belong in Git. `archify/`, generated
  productions, screenshots and local verification evidence are ignored. Source sync is
  not media backup.
- To use a diagram in video, pass `--showcase-bridge` (and optionally `--chapter-dwell 2500`
  or `--video productions/<name>/diagram.mp4`) to `creator.py diagram render`. That injects
  a deterministic `window.__ready` / `window.__advance(ms)` / `window.__done()` bridge that
  steps through `Archify.guidedViews` chapters for frame-exact `showcase` MP4 capture.

## Source review record

The downloaded release was compared against the pinned GitHub tree: 76 packaged files
were compared; 75 matched byte-for-byte by git blob hash. Only `package.json` differs,
with development scripts/dependencies removed in release packaging. The archive SHA-256
is recorded in the lock. Audit found no credential reads or install hooks; network paths
are the disabled update notice, opt-in brand capture, and viewer font requests. This is
a bounded review, not a security certification.
