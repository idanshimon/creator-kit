# Pipeline Control (`creator.py pipeline-control`)

A pipeline monitoring page built from **one run log**: a live flow line on top, the agent's
approval panel beside it, and "What changed" insight cards below in our data-story pattern.

```bash
python3.13 creator.py pipeline-control validate --input examples/pipeline-control/checkout-service.pipeline.json
python3.13 creator.py pipeline-control render \
  --input examples/pipeline-control/checkout-service.pipeline.json \
  --output productions/<name>/pipeline.html [--style claude|linear.app|...] [--theme dark|light] [--video out.mp4]
python3.13 creator.py design-check --input productions/<name>/pipeline.html
```

Default style is `claude` (warm, light). Any style from `creator.py style list` works.

## What is on the page

- **Flow line** — stages left to right, today's median per stage and the baseline ("was"),
  running/waiting/failed run dots, queue badges (counted from waiting runs), the agent
  checkpoint at its stage. Click/tap or keyboard-select a station or dot for details.
  On phones the line scrolls sideways with a visible hint.
- **Agent panel** — the 7-beat loop, the finding, evidence and the Approve/Reject gate.
  The first evidence lines are *derived* from the run log so they always match the cards.
  Approve/Reject only change the page (simulated); nothing is sent anywhere.
- **What changed** — five cards: slowest-growing stage time, **cost per run**, commit to
  production, first-time pass rate, failed runs. Each has a headline, the latest value, the
  change vs baseline in words (better / worse / about the same), a daily chart with the
  baseline as a dashed line, and **Explain this figure** (source, period, calculation,
  baseline, rate, daily values, log digest).

## Other views (tabs at the top; the URL hash keeps the view: `#flow`, `#waterfall`, `#volume`, `#heat`)

- **Run waterfall** — the slowest passed run on the latest day. Each stage bar sits on a dashed
  box of that stage's baseline median starting at the same point, with the difference labelled.
- **Volume flow** — where runs stop, last 7 days vs the 7 before, with five chart types
  (sub-tabs, URL `#volume/<type>`; default `arrows`). Research: Datawrapper (zoom in and say so
  when losses are small next to the total; arrow plots for change), Atlassian (plain bars beat
  funnel shapes), Preset (Sankeys are hard to compare across periods).
  - `arrows` — change arrows: failure rate per stage (failed there ÷ reached), last week → this
    week; red worse, blue better. Answers "what got worse?" directly. Default.
  - `units` — every run is a square, coloured by where it stopped; tap a square for the run.
  - `steps` — zoomed step-down from runs started to runs finished; the zoom is stated on the chart.
  - `survival` — share of runs still going after each stage, this week vs last (zoomed, stated).
  - `bands` — the original flow bands (width = runs reaching each stage).
  Tested: `reach[i] − drop[i] = reach[i+1]`, and the squares per stop equal the drops.
- **Heat grid** — stage × day. Colour = that day's stage median ÷ baseline (normal, 1.25–2×,
  2× or more); number = failed runs at the stage. A dashed box marks the first day the
  slowest-growing stage reached 1.5× its baseline. Tap a cell for the exact values.

All three are derived from the same run log as the flow line and cards; the agent panel stays
on every view.

## Measuring improvement

`baseline.until` fixes the comparison to the days before a change, so a slow week does not
become the new normal. After a fix, the cards show whether time and cost return below the
dashed line; the cost card states the weekly difference at today's volume
(`cost difference × runs on the latest day × 7`). Without `baseline`, the page says it
compares with the previous 7 days (rolling).

## Input (JSON)

| Field | Meaning |
|---|---|
| `pipeline`, `title`, `subtitle`, `data_label`, `style` | Labels; `data_label` shows as a pill (e.g. "Synthetic data") |
| `runner_rate_usd_per_min`, `rate_note` | Cost input. Shown in Explain. Replace the example's assumed list price with your real rate |
| `stages[]` | `{id, name}` in order |
| `runs[]` | The run log: `{id, date YYYY-MM-DD, status passed|failed, failed_stage, first_try, stage_minutes{stage: min}}` |
| `baseline` | `{until: YYYY-MM-DD, label}` — fixed baseline |
| `live` | Optional snapshot: `stage_state{stage: ok|slow|failed}`, `runs[{id, stage, state running|waiting|failed|done, progress 0..1, message}]` |
| `agent` | Optional: `{stage, finding, action, evidence[]}` |

The example is synthetic (`examples/pipeline-control/make_example.py`, seed 4812): a new runner
image on Nov 4 makes Integration and cost per run jump. A real GitHub Actions export only needs
mapping into `runs[]`; no importer is shipped yet.

## Rules

- Numbers are derived in Python from the run log, never typed into the page.
- Stage time uses only runs that reached the stage (a run that failed earlier has no time
  there, not zero). Flow line, agent evidence and cards use the same method.
- Text is escaped; the embedded data cannot close its script tag.
- Output is one offline HTML file; `--video` records it with `showcase` (deterministic hooks).

## Verification

`tests/test_pipeline_control.py` (derivation, agreement between views, cost arithmetic,
fixed vs rolling baseline, queues, bad input, escaping, no overwrite). Browser: `design-check`
passes Floor in `claude` and `linear.app` at 1440 and 390 widths in both themes; a 16 s MP4
was recorded and sampled (flow line → cards). Canvas/SVG text is not covered by
`design-check`; review screenshots too.
