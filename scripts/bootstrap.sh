#!/usr/bin/env bash
# Creator Kit bootstrap: installs everything at the versions pinned in upstream-lock.json.
#
#   scripts/bootstrap.sh            full install (Studio, HyperFrames, OpenMontage, Archify)
#   scripts/bootstrap.sh --minimal  Studio editor + CLI only (no video renderer, no voices)
#   scripts/bootstrap.sh --check    report what is installed; change nothing
#
# Safe to re-run. It never resets, upgrades or deletes an existing checkout; it only
# fills in what is missing. Network access is required for the first run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="full"
case "${1:-}" in
  --minimal) MODE="minimal" ;;
  --check)   MODE="check" ;;
  "")        ;;
  -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
  *) echo "unknown option: $1 (use --minimal, --check or --help)"; exit 2 ;;
esac

ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
miss() { printf '  \033[31mmissing\033[0m %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Unset variables that commonly break npm/node installs when inherited from a parent tool.
NPM="env -u NODE_ENV -u NODE_PATH -u NODE_OPTIONS npm"

# ---------------------------------------------------------------- prerequisites
step "Prerequisites"
FAIL=0
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] && ok "python  $($PY --version 2>&1 | awk '{print $2}') ($PY)" || { miss "python 3.10+  (macOS: brew install python@3.13)"; FAIL=1; }
have git && ok "git     $(git --version | awk '{print $3}')" || { miss "git"; FAIL=1; }
if have node && node -e 'process.exit(+process.versions.node.split(".")[0] >= 18 ? 0 : 1)'; then
  ok "node    $(node --version)"
else miss "node 18+  (macOS: brew install node)"; FAIL=1; fi
have npm && ok "npm     $(npm --version)" || { miss "npm"; FAIL=1; }
if have ffmpeg && have ffprobe; then
  ok "ffmpeg  $(ffmpeg -version | head -1 | awk '{print $3}')"
  ffmpeg -hide_banner -filters 2>/dev/null | grep -qE ' subtitles ' \
    || echo "        note: this ffmpeg has no libass ('subtitles' filter); burned-in captions will not work"
else miss "ffmpeg + ffprobe  (macOS: brew install ffmpeg)"; FAIL=1; fi
if [ "$MODE" != "minimal" ]; then
  have bun && ok "bun     $(bun --version)" || { miss "bun  (curl -fsSL https://bun.sh/install | bash), needed by HyperFrames"; FAIL=1; }
fi
CHROME=""
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "$(command -v google-chrome 2>/dev/null)" "$(command -v chromium 2>/dev/null)"; do
  [ -n "$c" ] && [ -x "$c" ] && { CHROME="$c"; break; }
done
have uv && ok "uv      $(uv --version | awk '{print $2}') (local Qwen3/Chatterbox voices)" \
  || echo "  warn    uv not found; optional, needed only for --engine qwen3|chatterbox (brew install uv)"
[ -n "$CHROME" ] && ok "chrome  (used to record HTML to MP4 and for design checks)" \
  || echo "  warn    Google Chrome not found; showcase/design-check recording needs it"

if [ "$FAIL" = 1 ]; then
  echo; echo "Install the missing tools above, then re-run scripts/bootstrap.sh"; exit 1
fi

lock() { # lock <path> <field>
  "$PY" - "$1" "$2" <<'EOF'
import json, sys
for d in json.load(open("upstream-lock.json"))["dependencies"]:
    if d["path"] == sys.argv[1]:
        print(d.get(sys.argv[2], "")); break
EOF
}

clone_pinned() { # clone_pinned <dir>
  local dir="$1" url rev
  url="$(lock "$dir" repository)"; rev="$(lock "$dir" revision)"
  if [ -d "$dir/.git" ]; then
    local head; head="$(git -C "$dir" rev-parse HEAD)"
    [ "$head" = "$rev" ] && ok "$dir at pinned $rev" \
      || echo "  warn    $dir is at $head, lock says $rev (left as is; never reset automatically)"
    return
  fi
  [ "$MODE" = "check" ] && { miss "$dir (not cloned)"; return; }
  echo "  cloning $dir @ ${rev:0:10}"
  GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --filter=blob:none --no-checkout "$url" "$dir"
  GIT_LFS_SKIP_SMUDGE=1 git -C "$dir" checkout --quiet --detach "$rev"
  ok "$dir at pinned $rev"
}

