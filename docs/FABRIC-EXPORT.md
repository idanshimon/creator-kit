# Local protected Fabric export kits

`creator_tools.fabric_export` packages **one explicitly trusted self-contained
offline HTML document** into a new local Rayfin deployment kit. It does not
publish Studio, accept arbitrary asset directories, install dependencies, sign
in, execute subprocesses, or make cloud/network calls.

## CLI

From the repository root:

```sh
python3.13 creator.py fabric package --input local/data-story-workshop.html --output local/fabric-kit --name evidence-story
node local/fabric-kit/scripts/build.mjs
```

The input must already exist and the output parent must exist; the kit directory itself must be new. This is the same local-only module API below, exposed through the real CLI. It does not install Rayfin or upload anything.

## Python API

```python
from creator_tools.fabric_export import package_site

report = package_site(
    input_html="productions/my-story/story.html",
    output_dir="productions/my-story/fabric-kit",
    app_name="creator-data-story",  # optional; this is the default
)
```

Exact signature:

```python
package_site(input_html: str | os.PathLike,
             output_dir: str | os.PathLike,
             app_name: str = "creator-data-story") -> dict
```

The caller explicitly selects and trusts that HTML artifact. No directory
contents are discovered. The input must be a plain `.html`/`.htm` file, not a
symlink, and decode as UTF-8 (an optional UTF-8 BOM is accepted). The bytes,
including BOM and line endings, are copied unchanged. A whole HTML document
with `html` and `body` elements is required.

The app name must match `[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?`: 1–63 lowercase
ASCII alphanumeric/hyphen characters, without leading/trailing hyphens.
The output parent must already exist and may not itself be a symlink. Platform
ancestor aliases such as macOS `/var` are allowed. An existing output of any kind (file, directory,
valid or dangling symlink) raises `FileExistsError`; nothing is overwritten.
Unsupported input/name/path raises `ValueError`; IO errors use normal `OSError`
subclasses. Validation completes before output is created; an IO failure during
writing removes the newly reserved kit. No output parent directories are created.
This is a local trusted-filesystem tool, not protection against a hostile process
concurrently replacing parent directories or mutating files during packaging.

The JSON-serializable return value has these fields:

- `status`: exactly `"local-deployment-kit"`.
- `deployed`: exactly `False`.
- `output_dir`: absolute output directory string.
- `app_name`: chosen slug.
- `manifest`: absolute path to the generated manifest.
- `manifest_sha256`: SHA256 of the actual manifest bytes.
- `input_sha256`: SHA256 of the actual packaged HTML bytes.
- `files`: sorted list of seven kit-relative file paths.
- `warnings`: trust/data-review and not-installed/authenticated/deployed notices.

## Scope and preflight limits

The HTML remains **trusted active code**, not sanitized or sandboxed content.
Review code, embedded data, source rights and intended audience before packaging
or upload. A successful static preflight is not a certification of arbitrary HTML
or JavaScript and does not prove offline behavior for adversarial input.

Conservative checks reject external/relative runtime resource attributes,
script `src`, stylesheet/resource links, `srcset`, external images, media/posters,
iframes, object/embed, base/frame/portal elements, form destinations, ping,
HTTP-equiv directives other than non-reporting Content-Security-Policy, CSS
`@import`, CSS escapes, `image-set()` and nonembedded `url()` targets.
Obvious inline `fetch`, XHR, WebSocket, EventSource, beacon, worker,
module-import/eval/dynamic-function, dynamic-element creation and location/window
navigation patterns are rejected, including event-handler code. These are
heuristics, not an ECMAScript/CSS/browser parser; false positives are possible and
computed, obfuscated, reflective or indirect operations can evade them. Do not
use this tool as an untrusted HTML upload boundary. If the artifact needs remote
code/data/fonts/maps, produce a genuinely offline artifact first rather than
weakening the guard.

Normal HTTPS/HTTP source anchors and fragment anchors remain allowed. Safe
base64 raster image, font, audio and video data URIs are accepted as resource
values; SVG/HTML data documents are deliberately unsupported. SVG fragment
references are supported. Data payload decoding checks format, not media validity.

## Generated files

```text
fabric-kit/
  .gitignore
  README.md
  manifest.json
  package.json
  rayfin/rayfin.yml
  scripts/build.mjs
  site/index.html
```

`package.json` uses **exactly** `@microsoft/rayfin-cli: "1.36.2"` as its sole
devDependency. Supported Rayfin Node engines are **20/22/24**. There is no
fabricated lockfile, `node_modules`, install, auth or deployment. Rayfin config
contains no actual workspace/item IDs, redirect URLs or credentials:

