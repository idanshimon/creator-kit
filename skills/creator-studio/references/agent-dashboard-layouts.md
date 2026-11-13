# Agent dashboard layouts: picking the shape for the domain

Mission Control's orbit answers "which of many items needs attention now?". Other operational domains need a different main shape. The agent rail stays the same everywhere: the 7 beats, what it noticed, the evidence, the proposed action, and the Approve/Reject gate.

| Question the operator asks | Layout | Fits |
|---|---|---|
| Which of many items needs attention? | Orbit (Mission Control) | cohorts, fleets, accounts, patients |
| Where is work stuck right now? | Flow line: stages left to right, runs as moving dots, queue badges, agent hex checkpoint at the failing stage | CI/CD, deployments |
| Why was this run slow? | Run waterfall: actual bars over dashed median ghosts, delta labels | detail view of one run |
| Where do items drop out? | Volume flow — see "Attrition charts" below; a Sankey is the wrong default | data/ETL, funnels |
| What repeats across many items? | Heat grid: rows × days, agent-found pattern boxed | portfolio of pipelines |
| Is it getting worse, and can I trust the number? | Insight cards from our data-story pattern: rail + headline + trend + "Explain this figure" | weekly review under any live view |

A proven combination for pipelines: the flow line on top (live), the data-story insight cards below (trend plus proof), in the `claude` style.

## Attrition charts (volume flow)

When losses are small next to the total (e.g. 16 of 204), a Sankey/funnel drawn from zero shows almost nothing, and it cannot compare periods. Pick by question:

