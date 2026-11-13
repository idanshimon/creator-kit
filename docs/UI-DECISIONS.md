# UI decisions (cross-renderer)

Decisions taken while shipping real dashboards (BreakingTrades Agent Ops, Release
Pipeline, Agent Memory) with Mission Control, Pipeline Control, Archify diagrams and
data stories. Each rule says what we do and why. Renderer-specific detail lives in
[MISSION-CONTROL.md](MISSION-CONTROL.md), [DIAGRAMS.md](DIAGRAMS.md) and
[DATA-STORIES.md](DATA-STORIES.md).

## Data honesty

- **Every number comes from data.** Builders derive values from fetched sources; nothing is
  typed in. A ranking formula (for example *score = stage base + hours open*) is fine,
  but it is shown on the page, not presented as a measurement.
- **Missing is not zero.** If a value cannot be measured, say "not measured" or leave the
  field out. A flat zero line is only shown when zero is the real, explained baseline
  ("these PRs merged before memory existed").
- **Say what a value waits for.** Never show placeholders such as `unleveled`, `unknown`
  or `n/a`. Write the reason: `waiting for you`, `not set`. `mission-control validate`
  warns about these words.
- **State real vs assumed** in the hand-off: real (fetched), derived (method shown),
  assumed (a choice such as the baseline date), missing.

## Attention

- **One cue for "needs you": a calm 2 s ping.** A ring grows and fades on items in the
  critical ring, and on a human watcher whose status is `waiting`. The scope bar shows a
  pill `N needs you`, and its dot pings. No other element pulses, so the motion keeps its meaning.
- **Not a fast flicker.** The earlier 4 rad/s wobble read as jitter, not urgency.
- **Respect reduced motion.** With `prefers-reduced-motion: reduce`, the ping becomes a
  steady double ring and the pill dot a steady halo.
- **Vibration is a bonus, not the channel.** Android only, after the first tap (a browser
  rule), one short pattern per *new* attention item (remembered in localStorage). iOS
  Safari has no vibration API. Real alerts belong in a push or chat notification.

## Every click explains

- **A click answers "what is this and what do I do".** Any item, watcher or step opens a detail
  sheet. For items that need a person it starts with **Why you are needed** and **The decision**
  (one plain question, options with their effect, the recommended one marked, links to where the
  answer is recorded). Facts, findings, who is watching, timeline and evidence follow.
- **Producers own the question.** The agent that stops must write the question and options; a
  builder falls back to the approval the risk level requires and says that it did.
- **A direct hit on a dot wins** over labels drawn near it; touch taps get a larger target and
  ignore the synthetic click that follows a tap.
- **Fake buttons are not decisions.** Demo Approve/Reject only appear when no real decision
  link exists.

## Theme fit

- **Labels on the map are themed chips, not panel rectangles.** Rounded, tinted with the
  watcher's own colour over the map background, with a thin border of the same colour. Flat
  `panel` rectangles turned into white boxes in light mode.
- **Map overlays are translucent.** The HUD and legend use a surface tint, a blur and a pill shape in
  both themes.
- **Embeds follow the host theme.** A page that embeds same-origin artifacts passes
  `?theme=` to Archify and, for data stories, clicks the story's `#theme` toggle when
  the host is dark. Never leave a light slab inside a dark page.

## Phones first

- **The page never scrolls sideways at 390 px.** `design-check` fails it; fix the cause.
- **Long words do not wrap.** One 14-character word in a title (`BreakingTrades`) pushed
  the whole page 41 px wide. Keep title words, badge, banner and model name short; sector
  labels ≤ 12 characters; entity labels ≤ 32 (detail goes in the summary).
- **No raw URLs or long paths in visible text.** Strip links, cut tokens over 28
  characters (`scripts/very/long/path.py…`). The engine also sets `overflow-wrap:
  anywhere` on rails and cards as a safety net.
- `mission-control validate` and `render` return `warnings` for all of the above.

## Diagrams (Archify)