# ---------------------------------------------------------------- local config
step "Local config"
if [ -f .env ]; then ok ".env exists"
elif [ "$MODE" != "check" ]; then cp .env.example .env; ok ".env created from .env.example (all optional; fill in later)"
else miss ".env (optional)"; fi
mkdir -p productions

# ---------------------------------------------------------------- Studio UI
step "Studio editor (studio-ui)"
if [ "$MODE" = "check" ]; then
  [ -f studio-ui/dist/index.html ] && ok "studio-ui built" || miss "studio-ui/dist (not built)"
else
  (cd studio-ui && $NPM ci --no-audit --no-fund && $NPM run build)
  ok "studio-ui built -> studio-ui/dist"
fi

if [ "$MODE" = "minimal" ]; then
  step "Done (minimal). Start the editor: $PY creator.py studio  ->  http://127.0.0.1:4318"
  exit 0
fi

# ---------------------------------------------------------------- HyperFrames
step "HyperFrames (HTML -> MP4 renderer + video skills)"
clone_pinned hyperframes
if [ "$MODE" != "check" ]; then
  (cd hyperframes && bun install && bun run build)
  ok "hyperframes built"
fi

# ---------------------------------------------------------------- OpenMontage
step "OpenMontage (pipelines + Python env used for local Kokoro voice)"
clone_pinned OpenMontage
if [ "$MODE" != "check" ]; then
  [ -x OpenMontage/.venv/bin/python ] || "$PY" -m venv OpenMontage/.venv
  OpenMontage/.venv/bin/python -m pip install --quiet --upgrade pip
  OpenMontage/.venv/bin/python -m pip install --quiet -r OpenMontage/requirements.txt
  OpenMontage/.venv/bin/python -m pip install --quiet kokoro-onnx soundfile
  [ -f OpenMontage/.env ] || cp OpenMontage/.env.example OpenMontage/.env
  ok "OpenMontage venv ready"
elif [ -x OpenMontage/.venv/bin/python ]; then ok "OpenMontage venv"; else miss "OpenMontage/.venv"; fi

# ---------------------------------------------------------------- Archify
step "Archify (interactive architecture diagrams)"
if [ -d archify ]; then ok "archify installed"
elif [ "$MODE" = "check" ]; then miss "archify"
else
  URL="$("$PY" -c 'import json;print(json.load(open("integrations/archify-lock.json"))["url"])')"
  ZIP="$(mktemp -d)/archify.zip"
  curl -fsSL --max-time 180 "$URL" -o "$ZIP"
  "$PY" creator.py diagram install --archive "$ZIP" >/dev/null   # verifies the pinned sha256
  ok "archify installed from checksum-pinned release"
fi

# ---------------------------------------------------------------- verify
step "Verify"
"$PY" creator.py motion doctor >/dev/null && ok "motion doctor (GSAP runtime matches lock)" || echo "  warn    motion doctor failed"
"$PY" creator.py diagram doctor >/dev/null && ok "diagram doctor (Archify integrity)" || echo "  warn    diagram doctor failed"
env -u PYTHONPATH -u PYTHONHOME "$PY" -m unittest discover -s tests -q >/dev/null 2>&1 \
  && ok "unit tests pass" || echo "  warn    unit tests failed: run  $PY -m unittest discover -s tests -v"

cat <<EOF

==> Setup finished. Next:
    scripts/smoke.sh                 render a short narrated test video (proves the whole chain)
    $PY creator.py studio            browser editor at http://127.0.0.1:4318
    Read AGENTS.md, then ask your agent for a video.
EOF
