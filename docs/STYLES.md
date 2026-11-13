# Style library and design gate

Two pieces, added together:

1. `creator.py style list|show` — 84 vendored DESIGN.md brand analyses from
   [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
   (MIT, pinned in `integrations/design-md-lock.json`). 74 carry machine-readable
   tokens; the other 10 are prose-only and are listed as `unsupported`, never guessed.
2. `creator.py design-check --input page.html [--shots DIR] [--report FILE]` — a
   real-browser quality gate (our own code, tiers inspired by Nutlope/hallmark).

## Using a style

```bash
python3.13 creator.py style list
python3.13 creator.py mission-control render --input spec.json --output out.html --style linear.app
python3.13 creator.py mission-control render --input spec.json --output out.html --style stripe --theme dark
python3.13 creator.py design-check --input out.html --shots out-shots
```

Opening theme: `--theme` > the style's native mode (dark canvas → dark) > spec.
Without `--style`, Mission Control uses its native palette, now contrast-finalized.

## What a style changes (and what it does not)

- Changes: background/panel/raised surfaces, ink/muted/faint text, borders, accent,
  font stack, mono stack, corner radius — in CSS **and** in the canvas palette.
- Keeps: severity and watcher colours (critical/concerning/at-risk/stable, model/human/
  system). Domain meaning outranks brand. Only their lightness moves for contrast.
- Brand fonts are not bundled. The brand family is listed first; the system stack is the
  fallback, so the artifact stays offline. Expect system fonts on machines without them.
- It is a palette/type re-skin. Layout and density stay the same; structurally different
  concepts are a separate (Phase 2) capability.

Every text role is pushed to WCAG AA (4.5:1, ink 7:1) on panel, surface, raised, bg and
accent/severity tints. `tests/test_styles.py` asserts this for every supported style.

## Gate tiers

- **Floor (exit 1):** any visible DOM text below WCAG AA (both themes, desktop 1440 and
  mobile 390), sideways page scroll, page errors, network requests, invisible keyboard focus.
- **Reflex (reported):** AI-look tells — tracked-uppercase label count, gradient text,
  emoji used as button icons, eyebrow labels above headings. Overrule with a stated reason.
- **Finish (reported):** clipped text in overflow-hidden containers.

Limits: canvas pixels are not contrast-checked (only DOM text); backgrounds drawn by
images are reported as `unknownBackground`, not passed. Passing the gate is not a visual
review — still look at the screenshots.

Measured on `examples/mission-control/finops-governance.mission.json` (2026-11-06): the
previous template failed Floor (dark: approve button 2.41:1; light: 19 elements). Native
and the linear.app / stripe / claude / nvidia / vercel styles now pass Floor at both widths
and themes.

## Built-in `noir`

`noir` is a restrained developer-product look studied from herdr.dev: near-black, white and greys, no brand hue, hierarchy carried by brightness, Geist and JetBrains Mono (falling back to system fonts), and a near-white accent so the primary action is the brightest thing on screen. It is listed with `builtin: true` in `style list` and is the default for `creator.py wall`.