- Fabric auth enabled, password auth disabled.
- `staticHosting` enabled, folder `dist`, build command `npm run build`,
  index document `index.html`, `assetAccess: protected`.
- Data, storage and functions disabled.
- Empty allowed redirect list until the real hosted URL is known.

The `.gitignore` excludes environment files, deployment state, `node_modules`,
`dist` and build staging directories. Keep actual IDs/URLs in local deployment
configuration rather than committed source; `.gitignore` is not a secret scanner.

## Build and identity verification

Run locally from the kit (no dependency installation required):

```sh
node scripts/build.mjs
# equivalent: npm run build
```

The script uses Node standard-library APIs only and locates the kit relative to
itself, not the current working directory. It verifies `site/index.html` SHA256
and byte length against `manifest.json` **before any dist/staging mutation**.
Unexpected site files, a symlinked site/index/manifest or a symlinked dist are
refused. Only the verified HTML bytes are written to `dist/index.html`; unrelated
files such as `.env` are never copied. A modified HTML must be reviewed and
repackaged, not quietly adopted by rebuilding. An existing successful dist remains
unchanged when integrity checks fail.

The manifest has `schema_version: 1`, `algorithm: "sha256"`, and `files`, a mapping
from each of the six nonmanifest relative paths to `{ "bytes": integer,
"sha256": hex_digest }`. It records the initial bytes of **every** generated
artifact except itself (no self-referential digest). The return value separately
hashes the manifest. The build enforces the **site** hash, not the whole kit:
Rayfin config must be editable for redirect registration. Initial config hashes
remain historical byte identity, not claims that edited files are unchanged.
Neither an unsigned manifest nor its reported hashes establish authenticity,
source accuracy, source/query lineage, analytical correctness, safety or
independent verification. Someone able to edit both site and manifest can defeat
the check. Local build success is not a Rayfin compatibility/deployment test.

## Manual Fabric upload

These commands are instructions, not actions performed by the packager.
Before upload, confirm the Fabric Apps preview workload is enabled in the tenant,
the workspace has a running supported capacity, the region supports the workload,
and both the deploying identity and intended viewers have appropriate
workspace/item permissions. Use a Rayfin-supported Node 20/22/24 release and
review current Microsoft requirements:

- <https://learn.microsoft.com/en-us/fabric/apps/overview>
- <https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli>

From the generated kit directory:

```sh
npm install
npx rayfin login
npx rayfin up --workspace-id <workspace-id>
```

Use `npm install`, **not** `npm ci`: this kit has no lockfile until the first
real install. The direct CLI dependency is pinned, but transitive versions are
not locked until installation. Review the dependency tree and any vendor install
scripts, then retain the real resulting lockfile for reproducibility.

Add the **actual** hosted redirect URL printed by the initial deployment to
`services.auth.allowedRedirectUris` in local `rayfin/rayfin.yml`, then run:

```sh
npx rayfin up staticapp deploy
```

Use the staticapp deploy command after subsequent reviewed snapshot builds too.
Keep actual workspace/item IDs, URLs, credentials and `.deployments.json` local.
After cloud writes, read deployment status back and open the real URL as both
intended allowed and disallowed users. Only those checks can support a claim of
successful protected deployment. Packaging and local build alone cannot.

## Data and access boundary

The supplied HTML may carry confidential data. Fabric identity/item permissions
protect access to the static artifact **when actually deployed and verified**;
the default config is merely that intention until then. Every authorized app
viewer receives the whole extract. Semantic-model **per-viewer row-level security
is not inherited** by static snapshots extracted under the refresh operator's
identity. Scope snapshots to the audience, remove secrets/identifiable data as
required, or design a separately authorized server-side/live-query path. The
operator owns that review. No live semantic-model refresh is provided.

## Local verification

```sh
python3.13 -m unittest tests.test_fabric_export -v
```

Tests create real temporary directories under `TMPDIR` and execute the generated
build directly using `node`, with no install. They verify exact copied bytes,
manifest hashes, refusal/no-overwrite boundaries, conservative network checks,
secret-copy avoidance, symlink/extra-file failures and tamper-before-dist-mutation.
The dependency-free build can be exercised on a newer host Node, but that is not
proof that the pinned Rayfin CLI supports that Node release.

The thin wrapper is inspired by
[Sanjay Narendran's CMS Hospital Insights](https://github.com/SanjayNarendran/MS102-public-CMS-Hospital-Insights-fabric-rayfin-GHC).
