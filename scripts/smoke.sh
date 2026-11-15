#!/usr/bin/env bash
# End-to-end proof that the kit works on this machine: free local narration (Kokoro)
# + an animated GSAP title card, recorded to MP4 and muxed. No API keys, no cloud.
#
#   scripts/smoke.sh [output-dir]     default: productions/smoke-<timestamp>
#
# Passes only if every renderer produces its output (motion, diagram, mission-control,
# pipeline-control, data-story, prompt-crawler) AND the final MP4 has an h264 video
# stream, an aac audio stream and a duration that matches the narration. Each failure
# names the fix instead of a stack trace.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PY:-$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)}"
OUT="${1:-productions/smoke-$(date +%Y%m%d-%H%M%S)}"
[ -e "$OUT" ] && { echo "Output exists: $OUT (pick a new one)"; exit 1; }
mkdir -p "$OUT"

FAILS=0
check() { # check <label> <fix hint> -- <command...>
  local label="$1" hint="$2"; shift 3
  if "$@" >"$OUT/logs/$label.log" 2>&1; then printf '    \033[32mok\033[0m   %s\n' "$label"
  else printf '    \033[31mFAIL\033[0m %s  -> %s  (log: %s)\n' "$label" "$hint" "$OUT/logs/$label.log"; FAILS=$((FAILS+1)); fi
}
mkdir -p "$OUT/logs"

echo "==> 0/5 preflight"
check gsap-runtime    "scripts/bootstrap.sh --minimal" -- "$PY" creator.py motion doctor
check archify         "scripts/bootstrap.sh --minimal" -- "$PY" creator.py diagram doctor
check kokoro-runtime  "scripts/bootstrap.sh (installs OpenMontage venv)" -- OpenMontage/.venv/bin/python -c "import soundfile, kokoro_onnx"
check chrome          "install Google Chrome" -- "$PY" -c "import sys; from creator_tools import showcase; sys.exit(0 if showcase.find_chrome() else 1)"

echo "==> 1/5 every renderer -> HTML"
R="$OUT/renderers"; mkdir -p "$R"
check diagram          "see docs/DIAGRAMS.md"          -- "$PY" creator.py diagram render --input examples/diagrams/creator-kit.architecture.json --output "$R/diagram.html"
check mission-control  "see docs/MISSION-CONTROL.md"   -- "$PY" creator.py mission-control render --input examples/mission-control/finops-governance.mission.json --output "$R/mission.html"
check pipeline-control "see docs/PIPELINE-CONTROL.md"  -- "$PY" creator.py pipeline-control render --input examples/pipeline-control/checkout-service.pipeline.json --output "$R/pipeline.html"
check data-story       "see docs/DATA-STORIES.md"      -- "$PY" creator.py data-story render --input examples/data-story/synthetic-workshop.json --output "$R/story.html"
check prompt-crawler   "see docs/SHOWCASE.md"          -- "$PY" creator.py crawl --input skills/video-production/SKILL.md --output "$R/crawl"
for f in diagram.html mission.html pipeline.html story.html crawl/viewer.html; do
  [ -s "$R/$f" ] || { echo "    FAIL $R/$f missing or empty"; FAILS=$((FAILS+1)); }
done
if [ "$FAILS" -gt 0 ]; then echo; echo "FAIL: $FAILS check(s) above. Fix them, then re-run scripts/smoke.sh"; exit 1; fi

cat > "$OUT/SCRIPT.md" <<'EOF'
## Welcome (Frame 1)

    This is Creator Kit. If you can hear this, narration and rendering both work.
EOF

echo "==> 2/5 narrate (kokoro, local)"
"$PY" creator.py narrate --engine kokoro --script "$OUT/SCRIPT.md" --output "$OUT/narration" >/dev/null
DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/narration/narration.wav")"
SECS="$("$PY" -c "import math,sys;print(max(4, math.ceil(float(sys.argv[1]))+1))" "$DUR")"
echo "    narration ${DUR}s"

echo "==> 3/5 motion title card (GSAP, offline)"
"$PY" creator.py motion create --output "$OUT/title" --title "Creator Kit" --subtitle "Narration + motion + render, all local" >/dev/null

echo "==> 4/5 record HTML -> MP4 (${SECS}s, frame-exact)"
"$PY" creator.py showcase --input "$OUT/title/index.html?render=1" --output "$OUT/silent.mp4" \
  --width 1280 --height 720 --fps 24 --seconds "$SECS" >/dev/null

echo "==> 5/5 mux narration"
ffmpeg -v error -i "$OUT/silent.mp4" -i "$OUT/narration/narration.wav" \
  -c:v copy -c:a aac -b:a 160k -shortest "$OUT/smoke.mp4"

STREAMS="$(ffprobe -v error -show_entries stream=codec_name -of csv=p=0 "$OUT/smoke.mp4" | sort | tr '\n' ' ')"
FINAL="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/smoke.mp4")"
echo "    streams: $STREAMS  duration: ${FINAL}s"
case "$STREAMS" in *aac*h264*) ;; *) echo "FAIL: expected h264 + aac"; exit 1 ;; esac
"$PY" -c "import sys; a,b=float(sys.argv[1]),float(sys.argv[2]); sys.exit(0 if abs(a-b) < 1.5 else 1)" "$FINAL" "$DUR" \
  || { echo "FAIL: video length ${FINAL}s does not match narration ${DUR}s"; exit 1; }
ffmpeg -v error -ss 1 -i "$OUT/smoke.mp4" -frames:v 1 "$OUT/frame-1s.png"
echo
echo "PASS: $OUT/smoke.mp4"
echo "Open it and listen; also look at $OUT/frame-1s.png. Structure checks do not prove it looks or sounds right."