- **Fit desktop readability first.** At the presenter width, a viewBox much wider than
  about 1,340 px projects text below 6 px and fails delivery. Four columns of about 200 px,
  with gaps of about 80 px, fit. Drop a column before shrinking copy.
- **Straight edges between aligned rows and columns.** Diagonal or crossing routes fail the
  clean-flow checks. Move a node rather than fighting the router. Fix label collisions with `labelAt`.
- **Chapter labels are short** (`1 Arrive`, `2 Recall`). Notes are 140 characters or fewer.
- **Wrapper templates are offline.** `presenter|story|embed|minimal` strip the upstream
  Google Fonts link and give SVG nodes a visible keyboard focus. `full` stays byte-identical.
- **No `sources` through the wrapper.** Source evidence needs `--repo-root`, which the
  wrapper deliberately does not forward. Put the file name in `tag`, or use Archify directly.

## Composition

- **Every screen has a way home.** When several renderers make one product, the host serves them
  with one shared top strip (Home + every screen, current one marked). Embedded iframes skip it.
- **The home page connects the dots.** Lead with the end-to-end flow (each step live, coloured by
  status, clickable to its screen), then insights (trend, work by stage, recent activity), then
  screen cards. Panels align to the top so a short chart never leaves dead space.

- **One page, several renderers.** A short host page (title, one-line lede, anchor pills)
  embeds the diagram (`story` template) and the data story in same-origin iframes and
  sizes the story to its content. Each embedded artifact still passes `design-check` on
  its own.
- **Look at the screenshots.** Passing the gate is necessary, not sufficient. Review
  desktop and phone shots in both themes before calling it done.
- **No filler labels.** Brand subtitles like "Decision support" say nothing; the screen title is enough.
- **Every press answers.** Pressing a card, station or dot glows what was pressed and what it points to (card -> its stage or failed runs on the flow line), keeps that target outlined until the next press, and buzzes once on Android. Reduced motion gets a steady outline.
- **Missing is not zero on the flow line.** A stage no run has reached says "no run yet / never reached", not "0.0 min".

## Motion timing (2026-11, from the herdr.dev study)

Entrances are 0.35s for small items, 0.5s for panes and 0.6s for layout changes. Each one fades with a 6–24px slide, using `cubic-bezier(.2,.8,.2,1)` everywhere. Ambient loops are slow (wall columns 18–26 px/s), pause on hover or focus, and stop under reduced motion. Status motion: a spinner means working, a small jump means it needs you, and a slow bob means idle.

- **Briefings lead with a brief strip, not the orbit.** Recording warnings, "before 9:00" actions, talking points and the one ask go in `brief` above the cockpit; the orbit is for drilling in. Canvas sector labels get a background halo and are clamped/shortened so they never clip the canvas edge; watcher chips are clamped on-canvas at 100%. On phones the top bar wraps (search on its own row) instead of crushing buttons into vertical text.

## Scrollbars and the Ask pane

- **Scrollbars follow the theme.** Each theme sets `color-scheme` (dark/light) and every scroll region (page, rails, worklist, detail sheet, Ask log) uses `scrollbar-width: thin` + `scrollbar-color` from the `--mc-scroll-*` tokens (derived from `--mc-faint`/`--mc-surface`), with `::-webkit-scrollbar` fallbacks. A white OS scrollbar on a dark page reads as broken. Verify with a screenshot of a scrolled list in both themes.
- **Ask is docked, never blocking.** Right dock (pushes the cockpit at >=1280px, overlays below), bottom sheet on phones, under the detail sheet's z-index. It shows a visible Thinking… state with seconds, the answer as sanitized markdown (everything escaped, only http(s) and repo-relative links; relative links open read-only via `/src`), source chips and the tools it used. "Ask about selected item" asks about whatever the map/list has selected.
- **Opened as a file, Ask is off, not broken.** The pane stays, inputs are disabled and one line says how to start `creator.py mission-control serve`.