| Question | Chart | Note |
|---|---|---|
| Which stage got worse? (agent's question) | Arrow/dumbbell plot: one row per stage, last week's failure rate → this week's, red worse / blue better, counts at the right | default main chart; shows improvements a funnel hides |
| How many lost, step by step? | Zoomed step-down waterfall | state the truncated axis on the chart; it exaggerates size |
| Share surviving each stage, two periods | Survival line | honest but hides WHICH stage changed when totals are close |
| Which runs stopped, and where? | Unit/waffle: one tappable square per run, coloured by stop stage | honest scale, drill-down; no period comparison |

Recommended pairing: arrow plot on top, unit squares below. Derive reach/drop from `stage_minutes` presence and `failed_stage`; test `reach[i] - drop[i] == reach[i+1]`. Build trials by reusing `pipeline_control.derive`.

## Trial procedure

0. When asked for "more solutions" for one chart, research the chart class first (practitioner guides such as Datawrapper/Atlassian/Preset), state why the current one fails, then build 3–4 alternatives from the shipped module's derived data and show them next to the current view.

1. Build ONE synthetic dataset and render every candidate layout from it, so the comparison is about shape, not data. Put the trial builder in `productions/<name>-trials/build.py`, reusing `creator_tools.styles` (`styles.style_css(style)`, `--mc-*` tokens) so every trial can be re-skinned with `python3.13 build.py <style>`.
2. Derive every number on the page (headlines, deltas, agent evidence lines) from one generated run log in code. Hand-typed numbers in parallel views drift and contradict each other. Record the source, period, row count, calculation and log digest in each figure's Explain panel.
3. Use shared chrome: tabs linking the views, a theme toggle, a synthetic-data pill, and the same agent rail. SVG charts are drawn at measured width with `style="fill:var(--mc-x)"`; presentation attributes cannot resolve `var()`.
4. Gate with `creator.py design-check` at desktop and phone widths in both themes. Wrap wide SVG in an `overflow-x:auto` container and give the mobile grid `minmax(0,1fr)`, or the page scrolls sideways.
5. design-check reads DOM text only. Text inside SVG/canvas (axis labels, station names) is unchecked, so screenshot every view (`ffmpeg hstack/vstack` sheet) and run a vision critique. Fix chart defects it finds: integer series need integer ticks, % axes run 0–100, add axis unit labels, use round tick steps, `align-items:start` on card grids so one open Explain panel does not stretch its neighbour, and put "worse/better" text next to colour.
6. Open all variants in one new Chrome window (one tab each), then ask which shape to promote. Promote to a `creator.py` command only after the owner picks one; until then it is a trial in ignored `productions/`, not shipped.

## Feeding the templates real data (another project's dashboards)

Keep the mapping code in the consuming project (fetch → raw cache → build specs), not in the kit; render with the CLI. Cache the raw fetch to a file first — GitHub timelines/jobs take minutes and every layout fix needs a re-render, not a re-fetch.

- **Pipeline Control from GitHub Actions:** one run per workflow run (exclude `pull_request` and `cancelled`); stages = job steps grouped by name prefix, plus a "wait for runner" stage = first job `started_at` − run `created_at`; drop stages after `failed_stage`; `first_try` = success on attempt 1. Map renamed historical step names too (count distinct step names across the window first).
- **Flow-line station colours are the builder's job.** Without `live.stage_state` every station renders healthy even on a day of failures, which reads as "nothing stuck". Derive it from the log: `failed` when ≥25% of today's runs stopped at the stage, `slow` when today's stage median is ≥1.5× and ≥1 min over the baseline median, else `ok`; add today's last few failed runs as `failed` live dots at their stage.
- **Real runner rate:** Azure Cost Management actual cost of the runner resource ÷ self-hosted run minutes in the SAME whole-day window ending yesterday (cost data lags). Exclude GitHub-hosted workflows from the minutes. Query runs one day at a time — the runs API stops at 1000 results per query, which silently inflates the rate. Write the formula, window and exclusions into `rate_note`; it is an effective rate, say so.
- **Mission Control from issues:** one entity per work item; sector = item type; stage from real state; any score formula is a ranking, state it in the subtitle. Watchers come from real comments/labels/PR state; show "not yet" rather than inventing values.
- **Phone sideways scroll (design-check Floor) from data, not the template:** long unbreakable words in the title (a ~14-char brand name), a long badge/banner/model name, URLs or long path tokens in entity text. Keep title/badge/banner short, cap entity labels ~30 chars, strip URLs and ellipsize long tokens. Find the offender at 390px by listing elements whose right edge exceeds the viewport, and compare against the bundled example (which passes).
- `render` refuses to overwrite an existing output; delete it (and the old shots dir) before re-rendering.
- Canvas text (beat ring, hex gate, legend) is outside design-check; report template-level overlaps instead of editing the kit unless asked. When asked to fix UI bugs and design, fixing the template is authorized; add a test in `tests/test_mission_control.py`. Current geometry: critical ring at 0.40 so dots clear the beat-dial labels, wide per-sector spread, staggered radius in busy buckets, gate hex at 0.82 of the arm, worklist score `nowrap`.
- Pipeline Control chart axes: tick generation must be bounded (~5 round ticks via a nice-step); one real outlier once produced thousands of 10-minute ticks and an unreadable black axis. Stages no run reached render "never reached", not 0.0 min.
- Collapse finished items into one aggregate dot per group, keeping one dot per open or needs-you item. Dozens of stable dots crowd the orbit and hide what needs attention.
- Mission Control has no `?theme=` URL parameter. For a light host, set `default_theme: light` in the spec. Embed it with a toolbar above the iframe for the caption and the full-screen link; an overlay button covers the cockpit's own top-bar buttons. Below ~1300px the cockpit's three rails squeeze the map, so offer full screen.
- Cache real data and add a fast partial refresh (re-fetch only the items/comments) so you can re-render after agent activity without the slow full fetch.
- To show it on a phone, copy the single-file HTML into an existing served app and verify the public URL renders (title, canvas present, no CSP errors).

## Making the rendered screens live ("make it live")

A snapshot page goes stale within the hour; owners expect live. Run the whole fetch → build → render loop inside the serving service:

1. **Vendor the renderers, don't install the whole kit.** `mission_control`, `pipeline_control`, `data_story`, `styles` are stdlib-only; copy them plus `integrations/design-md` into `vendor/content_creator/` with a `VENDOR.md` recording the kit commit, via a re-runnable sync script. Call `validate_spec` + `render_html` directly (the CLI `run()` refuses to overwrite outputs).
2. **Check the server's token scopes before designing the fetch.** Probe each endpoint from inside the container; a fine-grained Actions-only token gets 403 on issues/timelines. Instead of minting a broader token, add a repo workflow (event-driven on issues/comments/PRs + a schedule, workflow token with read permissions, self-hosted runner, concurrency cancel-in-progress) that exports the items as an artifact; the server downloads the newest artifact with the Actions token. Use `add_unredirected_header` for Authorization, because the artifact zip redirects to blob storage, which rejects a forwarded bearer.
3. **Cache incrementally in a named volume:** jobs keyed by `run_id:attempt`, closed days of runs kept, only today and yesterday re-fetched. Cold start took minutes; warm refreshes took tens of seconds.
4. **Retry 5xx/URL errors with backoff, write outputs atomically (tmp + rename), and keep serving the last good render on failure.** Expose a `/api/views-status` (last_ok, last_error), and show "rebuilt N min ago (data as of M)" on the home page.
5. **Name the data that can't be live** (for example, cost with no cloud login on the server) as a baked, dated file, and add a TODO, rather than presenting it as live.
6. **Verify on the server after the first cycle:** status `last_error: null`, every route 200, a new real item appearing with no manual rebuild, and memory/CPU in the container. Confirm the container was actually rebuilt (its uptime, plus a marker of the change in the served HTML) before judging a fix: a timed-out rsync/compose step can leave the old image serving.
