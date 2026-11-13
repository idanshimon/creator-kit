# Evidence-backed data stories

`creator.py data-story` makes a **standalone, offline HTML reading page**, not a Studio timeline, video, live dashboard, source reconciliation service or deployed application. It uses Python's standard library, native SVG, inline CSS/JavaScript and native `<details>` explanations. No installation, CDN, backend, paid model or cloud call is required for rendering.

## Quick start

From the repository root, using the project's Python 3.10+ runtime:

```sh
python3 creator.py data-story validate --input examples/data-story/synthetic-workshop.json
python3 creator.py data-story render --input examples/data-story/synthetic-workshop.json --output local/data-story-workshop.html
```

Open the resulting file directly in a browser. Choose a **new `.html` path** for every render. Existing files, directories and output symlinks are refused. Validation finishes before any destination directory/file is created. Source links are navigation links, not fetched runtime dependencies; following one deliberately leaves the offline page.

The example is unmistakably **SYNTHETIC**: all workshop numbers, dates and extracts are invented software fixtures, not CMS data, measured operational results or clinical findings. `example.org` URLs identify illustrative source locations, not real source evidence.

## Input contract

The JSON root contains nonempty `title`, `introduction` and `figures`. Each figure contains:

| Field | Contract |
|---|---|
| `id` | Unique identity matching `[A-Za-z][A-Za-z0-9_-]*`; renderer namespaces its DOM anchors |
| `title`, `question`, `unit` | Nonempty strings; units accompany the derived latest and evidence values |
| `interpretation` | Required human-authored text, visibly separate from calculated facts; it is not certified by verification |
| `kind` | `scalar` or `pooled_ratio` |
| `source` | `{ "url": "https://…", "label": "…" }`; absolute HTTP(S), no credentials, whitespace, control characters or backslashes |
| `extract` | `{ "id": "snapshot identity", "time": "2026-10-01T12:00:00Z", "mode": "local" }`; ISO-8601 timestamp with timezone |
| `points` | Nonempty list, supplied in intended display order; every point has a nonempty actual `period` label |
| `verification` | Optional declaration described below; absent means **Not verified** |

Periods are source labels, not inferred dates or assumed equally spaced years. Preserve actual start/end dates, gaps, reporting exceptions and overlapping windows in those labels. The validator checks presence, not the truth or statistical comparability of periods. The line chart is an **ordinal/source-order** display, not a continuous calendar axis; the complete periods appear in chart point descriptions and Explain. Each figure has its own zero-inclusive scale; cross-figure scales are not comparable.

A scalar point:

```json
{"period": "SYNTHETIC: 2025-01-01 through 2025-03-31", "value": 12}
```

A pooled-ratio point:

```json
{"period": "SYNTHETIC window A", "observed": [1, 9], "predicted": [2, 3]}
```

For each point, `sum(observed) / sum(predicted)` is calculated; the example gives `10 / 5 = 2`, **not** the mean of `1/2` and `9/3`. Both fields can instead be scalar aggregate totals, with the same formula. Arrays must be nonempty and have equal component counts. Observed inputs must be nonnegative and **every predicted input positive**; zero predicted values are refused even when the sum is nonzero. Negative scalar values are allowed. Booleans, numeric strings, NaN, infinity and nonfinite derived results are refused. Duplicate JSON object keys are refused.

All numeric surfaces use one validated fact model:

- Chart points and Explain values use the same derived `values`.
- `latest` is the last supplied point, not the greatest value or lexicographically latest period.
- `delta` is `latest − first`, in the same units; it is not a percent change or previous-point comparison. A single point has delta zero.
- Display uses six significant digits; raw inputs remain available in Explain. CLI validation returns unrounded numeric facts and calculation inputs.

The source/extract declaration is per figure and applies to all of its points. Split a figure if its observations require distinct extract identities or source URLs.

### Local versus executed-query evidence

`extract.mode = "local"` is labeled **Local-file extract**, with no executed query claimed. Do not include a `query` key in local mode. The extract identity is an operator-supplied identity, not a filesystem access path; the renderer never opens source files or checks their existence.

`extract.mode = "query"` additionally requires nonempty `extract.query`. This is displayed verbatim as **Exact executed query (source-supplied)**. Supply only the actual query used to obtain this extract, not a suggested query or an assistant-generated reconstruction. The renderer does not execute it, authenticate, inspect a semantic model or prove that it ran. Never include credentials or secrets in a query or other frontend field.

### Extract-bound supplied checks

First validate the exact figure **without** its `verification` declaration. The CLI returns its SHA256 digest, derived latest, delta, inputs and values. An upstream checker may attach:

