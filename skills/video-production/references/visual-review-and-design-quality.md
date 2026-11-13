# Reviewing a finished video — the defects lint never catches

A render can pass `npx hyperframes lint`, `check`, and `ffprobe` and still be
visually bad. Those gates prove the file is *valid*, not that it's *good*. This
file is the visual review pass.

## Rule: pull frames from the MP4 and LOOK at them

Sample every scene, not just one or two:

```bash
for t in 2 8 14 20 26 32 38 44 50 56; do
  ffmpeg -loglevel error -ss $t -i renders/video.mp4 -frames:v 1 \
    -vf scale=960:-2 /tmp/rev/f$t.jpg -y
done
```

Then vision-analyze each. Also sample **just after each scene boundary** and
**near the very end** — entrance stagger and late reveals fail there specifically
(see the sync-durations pitfall in SKILL.md).

Reviewers who go frame-by-frame find real bugs. Never declare done on
lint-clean + ffprobe alone.

## Defects found this way in a real shipped render (a v1 clinical explainer)

1. **Dead space — the dominant failure.** Multiple frames were a headline in the
   top-left corner with ~70% of the canvas empty. A "risk assessment" frame was
   two words and a rule line on a blank field. An architecture frame showed one
   dot and a line trailing off-screen.
   → **Every frame must occupy the canvas.** If a scene is one headline, it is
   under-designed; add the supporting structure that earns the screen.
2. **Overlapping text in the closing frame.** Two headline lines rendered on top
   of each other, the second half-faded across the first. Shipped that way
   because nobody looked at t=56.
   → Always sample the final 2-3 seconds.
3. **A "three tiers" scene that never showed three tiers** at the sampled moment
   — the visual didn't deliver what the narration promised.
   → Check that each frame *illustrates its own narration line*. Read the
   SCRIPT.md line and the frame side by side.
4. **Palette mismatch to subject.** A cream/ivory ground read soft and academic
   for a clinical cardiology topic.
   → Pick the register from the subject: clinical/serious → deep navy ground with
   a meaningful accent set, not a warm neutral.

## What "good" looked like on the rebuild

- **Every color carries meaning**, none decorate: ECG red = the heartbeat/hero,
  cyan = data/FHIR, green = confirmed, amber = elevated/attention, violet =
  human-in-the-loop. A reviewer can decode the frame without the narration.
- **Information design over title cards.** "Three months behind" became three
  growing bars (Care → Abstraction → Report, ~90 days). "Three tiers" became
  three latency rows (`<1s` / `~60s` / `nightly`) each labeled with the decision
  it supports. A risk score became a sweeping gauge with a counting number beside
  the three weighted criteria (+18 / +24 / +16) that produced it.
- **Typographic contrast** is what stops output looking AI-generated: heavy
  geometric sans for structure, a **serif italic** reserved for the emotional
  beats ("honestly", "Not one firehose", "Show your work"), and small
  wide-letterspaced uppercase for labels/axis captions.
- **Show the proof, not the claim.** The extraction scene put the source chart
  and the extracted field side by side with the confidence score and the verbatim
  quote visible — the screen demonstrates "shows its work" instead of asserting it.

## Anti-patterns

- A frame whose entire content is a headline + rule line
- Content clustered in one corner with an empty majority
- Color used decoratively (a palette that would survive being shuffled)
- On-screen copy that contradicts or under-delivers its narration line
- Declaring done without sampling the last 3 seconds

## Closing frames — end on value

End on **value, not disclaimers**. A close built on POC caveats was rejected
("Synthetic data only", "Read-first · write Phase 2"). For client/executive
audiences the closing chips and line mirror what the video PROVED —
e.g. faster signal · proof on every value · human in the loop.
