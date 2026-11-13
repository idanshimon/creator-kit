# Operator dashboards: rules and recipes

`docs/UI-DECISIONS.md` in the repo owns the agreed rules; this is the working summary.

## UI rules

- **Data honesty:** no placeholders (say what a value waits for). Treat an empty API object as "unavailable" (a just-restarted collector returns `{}`); check the page after the first refresh, not right after deploy.
- **One attention cue:** calm 2 s ping + `N needs you` pill, reduced-motion fallback. Vibration is an Android-only bonus; a silent click reads as broken.
- Themed chips, not panel rectangles. Embeds follow the host theme. Phone-first copy. No filler labels.
- **Every click explains.** Feed `entity.detail` (why_you, decision{question, options{label, effect, url, recommended}}, sections, timeline, evidence), watcher `detail`, `agent.beat_help`. Prove with `studio-ui/probe-detail.mjs` (desktop click + phone tap).
- The agent that stops must write the owner's question and options (put that in its prompt); the builder's fallback ("approve what the risk level requires") must say it is a fallback.
- Escape all producer text (issue bodies are untrusted); allow only http(s) links.
- A tap that opens an overlay is followed by a synthetic click on the new backdrop: ignore backdrop clicks ~450 ms after opening. A direct hit on a dot beats nearby labels. Overlays need the top z-index (hosts inject sticky nav strips).
- `mission-control validate/render` return `warnings` from the spec linter; fix them in the spec builder.
- Canvas pixels are invisible to `design-check`: screenshot the canvas and run a vision pass in both themes.
- Pipeline Control specs take `figure_titles`, `cost_stages` (paid minutes only), `agent.badge`/`badge_sub`; never ship template defaults like "Commit to production" on a non-CI domain.
- Operator dashboards act, not just link, when a decision has a real backend.
- For a requested visual fix: fix the template in `creator_tools/`, add a test, re-render every consumer, record the rule in `docs/UI-DECISIONS.md`.

## Home page over several screens

- Every screen needs a way home: have the host server inject one shared top strip (Home + every screen, current marked, themed, sticky, sideways-scrolling on phone) after `<body>`; skip it for iframe-embedded pages.
- A grid of cards and numbers is boring. Lead with an end-to-end flow: clickable tiles with live numbers, coloured by status, a pulse on the step that needs the owner, animated connectors; a feedback strip under it. Then insights that say why: a daily trend whose caption names the top failing stage, a work-by-status stacked bar with distinct colours, a recent-activity feed. `align-items:start` avoids dead space.
- Order: one status box whose headline comes from live alerts and pending decisions (never "everything is running" while a decision waits), the `N needs you` pill, 3–4 live mini numbers, one card per screen with a live number and an "open when" line, a short "how to work with it" list.
- Keep a replaced dashboard at `/old` with a TODO of what lives only there; delete it once each item moved.

## Pipeline Control

`creator.py pipeline-control render --input spec.json --output X.html [--style] [--theme] [--video]`: flow line + agent gate + derived insight cards (stage time, cost per run, lead time, pass rate, failed runs) plus views `#waterfall`, `#volume`, `#heat` from one run log, with a fixed `baseline.until`.

- Every number derives from the log; flow line, agent evidence, cards and views must agree. Stage medians only over runs that reached the stage; baseline = median of daily medians everywhere. Test cross-view agreement.
- Stations stay blue unless the builder sets `live.stage_state` from data (failed when ≥25% of today's runs stopped there; slow when today's median ≥1.5× and ≥1 min over baseline). An all-healthy line on a failing day is a builder defect.
- Embed JSON with `<`, `>`, `&` escaped as `\u003c` etc.
- Prefer a fixed pre-change baseline over a rolling median (it absorbs the regression). Label any assumed rate in Explain.

## Mission Control

- `creator.py mission-control serve --page X.html --spec X.spec.json --workdir <repo> --context-dir <dir> [--port]` serves the page on 127.0.0.1 with a docked Ask pane backed by GitHub Copilot CLI (read-only tools). See `--help` for the optional work-data connector and how to disable it. Tell the agent to open the source file behind an item for history questions, or it answers from the spec summary only. Prove with `studio-ui/verify-mission-ask.mjs`. Headless Chrome hides scrollbars; for scrollbar screenshots use `studio-ui/shot-scrollbars.mjs`.
- **Map interaction:** wheel zoom toward the cursor (`{passive:false}`), drag pan with >4 px threshold, click selects only when no pan happened, double-click resets, live % label, touch pinch around the finger midpoint via Pointer Events with `touch-action:none` on the canvas. Prove with `cd studio-ui && node verify-mission-control-zoom.mjs <file.html>`. CDP touch emulation cannot lift one pinch finger; say so and ask for a real-device check.
- **"Can't click" reports:** prove selection per entity with `studio-ui/probe-select.mjs <file.html>` (`PT=touch OFF=26` simulates an off-centre finger) before touching code. Clustered data usually means a small target: taps use 36 px radius / 10 px slop, mice 22/4. Canvas-drawn labels are not clickable. Input/rAF probes stall in a background tab; that is not a page hang.
- There is no `?theme=` parameter; set `default_theme: light` in the spec for light hosts. Put caption and full-screen link in a toolbar above the iframe. Below ~1300 px offer full screen.
- Collapse finished items into one aggregate dot per group; keep one dot per open item.
- Check canvas height vs `.map-stage` height after adding anything above the cockpit.

## Audit / accountability reports

Show the actor first, not just affected people by severity.
- In Mission Control: one `brief` card per actor (what they did, whom it hit, `entity` = most affected), sectors = outcome, each affected person's watchers = the actors who touched them, exact lost items in `detail.why_you` (it renders above sections).
- Better: several views over one evidence JSON in one offline page with hash routes and a sticky tab bar — Home (headline, clickable outcome counts, actors ranked by impact), Group (actor→person flow, colour = outcome, width = count, plus a clickable grid), Person (picker, verdict sentence, per-item timeline, table that becomes cards on phone, a copyable message), and Method (rules confirmed / not proven, with source). Probe every route × viewport × theme with clicks.
- `design-check` loads only the default route; screenshot + vision every other route.
- For a read-only analysis, do not ship the cockpit as a main view: its beat loop, gate hex, decide box and score are agent-workflow parts that confuse readers. Never invent a score to satisfy the schema.
