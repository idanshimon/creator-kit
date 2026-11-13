# Analytical stories: evidence and publication workflow

Use for data-story reading pages, chart-local Explain panels and static analytical exports. Keep project-specific source findings and implementation status in the consuming repository; this reference owns the method.

## 1. Establish the data and evidence contract

- Identify the user's question and the decision the figure supports before choosing charts.
- Keep source URL/snapshot, extraction identity, actual period per series, filter scope and denominators with the figure input.
- Derive headline values, deltas, chart points and narration from one fact model; label human interpretation separately because a trend alone does not establish its cause.
- Record exact queries only where they actually ran. Distinguish a local-file calculation, a build-time semantic-model query and a live per-viewer query.
- Bind verification to the exact extract, preferably by content digest. Validate the displayed result as well as its inputs; agreeing totals do not prove a stored plotted ratio is correct.
- Preserve missing, stale and mismatched evidence as distinct states. Label supplied checks honestly; a digest match does not independently certify the source.

## 2. Author the experience

Use a narrative rail beside the figures for exploratory reading, or the existing staged presentation template for a deck. Explain one important figure concretely: source -> inputs -> arithmetic -> rounded display. Keep period differences and filter scope visible so a national chart is not mistaken for a locally filtered one.

Keep units next to both latest values and deltas; a unitless change can be mistaken for a percentage or ratio. State the comparison explicitly (first point versus previous point, absolute versus relative) and distinguish source-ordered observations from a continuous calendar axis. Preserve pooled ratios as sums of numerators divided by sums of denominators, not averages of individual ratios.

Exercise native navigation, Explain controls, theme switching and narrow layouts in the generated page. Check the same numeric fact against CLI output, chart and explanation. Include hostile author copy, long queries/URLs and narrow-screen evidence expansion: escaping can be correct while the resulting text still breaks layout. Inspect actual screenshots; authored reference images prove design intent, not executed interactions. If a full-page image exceeds the vision input limit, inspect labeled crops and retain the original; do not describe a crop as a full-page review. Capture current data and real interactions before final narration.

## 3. Capture the deployment recipe from source

Read deployment configuration, package scripts, lockfile and the author's runbook together. Record:

1. Supported runtime and workload/capacity/region/permission prerequisites.
2. Working directory and dependency installation command. Use `npm ci` only with a real compatible lockfile; otherwise document the intended install and resulting lock separately.
3. First upload command and which resources it creates or overwrites.
4. Hosted redirect URI and permission setup required after the first deployment.
5. Update command after regenerating the extract.
6. Read-back checks for the exact hosted app or model target.

Keep website hosting and data/model publication as separate paths. A static export can be hosted without publishing a semantic model; publishing a model does not update the website until its extract/assets are regenerated and redeployed.

For third-party hosting tools, take the upstream commands from that tool's own pinned docs. Check the consuming project's current docs and CLI help for any reusable local packaging feature; research or a proposal does not establish that one is installed.

## 4. Verify packaging without overstating it

- Run packaging probes in an isolated temporary copy with clearly inert fixtures; never insert test placeholders into a real data build.
- Check absent mandatory assets and unresolved lazy references fail. If semantic validity is a requirement, also reject empty/malformed data; presence checks alone are not a semantic gate.
- Rewrite content-hashed lazy data URLs before hashing their parent loader scripts, so refreshed data invalidates the loader's cache key.
- Check the generated manifest against actual output bytes and preserve existing destinations on refusal, including dangling symlinks.
- Tamper with the packaged site in an isolated kit and rerun its real build; require failure before the last good output changes. An unsigned manifest proves byte agreement, not authenticity, source accuracy or safe code.
- Separate packaged, locally built, authenticated and deployed evidence. Do not claim cloud success from a local build.

### Execute the reusable authoring-to-kit path

From the repo root, choose new output paths and an installed supported Python runtime:

```sh
python3.13 creator.py data-story validate --input story.json
python3.13 creator.py data-story render --input story.json --output local/review-story.html
PYTHON=python3.13 node studio-ui/verify-data-story.mjs
python3.13 creator.py fabric package --input local/review-story.html --output local/review-fabric-kit --name evidence-story
node local/review-fabric-kit/scripts/build.mjs
```

The browser harness tests its own synthetic fixtures; also inspect the actual authored `review-story.html` before packaging it. Create the output parent beforehand, but leave the HTML and kit destination nonexistent. Compare the authored HTML, packaged `site/index.html` and built `dist/index.html` byte-for-byte or by SHA256. After a visual correction, rerun affected tests/browser checks and build a new kit from that corrected artifact; old screenshots and a passing earlier build do not qualify changed bytes. Keep synthetic demonstrations visibly synthetic, and never present their placeholder source links as retrieved evidence.

## 5. Preserve the access boundary

Treat a static extract as readable by every authorized viewer of its assets. Hosting sign-in does not automatically reproduce the source semantic model's per-viewer row-level security. Scope the snapshot to its audience or design an explicitly authorized server-side query path.

Package only the explicit approved export, not the editor server, SQLite workspace, media library, credentials or arbitrary neighboring files. Inventory live routing, map and geocoding calls separately: protected hosting does not prevent browser requests from sending search terms to outside services.