```json
"verification": {
  "digest": "<exact digest returned by validate>",
  "status": "passed",
  "expected_latest": 18
}
```

This is accepted only when the digest matches, status is exactly `passed`, and the numeric `expected_latest` equals the unrounded derived latest. No tolerance is silently applied. A mismatch, stale extract, failed status or missing field fails validation/rendering instead of displaying a passing badge. Remove a stale declaration and rerun checks rather than changing the digest to conceal a failure.

The badge reads **Supplied checks passed**, explicitly **not independent source certification**. It proves only agreement of the declaration with the payload identity and derived latest; the CLI did not retrieve source data or independently reconcile every plotted value. A digest is not a signature, does not identify a trusted verifier and does not authenticate the source. Anyone who controls the document can calculate one. Human interpretation is still labeled human-authored and is not made factual or causal by a passing declaration.

For upstream Python callers:

```python
from creator_tools.data_story import figure_digest
sha256 = figure_digest(figure)
```

Canonical digest calculation: remove only the top-level `verification` key from the figure; encode `json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)` as UTF-8; SHA256 those bytes. Everything else in the figure, including source, extract, periods and interpretation, participates. No newline, normalization or whitespace rewriting is added. Reuse the Python helper when possible rather than approximating cross-language float serialization.

## Embedding

To embed a story in a host page, use a same-origin `<iframe>` and size it to `contentDocument.documentElement.scrollHeight`.
If the host is dark, click the story's `#theme` button on load. Keep period labels short (`PR #70 · 11/06`); the full
method belongs in Explain. See [UI-DECISIONS.md](UI-DECISIONS.md#composition).

## Reader experience and safety

The responsive narrative rail links to each figure; the current figure is indicated during reading. Charts have accessible names and source-period/value descriptions. Each figure's keyboard-operable **Explain this figure** exposes source URL, extract identity/time, calculation inputs, periods, exact query/local mode, digest and verification state. Light/dark themes use a button with explicit pressed state. The page respects reduced-motion preference.

Untrusted author content is HTML-escaped as text or attributes; it is never interpolated into executable JavaScript, CSS or raw HTML. Closing script sequences, quotes and markup remain inert text. A restrictive Content Security Policy prohibits runtime connections and external resources. Long URLs, queries and headings wrap rather than causing page-level overflow.

The renderer intentionally does not interpret author prose, infer causality, establish statistical validity, fetch sources, reconcile underlying datasets or evaluate a query. Check those upstream before sharing. All content in the resulting HTML is browser-readable; it must contain no secrets. A static extract **does not inherit per-viewer semantic-model row-level security**. Scope the whole snapshot to its audience; hosting/authentication/export packaging are separate concerns.

## Verification

Focused behavioral tests (no third-party Python dependencies):

```sh
python3 -m unittest discover -s tests -p test_data_story.py -v
```

Local browser harness, using **already installed** `studio-ui/node_modules/playwright-core` and local Google Chrome:

```sh
node studio-ui/verify-data-story.mjs
# Optional new evidence directory:
node studio-ui/verify-data-story.mjs local/verification/data-story/my-new-run
```

`PYTHON` and `CHROME` can select an installed Python executable and local Chrome path. The harness does not install dependencies, download browsers, start a server or contact cloud services. It renders via the real CLI, opens `file://` HTML in an offline context, verifies chart/CLI latest agreement, actual native Explain open/close via pointer/keyboard, navigation hash/current state/scroll, theme changes and mobile overflow at 390px/320px. A separate clearly synthetic hostile-text fixture exercises source-supplied query/verification rendering. The harness asserts zero page/console errors and zero HTTP(S) page requests, saves PNG screenshots and a SHA256-bound `browser-evidence.json` under `local/verification/data-story/<run>/`. A successful local browser run is not deployment or source-certification evidence.

### Design and control copy

This is a sparse narrative reading page for readers checking a static observation before acting, not a KPI grid or operations console. The local-file/offline contract overrides CDN frameworks/fonts/icons; native controls keep the artifact portable and keyboard-operable. Arbitrary figure counts are supported, including fewer than three rail destinations.

| Element | Copy | Meaning |
|---|---|---|
| Disclosure | Explain this figure | Reveal provenance and reproducible calculation inputs |
| Missing declaration | Not verified | No supplied verification declaration exists |
| Accepted declaration | Supplied checks passed | Payload binding and expected latest agree, not source certification |
| Prose label | Human interpretation | Author commentary, not a derived fact |
| Theme control | Use dark theme / Use light theme | Switch local reader appearance |
