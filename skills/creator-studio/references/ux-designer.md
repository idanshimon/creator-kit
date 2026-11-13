# Screenshot-grounded UX/UI designer

Run from the repo root with Python 3.13:

`python3.13 creator.py design-review --model RESOURCE/DEPLOYMENT --brief brief.txt --images screen1.jpg screen2.png --output new-review.json --allow-cloud`

Discover inventory first. Supply explicit local synthetic/authorized screenshots, one to three PNG/JPEGs under4MiB each; resize without replacing original images. The agent uses specialized UX/UI instructions, actual Responses image inputs, bounded brief/output and `store:false`. It returns two named light/dark portable-hex palette alternatives, concrete critique, material/lighting/interaction recommendations and verification steps. It records actual returned model, usage and screenshot hashes. It does not execute generated code, edit applications or deploy.

Reject incomplete responses; reasoning-heavy models can exhaust output before emitting a review. Low reasoning effort keeps a bounded review useful. Actual successful inference, not a catalog listing, establishes screenshot-model compatibility.

Validate domain semantics before applying designs. Calculate text contrast separately: a recommended marker colour can be acceptable at3:1 but fail small-text4.5:1. Lighting/fog/bloom can turn correct amber/orange into brown. Prefer neutral scene geometry with crisp unlit semantic caps/rims and readable status labels instead of random hue changes or fake stage gradients.

Inspect screenshots after browser tests, not just material token assertions. Reserve camera viewport space for phone overlay cards; do not hide map targets beneath them. Reposition selected satellite labels away from decorative agent centres, keep physical font sizes stable and restore overview when selection clears. Preserve zoom/theme/selection/approval state. Keep cloud consent explicit and Entra credentials in memory.

The current implementation is in `creator_tools/designer.py`, with CLI wiring in `creator.py` and tests in `tests/test_designer.py`. Keep real reviews under local `productions/`; inspect provenance rather than quoting historical token totals.
