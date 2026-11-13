# studio-ui

Local video-editing workspace UI for Creator Kit. A standalone,
self-contained React + TypeScript package that builds to a **static bundle**
(`dist/index.html`, `dist/app.js`, `dist/app.css`) served **same-origin** by the
parent Python server at `http://localhost:4318`. No Next.js server, no dev server —
esbuild bundles modular source files into one static app.

This package owns its own `package.json` + lockfile and changes **no other repo**.
The vendored `OpenMontage/` and `hyperframes/` trees are untouched.

## Commands

```bash
# from the repo's studio-ui/ directory
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm ci            # lockfile install
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm test          # Node test runner (timeline helpers)
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm run build     # -> dist/
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npx tsc -p tsconfig.json --noEmit   # typecheck
env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm run dev       # esbuild watch
```

The `env -u …` prefix clears inherited Node overrides so they cannot change the
install or build; it is harmless if none are set. The project `.npmrc` sets
`allow-remote=all` so npm accepts registry tarball redirects.

The parent Python server should serve `dist/` at the web root of `localhost:4318`
so `/app.js`, `/app.css`, and the `/api/*` + `/media/*` routes share one origin.

## Pinned dependencies

- `react` / `react-dom` 18.3.1
- `esbuild` 0.24.2
- `lucide-react` 0.469.0
- dev: `typescript` 5.7.2, `@types/react(-dom)`

## Architecture

```
src/
  lib/
    timeline.ts   # pure helpers + domain types (Clip/Plan/PRESETS)
    wire.ts       # tested UI asset-ID/in/out ↔ canonical path/start/end conversion
    api.ts        # typed StudioApi client (fetch, CSRF, ApiError w/ .stale for 409)
  components/
    ui.tsx        # design-system primitives (SWAP POINT) — Button/Field/Badge/fmt
    TopBar.tsx    # project select/new/rename/save, undo/redo, dirty/stale/saved badge
    AssetPanel.tsx    # binary video import + asset library -> add to timeline
    SourcePreview.tsx # SOURCE video of selected clip, seek + Set In/Out, split @ playhead
    Timeline.tsx      # ordered clips: select/reorder/duplicate/split/remove
    ClipInspector.tsx # per-clip speed 0.25..4, volume 0..2, mute
    OutputSettings.tsx# preset (landscape/portrait/square), contain/cover, global vol, fades
    ExportPanel.tsx   # draft/final render, real job list, rendered preview + download, stale mark
  App.tsx         # state orchestration, mutations, keyboard shortcuts, polling
  main.tsx        # React root
  styles/app.css  # CSS tokens — restrained dark video-editor workspace
build.mjs         # esbuild -> dist
```

CSS tokens (`:root` in `app.css`) are the single theme swap point. `components/ui.tsx`
is the design-system swap point; domain components never hardcode colors.

## Behavior notes

- **No fake data.** Every surface reads real endpoints; empty states are shown, not stubbed.
- **Local unsaved model.** Plan edits stay client-side and mark `dirty`. Save is explicit
  (creates a server revision with a label). `beforeunload` + confirm guards prevent
  accidental discards.
- **Optimistic-concurrency.** Mutations send `expected_revision`. HTTP 409 → `ApiError.stale`
  → a "stale — reload" badge and a Reload button; never a silent overwrite.
- **Export staleness.** A job rendered from an older revision than the current project is
  flagged stale in the export list.
- **Keyboard.** Ctrl/Cmd+S save, Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z (or Ctrl+Y) redo —
  all suppressed while typing in inputs/textareas/selects/contentEditable.
- **Security.** Names/paths render as React text (escaped) — no HTML injection. Upload
  filename travels URI-encoded in `X-Filename`; 256 MiB client cap.
- **Responsive.** ≤900px collapses to a single scrollable column with ≥44px touch targets.
- No AI controls in this pass; the existing cloud CLI is unchanged.

## API contract (implemented by the parent Python server)

- `GET /api/state` → `{ csrf, projects[{id,name,revision,updated_at}],
  assets[{id,name,path,duration,width,height,has_audio,url}],
  jobs[{id,status,project_id,revision,kind,result_url,error,created_at}] }`
- Every mutation sends header `X-CSRF-Token` from state.
- `GET /api/projects/:id` → `{id,name,revision,plan,history[{revision,label,created_at}],can_undo,can_redo}`
- `POST /api/projects` body `{name}` → project
- `PUT /api/projects/:id` body `{name,plan,expected_revision,label}` → project
- `POST /api/projects/:id/undo|redo` body `{expected_revision}` → project
- `POST /api/projects/:id/render` body `{kind:"draft"|"final",expected_revision}` → job
- `POST /api/assets` raw binary body, header `X-Filename=encodeURIComponent(file.name)` → asset
- Media served at `/media/:id`; a job's rendered video at its `result_url`.
- Empty plan (`clips: []`) is allowed. IDs are opaque. Errors return JSON `{error: string}`.
- API `plan` is a version-1 renderer document with width/height and path/start/end
  clips. `src/lib/wire.ts` converts to/from the browser-only state below.
  See [architecture](../docs/ARCHITECTURE.md).
- Browser verification: `node verify-studio.mjs` creates synthetic media, an isolated
  workspace and server, exercises save/undo/redo/render/download/restart, then stops it.
  `CREATOR_PYTHON` and `CHROME_PATH` override its Python/Chrome paths.
- `verify-browser.mjs` is the older partial import-only probe targeting port 4318;
  prefer the isolated full workflow test for repeatable verification.

### Browser-only editing state (NOT the API wire format)

```ts
{
  clips: [{ id, asset_id, in, out, speed, volume, mute }],
  preset?: "landscape" | "portrait" | "square",
  fit?: "contain" | "cover",
  volume?: number,      // global 0..2
  fade_in?: number, fade_out?: number
}
```
