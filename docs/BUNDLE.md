# Per-production manifest (`creator.py bundle`)

A production directory accumulates renders, posters, edit plans with
`.provenance.json`, and prompt-crawler `crawl.json` files. `bundle` writes a single
`manifest.json` that inventories everything and surfaces what still needs a human.

## Usage

```
python3.13 creator.py bundle --production productions/<name>
```

Writes `productions/<name>/manifest.json`. It **never overwrites**: if the manifest
already exists the command fails and tells you to pass `--output` with a new path:

```
python3.13 creator.py bundle --production productions/<name> --output productions/<name>/manifest-2.json
```

`bundle` is read-only over the production directory except for the one manifest it
writes. No network, no cloud.

## Manifest fields

- `production`, `generated_at` (ISO-8601 UTC).
- `artifacts`: every file (except the manifest) with `path` (POSIX, relative),
  `type` (video/image/html/json/audio/text/other by extension), `bytes`, `sha256`,
  `mtime`.
- `videos`: video artifacts with `duration` from ffprobe when available, else null.
- `cover`: `poster.png` if present, else the first `*.png`, else null.
- `open_decisions`: human-routed nodes from any `crawl.json` (`crawl-human-route`,
  with text/section/scores) and any `*.provenance.json` with `review_required` true
  (`provenance-review-required`).

Productions are gitignored; manifests live beside the production they describe.
