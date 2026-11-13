# Learning a technique from a video (before you build)

When the task is "watch this and learn how they do it", the deliverable is a
reusable method — and a transcript-only read will silently miss most of it.

## Rule

> **If a video's SUBJECT is what appears on screen, transcript alone is an
> incomplete read. Sample frames.**

Covers design/UI tool walkthroughs, editing workflows, product demos, dashboards,
charts, games. The narrator describes *intent*; the screen carries the *facts*.

Real miss, caught in review: a 16-minute video about an AI motion-graphics tool was
written up from transcript alone. The frame pass afterwards surfaced material the
narration never stated —

- generated files were React `.jsx` scene components, not the flat HTML the
  narrator said out loud (a load-bearing detail, and the summary was wrong on it)
- the tool's tweaks panel had a **talking-head safe-zone guides overlay** that
  solved the exact problem the narrator complained about later
- timeline scenes carried printed **names and durations** — which is *why*
  addressing a revision by section name works
- a full feature spec of his custom editor plugin was readable off the panel

The reviewer's challenge was simply "have you learned the visuals?" — treat that class of
question as a real defect report, not a clarification.

## Procedure

```bash
# 1. get it locally (720p is plenty for reading UI)
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" -o "ID.%(ext)s" "URL"

# 2. sample — ~39 frames for a 16-min talky video
ffmpeg -loglevel error -i ID.webm \
  -vf "fps=1/25,scale=960:-2,setparams=range=tv" \
  -pix_fmt yuvj420p -q:v 4 frames/g%03d.jpg -y

# 3. verify frames actually landed
find frames -size -2k | wc -l    # expect 0
```

Use scene detection (`-vf "select='gt(scene,0.3)'"`) instead when the video is
mostly hard cuts between distinct screens.

Then run the interesting frames through a vision model and **merge with the transcript** —
the write-up should reflect both.

### Pitfall — VP9 full-range YUV breaks the mjpeg encoder

yt-dlp `.webm` downloads are often full-range YUV. A plain
`ffmpeg -i in.webm -frames:v 1 -q:v 3 out.jpg` fails with:

```
Non full-range YUV is non-standard ...
ff_frame_thread_encoder_init failed
Nothing was written into output file
```

ffmpeg exits 0 on the *loop*, so this hides unless you count the outputs. Include
`setparams=range=tv` in the filter chain and `-pix_fmt yuvj420p` from the start
(`-strict unofficial` also works).

## Write-up shape

Put the spoken method in SKILL.md; put the observed-only visual detail in a
`references/` file and link it from SKILL.md. State explicitly which claims came
from the transcript and which from frames — it makes the write-up auditable when
a detail later turns out wrong.
