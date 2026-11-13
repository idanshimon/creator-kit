# Showcase: animated agent visuals → MP4

Two commands, both local (headless Chrome + ffmpeg, no uploads):

## `creator.py crawl` — prompt-crawler
```bash
python3.13 creator.py crawl --input path/to/SKILL.md --output productions/<name> [--video --speed 9]
```
Writes `crawl.json`, a standalone `viewer.html` (galaxy graph, crawling spider, crawl log,
route mix, coverage radar, word heat, spec score) and, with `--video`, `crawl.mp4` + `poster.png`.

What it measures: each instruction is classified by **keyword heuristics** (rule / approval /
sourced / vague / info) and routed to `code` (checkable rule), `model` (judgment) or `human`
(approval). No model call. Confidence values are rule-of-thumb, not calibrated. The spec score
= 40 expected sections present + 30 low vague wording + 30 share routed to code or a human gate.

Viewer URL flags: `?seek=N` (pre-crawl N decisions, for stills), `?speed=X`, `?render=1`
(deterministic clock for recording). Viewer loads d3 + font from CDN: needs network to render.

**Model scoring (`--scorer azure --allow-cloud`)**: each instruction gets one 5-letter question
(rule / judgment / approval / vague / source) on the highest-version `gpt-*-mini` deployment in
the inventory (`models.best_mini`; override with `--model`). Probabilities come from logprobs with
reasoning off. Routing: approval >= 0.5 -> human; rule/source >= 0.95 -> code; top answer < 0.6 ->
human (undecided); else model. gpt-5.4-mini caps `top_logprobs` at 5. 251 instructions ~36 s
with 12 parallel calls. Output records `heuristic_route` per node and `agreement_with_heuristic`.
Model probabilities are not measured accuracy.

Source of truth for the crawler: `integrations/prompt-crawler/`.

## `creator.py showcase` — record any animated HTML page
```bash
python3.13 creator.py showcase --input page.html --output out.mp4 [--seconds 20] [--scale 2] [--poster p.png]
```
Frame-exact when the page opts in to the contract:
`window.__ready = true`, `window.__advance(ms)` draws one frame, optional `window.__done()`.
Without it, pass `--realtime` (wall-clock screenshots, not frame-exact).
Speed: ~0.1–0.2 s per 1080p frame (JPEG capture). A 30 s clip at 30 fps ≈ 2–4 minutes.

Use it to turn D3/canvas/three.js agent visuals into posts or HyperFrames clips.
