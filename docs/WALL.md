# Living wall (`creator.py wall`)

A hero section built from past work: columns of 16:10 tiles drift up and down in opposite directions. A shade keeps the headline readable, hovering over or focusing a column pauses it, and clicking a tile opens a blurred lightbox. The pattern was studied from herdr.dev (2026-11).

```bash
python3.13 creator.py wall --input DIR_OF_IMAGES_OR_MP4 --output productions/NEW \
  --title "Every frame here | was made by asking." --subtitle "..." \
  --cta-label "Open the studio" --cta-href "#studio" [--stat 129:layouts] [--style noir] [--theme light] [--columns 4]
python3.13 creator.py showcase --input productions/NEW/index.html --output wall.mp4 --seconds 6
python3.13 creator.py design-check --input productions/NEW/index.html --shots shots/
```

- `|` in `--title` sets the break. The text after it is dimmed, so brightness rather than colour carries the hierarchy.
- The default stat is the real tile count. Pass `--stat` only with real numbers.
- Output is offline: assets are copied in, nothing is fetched, and existing output is never overwritten.
- `window.__ready/__advance` give frame-exact recording, and reduced motion stops the drift.
- `.hero` showing as "clipped" in design-check is expected, because the wall overflows on purpose.
- Tiles repeat when there are only a few per column. Use 12 or more items for a wall that doesn't visibly repeat.
- Pick it for developer, public and social audiences. Don't use it for an exec read-out (see the audience rules in the skill).
