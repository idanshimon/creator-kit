"""Deterministic, sandboxed video editing backend.

Pure stdlib. Shells out ONLY to the local ffmpeg/ffprobe binaries with
fully-quoted argument arrays (never a shell string, never a model-supplied
filter/command). Given an EDIT_PLAN (a plain dict, typically model-authored)
it validates it hard, then normalizes + concatenates the requested clip
windows into a single deterministic H.264/AAC MP4.

Public API
----------
probe(path) -> {"duration","width","height","has_audio", ...}
validate_plan(plan) -> normalized plan dict
render(plan, output) -> {"output","duration","width","height","clips", ...}

EDIT_PLAN schema (version == 1)
-------------------------------
{
  "version": 1,
  "width": <positive even int <= 3840>,
  "height": <positive even int <= 3840>,
  "clips": [{"path": <absolute existing file>,
             "start": <finite float >= 0>,
             "end":   <finite float > start, <= source duration>}],  # 1..100
  "fit": "contain" | "cover",   # default "contain"
  "mute": <bool>,               # default False
  "volume": <finite float 0..2>,# default 1.0
  "subtitles": <absolute .srt/.vtt path>   # optional
}

Security posture: no shell, no URL/pipe/playlist inputs, restricted ffmpeg
protocol whitelist (file only), output must not exist and must not equal any
input, total output duration capped, atomic temp write, provenance sidecar.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time

__all__ = ["EditPlanError", "probe", "analyze_clip", "retime_subtitles",
           "validate_plan", "render"]

MAX_DIM = 3840
MAX_CLIPS = 100
MAX_TOTAL_DURATION = 600.0  # seconds; guard against accidental giant jobs
_SUBTITLE_EXTS = (".srt", ".vtt")
_MEDIA_EXTS = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".ts", ".wav", ".mp3", ".m4a")
_DEMUXERS = "mov,matroska,webm,avi,mpeg,mpegts,wav,mp3"
_PROTO_WHITELIST = "file"

_TOP_KEYS = {"version", "width", "height", "clips", "fit", "mute",
             "volume", "subtitles", "retime_subtitles", "burn_subtitles",
             "bgm", "bgm_volume", "bgm_duck", "fade_in", "fade_out"}
_CLIP_KEYS = {"path", "start", "end", "speed", "volume", "mute"}

MIN_SPEED = 0.25
MAX_SPEED = 4.0
_AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")


class EditPlanError(ValueError):
    """Raised for any invalid plan, unsafe input, or refused render."""


# --------------------------------------------------------------------------- #
# binaries
# --------------------------------------------------------------------------- #
def _ffmpeg():
    b = shutil.which("ffmpeg")
    if not b:
        raise EditPlanError("ffmpeg not found on PATH")
    return b


def _ffprobe():
    b = shutil.which("ffprobe")
    if not b:
        raise EditPlanError("ffprobe not found on PATH")
    return b


def _ffmpeg_version():
    try:
        out = subprocess.run([_ffmpeg(), "-version"], check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL).stdout.decode()
        return out.splitlines()[0].strip()
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- #
# validation helpers
# --------------------------------------------------------------------------- #
def _finite_number(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EditPlanError("%s must be a number" % name)
    f = float(v)
    if not math.isfinite(f):
        raise EditPlanError("%s must be finite" % name)
    return f


def _safe_local_path(p, name):
    if not isinstance(p, str) or not p:
        raise EditPlanError("%s must be a non-empty string" % name)
    # reject URLs / protocol prefixes / pipes / globs
    lowered = p.lower()
    for bad in ("://", "|", "\n", "\r"):
        if bad in lowered:
            raise EditPlanError("%s contains an unsafe token" % name)
    if lowered.split(":", 1)[0] in ("http", "https", "ftp", "rtmp", "rtsp",
                                    "pipe", "data", "concat", "subfile",
                                    "tcp", "udp"):
        raise EditPlanError("%s uses a disallowed protocol" % name)
    if not os.path.isabs(p):
        raise EditPlanError("%s must be an absolute path" % name)
    if not os.path.isfile(p):
        raise EditPlanError("%s does not exist" % name)
    return os.path.realpath(p)


def _even_dim(v, name):
    if isinstance(v, bool) or not isinstance(v, int):
        raise EditPlanError("%s must be an integer" % name)
    if v <= 0 or v > MAX_DIM:
        raise EditPlanError("%s out of range (1..%d)" % (name, MAX_DIM))
    if v % 2 != 0:
        raise EditPlanError("%s must be even" % name)
    return v


# --------------------------------------------------------------------------- #
# probe
# --------------------------------------------------------------------------- #
def probe(path):
    """Return metadata for a local media file via ffprobe."""
    real = _safe_local_path(path, "path")
    if os.path.splitext(real)[1].lower() not in _MEDIA_EXTS:
        raise EditPlanError("Unsupported local media container; playlists are not accepted")
    args = [_ffprobe(), "-v", "error", "-protocol_whitelist", _PROTO_WHITELIST,
            "-format_whitelist", _DEMUXERS,
            "-show_entries", "stream=codec_type,width,height:format=duration",
            "-of", "json", real]
    try:
        out = subprocess.run(args, check=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=60).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise EditPlanError("Cannot probe media: invalid/unsupported container or timeout") from None
    data = json.loads(out.decode())
    width = height = 0
    has_audio = False
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not width:
            width = int(s.get("width") or 0)
            height = int(s.get("height") or 0)
        if s.get("codec_type") == "audio":
            has_audio = True
    duration = 0.0
    try:
        duration = float(data.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return {"path": real, "duration": duration, "width": width,
            "height": height, "has_audio": has_audio}


# --------------------------------------------------------------------------- #
# analyze_clip & retime_subtitles
# --------------------------------------------------------------------------- #
_TIME_RE = re.compile(
    r"^(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{3})(.*)$"
)


def _parse_ts(h, m, s, ms):
    return int(h or 0) * 3600.0 + int(m) * 60.0 + int(s) + int(ms) / 1000.0


def _fmt_ts(sec, sep=","):
    ms_total = max(0, int(round(sec * 1000.0)))
    h, rem = divmod(ms_total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return "%02d:%02d:%02d%s%03d" % (h, m, s, sep, ms)


def parse_subtitle_cues(text):
    """Parse SRT or WebVTT text into [{'start': float, 'end': float, 'text': str}]."""
    cues = []
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    for block in blocks:
        lines = [ln.rstrip("\r") for ln in block.splitlines() if ln.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        ts_idx = None
        m = None
        for idx, ln in enumerate(lines[:3]):
            m = _TIME_RE.match(ln.strip())
            if m:
                ts_idx = idx
                break
        if m is None or ts_idx is None:
            continue
        g = m.groups()
        start = _parse_ts(g[0], g[1], g[2], g[3])
        end = _parse_ts(g[4], g[5], g[6], g[7])
        body = "\n".join(lines[ts_idx + 1:]).strip()
        if end > start and body:
            cues.append({"start": round(start, 3), "end": round(end, 3),
                         "text": body, "settings": (g[8] or "").strip()})
    return cues


def retime_subtitles(subtitle_text, clips, fmt="srt"):
    """Deterministically remap source-timed SRT/VTT cues onto the edited timeline.

    Each clip dict must have `start`, `end`, and optional `speed` (default 1.0).
    Cues overlapping `[clip.start, clip.end]` are clamped to the clip window,
    scaled by `1 / speed`, and shifted to that clip's cumulative timeline offset.
    """
    if fmt not in ("srt", "vtt"):
        raise EditPlanError("subtitle format must be 'srt' or 'vtt'")
    cues = parse_subtitle_cues(subtitle_text)
    remapped = []
    offset = 0.0
    for c in clips:
        c_start = float(c["start"])
        c_end = float(c["end"])
        speed = float(c.get("speed", 1.0))
        eff_dur = (c_end - c_start) / speed
        for cue in cues:
            ov_start = max(c_start, cue["start"])
            ov_end = min(c_end, cue["end"])
            if ov_end - ov_start >= 0.04:
                new_s = offset + (ov_start - c_start) / speed
                new_e = offset + (ov_end - c_start) / speed
                remapped.append({"start": new_s, "end": new_e,
                                 "text": cue["text"],
                                 "settings": cue.get("settings", "")})
        offset += eff_dur
    sep = "." if fmt == "vtt" else ","
    out_lines = ["WEBVTT\n"] if fmt == "vtt" else []
    for idx, cue in enumerate(remapped, 1):
        ts = "%s --> %s" % (_fmt_ts(cue["start"], sep), _fmt_ts(cue["end"], sep))
        if fmt == "vtt" and cue["settings"]:
            ts += " " + cue["settings"]
        if fmt == "srt":
            out_lines.append("%d\n%s\n%s" % (idx, ts, cue["text"]))
        else:
            out_lines.append("%s\n%s" % (ts, cue["text"]))
    return ("\n\n".join(out_lines) + "\n") if remapped else ("WEBVTT\n\n" if fmt == "vtt" else "")


def analyze_clip(path, silence_db=-35.0, min_silence=0.35, scene_threshold=0.3, srt_path=None):
    """Probe local media and extract deterministic silence intervals, scene cuts,
    and optional parsed SRT/VTT cues for content-aware edit planning."""
    meta = probe(path)
    real = meta["path"]
    silences = []
    if meta["has_audio"]:
        s_args = [_ffmpeg(), "-nostdin", "-hide_banner", "-protocol_whitelist", _PROTO_WHITELIST,
                  "-format_whitelist", _DEMUXERS, "-i", real, "-map", "0:a:0",
                  "-af", "silencedetect=noise=%.1fdB:d=%.3f" % (float(silence_db), float(min_silence)),
                  "-f", "null", "-"]
        proc = subprocess.run(s_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        cur_start = None
        for line in proc.stderr.decode(errors="replace").splitlines():
            if "silence_start:" in line:
                try:
                    cur_start = float(line.split("silence_start:")[-1].strip().split()[0])
                except ValueError:
                    cur_start = None
            elif "silence_end:" in line and cur_start is not None:
                try:
                    s_end = float(line.split("silence_end:")[-1].strip().split()[0])
                    if s_end > cur_start:
                        silences.append({"start": round(cur_start, 3), "end": round(s_end, 3)})
                except ValueError:
                    pass
                cur_start = None
    scenes = []
    if meta["width"] > 0 and meta["height"] > 0:
        v_args = [_ffmpeg(), "-nostdin", "-hide_banner", "-protocol_whitelist", _PROTO_WHITELIST,
                  "-format_whitelist", _DEMUXERS, "-i", real, "-map", "0:v:0",
                  "-vf", "select='gt(scene,%.3f)',showinfo" % float(scene_threshold),
                  "-f", "null", "-"]
        proc = subprocess.run(v_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        for line in proc.stderr.decode(errors="replace").splitlines():
            if "pts_time:" in line:
                try:
                    pts = float(line.split("pts_time:")[-1].strip().split()[0])
                    scenes.append(round(pts, 3))
                except ValueError:
                    pass
    transcript = []
    if srt_path is not None:
        sub_real = _safe_local_path(srt_path, "srt_path")
        if os.path.splitext(sub_real)[1].lower() not in _SUBTITLE_EXTS:
            raise EditPlanError("srt_path must be .srt or .vtt")
        with open(sub_real, "r", encoding="utf-8", errors="replace") as f:
            transcript = [{"start": c["start"], "end": c["end"], "text": c["text"]}
                          for c in parse_subtitle_cues(f.read())]
    return {**meta, "silences": silences, "scene_cuts": scenes, "transcript": transcript}


# --------------------------------------------------------------------------- #
# validate_plan
# --------------------------------------------------------------------------- #
def validate_plan(plan):
    """Validate and normalize an EDIT_PLAN. Raises EditPlanError on any fault."""
    if not isinstance(plan, dict):
        raise EditPlanError("plan must be a dict")
    unknown = set(plan) - _TOP_KEYS
    if unknown:
        raise EditPlanError("unknown plan keys: %s" % sorted(unknown))

    if type(plan.get("version")) is not int or plan.get("version") != 1:
        raise EditPlanError("unsupported plan version (need 1)")

    width = _even_dim(plan.get("width"), "width")
    height = _even_dim(plan.get("height"), "height")

    fit = plan.get("fit", "contain")
    if fit not in ("contain", "cover"):
        raise EditPlanError("fit must be 'contain' or 'cover'")

    mute = plan.get("mute", False)
    if not isinstance(mute, bool):
        raise EditPlanError("mute must be a bool")

    volume = _finite_number(plan.get("volume", 1.0), "volume")
    if not (0.0 <= volume <= 2.0):
        raise EditPlanError("volume must be in 0..2")

    raw_clips = plan.get("clips")
    if not isinstance(raw_clips, list) or not raw_clips:
        raise EditPlanError("clips must be a non-empty list")
    if len(raw_clips) > MAX_CLIPS:
        raise EditPlanError("too many clips (>%d)" % MAX_CLIPS)

    clips = []
    total = 0.0
    for i, c in enumerate(raw_clips):
        if not isinstance(c, dict):
            raise EditPlanError("clip %d must be a dict" % i)
        unk = set(c) - _CLIP_KEYS
        if unk:
            raise EditPlanError("clip %d unknown keys: %s" % (i, sorted(unk)))
        real = _safe_local_path(c.get("path"), "clip %d path" % i)
        start = _finite_number(c.get("start"), "clip %d start" % i)
        end = _finite_number(c.get("end"), "clip %d end" % i)
        if start < 0:
            raise EditPlanError("clip %d start must be >= 0" % i)
        if end <= start:
            raise EditPlanError("clip %d end must be > start" % i)

        speed = _finite_number(c.get("speed", 1.0), "clip %d speed" % i)
        if not (MIN_SPEED <= speed <= MAX_SPEED):
            raise EditPlanError(
                "clip %d speed must be in %.2f..%.2f" % (i, MIN_SPEED, MAX_SPEED))
        c_vol = _finite_number(c.get("volume", 1.0), "clip %d volume" % i)
        if not (0.0 <= c_vol <= 2.0):
            raise EditPlanError("clip %d volume must be in 0..2" % i)
        c_mute = c.get("mute", False)
        if not isinstance(c_mute, bool):
            raise EditPlanError("clip %d mute must be a bool" % i)

        meta = probe(real)
        src_dur = meta["duration"]
        if not math.isfinite(src_dur) or src_dur <= 0 or meta["width"] <= 0 or meta["height"] <= 0:
            raise EditPlanError("clip %d must have a video stream and finite positive duration" % i)
        if src_dur > 0 and end > src_dur + 0.05:
            raise EditPlanError(
                "clip %d end %.3f exceeds source duration %.3f"
                % (i, end, src_dur))
        eff_dur = (end - start) / speed
        total += eff_dur
        clips.append({"path": real, "start": start, "end": end,
                      "has_audio": meta["has_audio"], "speed": speed,
                      "volume": c_vol, "mute": c_mute,
                      "effective_duration": eff_dur})

    if total > MAX_TOTAL_DURATION:
        raise EditPlanError(
            "effective total duration %.1fs exceeds cap %.0fs"
            % (total, MAX_TOTAL_DURATION))

    fade_in = _finite_number(plan.get("fade_in", 0.0), "fade_in")
    fade_out = _finite_number(plan.get("fade_out", 0.0), "fade_out")
    if fade_in < 0 or fade_out < 0:
        raise EditPlanError("fade_in/fade_out must be >= 0")
    half = total / 2.0
    if fade_in > half + 1e-9 or fade_out > half + 1e-9:
        raise EditPlanError(
            "fade_in/fade_out must each be <= total_duration/2 (%.3fs)" % half)

    subtitles = plan.get("subtitles")
    if subtitles is not None:
        sub_real = _safe_local_path(subtitles, "subtitles")
        if os.path.splitext(sub_real)[1].lower() not in _SUBTITLE_EXTS:
            raise EditPlanError("subtitles must be .srt or .vtt")
        subtitles = sub_real

    retime_subs = plan.get("retime_subtitles", False)
    if not isinstance(retime_subs, bool):
        raise EditPlanError("retime_subtitles must be a bool")
    burn_subs = plan.get("burn_subtitles", False)
    if not isinstance(burn_subs, bool):
        raise EditPlanError("burn_subtitles must be a bool")
    if (retime_subs or burn_subs) and subtitles is None:
        raise EditPlanError("retime_subtitles/burn_subtitles require a subtitles path")

    bgm = plan.get("bgm")
    if bgm is not None:
        bgm_real = _safe_local_path(bgm, "bgm")
        if os.path.splitext(bgm_real)[1].lower() not in _AUDIO_EXTS:
            raise EditPlanError("bgm must be a supported audio/video file")
        bgm_meta = probe(bgm_real)
        if not bgm_meta["has_audio"] or bgm_meta["duration"] <= 0:
            raise EditPlanError("bgm must contain an audio stream with positive duration")
        bgm = bgm_real
    bgm_volume = _finite_number(plan.get("bgm_volume", 0.25), "bgm_volume")
    if not (0.0 <= bgm_volume <= 2.0):
        raise EditPlanError("bgm_volume must be in 0..2")
    bgm_duck = plan.get("bgm_duck", True)
    if not isinstance(bgm_duck, bool):
        raise EditPlanError("bgm_duck must be a bool")

    return {"version": 1, "width": width, "height": height, "fit": fit,
            "mute": mute, "volume": volume, "clips": clips,
            "subtitles": subtitles, "retime_subtitles": retime_subs,
            "burn_subtitles": burn_subs, "bgm": bgm,
            "bgm_volume": bgm_volume, "bgm_duck": bgm_duck,
            "total_duration": total,
            "fade_in": fade_in, "fade_out": fade_out}


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def _scale_filter(width, height, fit):
    if fit == "cover":
        scale = ("scale=%d:%d:force_original_aspect_ratio=increase:force_divisible_by=2,"
                 "crop=%d:%d" % (width, height, width, height))
    else:  # contain
        scale = ("scale=%d:%d:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                 "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black"
                 % (width, height, width, height))
    return scale


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _atempo_chain(speed):
    """Return a comma-joined atempo chain that multiplies to `speed`, each
    factor within ffmpeg's supported 0.5..2.0 range (pitch-preserving)."""
    factors = []
    remaining = speed
    while remaining > 2.0 + 1e-9:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join("atempo=%.6f" % f for f in factors)


def _draft_dims(width, height, max_dim=640):
    """Scale so the larger dimension is <= max_dim, preserve aspect, even.
    Never upscale."""
    longest = max(width, height)
    if longest <= max_dim:
        return width, height
    scale = max_dim / float(longest)
    w = int(round(width * scale))
    h = int(round(height * scale))
    w -= w % 2
    h -= h % 2
    return max(w, 2), max(h, 2)


def _escape_filter_path(path):
    """Escape a filesystem path for ffmpeg's subtitles=filename='...' filter."""
    s = path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")
    return s.replace("[", "\\[").replace("]", "\\]")


def render(plan, output, profile="final"):
    """Render a validated plan to `output` (MP4, H.264 + AAC). Atomic write.

    profile:
      "final" (default) — full plan dimensions, original encoder settings.
      "draft"           — output downscaled so its longest side is <= 640
                          (aspect preserved, dims even, never upscaled) and a
                          faster encoder preset, for quick preview.
    """
    if profile not in ("final", "draft"):
        raise EditPlanError("profile must be 'final' or 'draft'")
    norm = validate_plan(plan)

    if not isinstance(output, str) or not output:
        raise EditPlanError("output must be a non-empty string")
    if not os.path.isabs(output):
        output = os.path.abspath(output)
    if os.path.splitext(output)[1].lower() != ".mp4":
        raise EditPlanError("Output must have .mp4 extension")
    if os.path.lexists(output) or os.path.lexists(output + ".provenance.json"):
        raise EditPlanError("output already exists; refusing to overwrite")
    out_real_parent = os.path.realpath(os.path.dirname(output) or ".")
    os.makedirs(out_real_parent, exist_ok=True)
    for c in norm["clips"]:
        if os.path.realpath(c["path"]) == os.path.realpath(output):
            raise EditPlanError("output must not equal an input")
    if norm["bgm"] and os.path.realpath(norm["bgm"]) == os.path.realpath(output):
        raise EditPlanError("output must not equal bgm input")

    fit = norm["fit"]
    mute, volume = norm["mute"], norm["volume"]
    fade_in, fade_out = norm["fade_in"], norm["fade_out"]
    total_dur = norm["total_duration"]
    fps = 30

    if profile == "draft":
        width, height = _draft_dims(norm["width"], norm["height"], 640)
        preset = "ultrafast"
    else:
        width, height = norm["width"], norm["height"]
        preset = "veryfast"

    # Capture input hashes BEFORE render to detect mid-render changes.
    input_hashes_pre = [_sha256(c["path"]) for c in norm["clips"]]

    args = [_ffmpeg(), "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]
    filt = []
    concat_labels = []
    for i, c in enumerate(norm["clips"]):
        args += ["-protocol_whitelist", _PROTO_WHITELIST, "-format_whitelist", _DEMUXERS, "-i", c["path"]]

    n = len(norm["clips"])
    next_input_idx = n
    sub_input_idx = None
    bgm_input_idx = None
    tmp_sub_path = None

    effective_sub_path = norm["subtitles"]
    if effective_sub_path and norm["retime_subtitles"]:
        ext = os.path.splitext(effective_sub_path)[1].lower()
        fmt = "vtt" if ext == ".vtt" else "srt"
        with open(effective_sub_path, "r", encoding="utf-8", errors="replace") as sf:
            retimed_text = retime_subtitles(sf.read(), norm["clips"], fmt=fmt)
        sfd, tmp_sub_path = tempfile.mkstemp(suffix=ext, dir=out_real_parent)
        with os.fdopen(sfd, "w", encoding="utf-8") as tf:
            tf.write(retimed_text)
        effective_sub_path = tmp_sub_path

    if effective_sub_path:
        sub_input_idx = next_input_idx
        next_input_idx += 1
        args += ["-protocol_whitelist", _PROTO_WHITELIST, "-format_whitelist", "srt,webvtt", "-i", effective_sub_path]

    if norm["bgm"]:
        bgm_input_idx = next_input_idx
        next_input_idx += 1
        args += ["-protocol_whitelist", _PROTO_WHITELIST, "-format_whitelist", _DEMUXERS, "-stream_loop", "-1", "-i", norm["bgm"]]

    for i, c in enumerate(norm["clips"]):
        speed = c["speed"]
        eff_dur = c["effective_duration"]
        clip_mute = mute or c["mute"]
        clip_vol = volume * c["volume"]
        vlabel = "v%d" % i
        alabel = "a%d" % i
        # video: trim -> reset pts -> speed (setpts) -> fps -> scale/pad
        vf = ("[%d:v]trim=start=%.6f:end=%.6f,setpts=(PTS-STARTPTS)/%.6f,"
              "fps=%d,%s,setsar=1[%s]"
              % (i, c["start"], c["end"], speed, fps,
                 _scale_filter(width, height, fit), vlabel))
        filt.append(vf)
        if clip_mute or not c["has_audio"]:
            # synthesize silence of exact EFFECTIVE clip duration
            af = ("anullsrc=channel_layout=stereo:sample_rate=44100,"
                  "atrim=duration=%.6f,asetpts=PTS-STARTPTS[%s]"
                  % (eff_dur, alabel))
        else:
            af = ("[%d:a]atrim=start=%.6f:end=%.6f,asetpts=PTS-STARTPTS,"
                  "%s,volume=%.6f,"
                  "aformat=sample_rates=44100:channel_layouts=stereo,"
                  "apad,atrim=duration=%.6f[%s]"
                  % (i, c["start"], c["end"], _atempo_chain(speed), clip_vol,
                     eff_dur, alabel))
        filt.append(af)
        concat_labels.append("[%s][%s]" % (vlabel, alabel))

    filt.append("%sconcat=n=%d:v=1:a=1[vcat][acat]"
                % ("".join(concat_labels), n))

    vlast, alast = "vcat", "acat"
    if norm["bgm"] and bgm_input_idx is not None:
        filt.append(
            "[%d:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            "atrim=duration=%.6f,asetpts=PTS-STARTPTS,volume=%.6f[bgm_raw]"
            % (bgm_input_idx, total_dur, norm["bgm_volume"])
        )
        if norm["bgm_duck"]:
            filt.append("[%s]asplit=2[voice_main][voice_sc]" % alast)
            filt.append(
                "[bgm_raw][voice_sc]sidechaincompress="
                "threshold=0.015:ratio=8:attack=15:release=350[bgm_ducked]"
            )
            filt.append("[voice_main][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amixed]")
        else:
            filt.append("[%s][bgm_raw]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amixed]" % alast)
        alast = "amixed"

    if norm["burn_subtitles"] and effective_sub_path:
        filt.append("[%s]subtitles=filename='%s'[vburned]" % (vlast, _escape_filter_path(effective_sub_path)))
        vlast = "vburned"

    # Global fades applied at the FINAL timeline start/end (video + audio).
    if fade_in > 0 or fade_out > 0:
        vparts = []
        aparts = []
        if fade_in > 0:
            vparts.append("fade=t=in:st=0:d=%.6f" % fade_in)
            aparts.append("afade=t=in:st=0:d=%.6f" % fade_in)
        if fade_out > 0:
            fo_start = max(0.0, total_dur - fade_out)
            vparts.append("fade=t=out:st=%.6f:d=%.6f" % (fo_start, fade_out))
            aparts.append("afade=t=out:st=%.6f:d=%.6f" % (fo_start, fade_out))
        filt.append("[%s]%s[vout]" % (vlast, ",".join(vparts)))
        filt.append("[%s]%s[aout]" % (alast, ",".join(aparts)))
        vlast, alast = "vout", "aout"
    else:
        filt.append("[%s]null[vout]" % vlast)
        filt.append("[%s]anull[aout]" % alast)
        vlast, alast = "vout", "aout"

    args += ["-filter_complex", ";".join(filt),
             "-map", "[%s]" % vlast, "-map", "[%s]" % alast,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", preset,
             "-c:a", "aac", "-ar", "44100", "-movflags", "+faststart"]

    if sub_input_idx is not None:
        args += ["-map", "%d:s:0" % sub_input_idx, "-c:s", "mov_text", "-disposition:s:0", "default"]
    args += ["-t", str(total_dur)]

    # atomic temp output in the destination directory
    fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=out_real_parent)
    os.close(fd)
    os.remove(tmp)
    args.append(tmp)
    try:
        try:
            proc = subprocess.run(args, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=900)
        except subprocess.TimeoutExpired:
            raise EditPlanError("Render exceeded 15-minute execution limit") from None
        if proc.returncode != 0:
            raise EditPlanError("ffmpeg render failed: %s"
                                % proc.stderr.decode(errors="replace")[-500:])
        meta = probe(tmp)
        os.link(tmp, output)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        if tmp_sub_path and os.path.exists(tmp_sub_path):
            try:
                os.remove(tmp_sub_path)
            except OSError:
                pass

    # Re-hash inputs AFTER render; flag if any source changed underneath us.
    input_hashes_post = [_sha256(c["path"]) for c in norm["clips"]]
    inputs_changed = input_hashes_pre != input_hashes_post

    provenance = {
        "output": output,
        "created": time.time(),
        "profile": profile,
        "ffmpeg_version": _ffmpeg_version(),
        "plan": {"version": norm["version"], "width": norm["width"],
                 "height": norm["height"], "fit": fit, "mute": mute,
                 "volume": volume, "fade_in": fade_in, "fade_out": fade_out,
                 "subtitles": norm["subtitles"],
                 "retime_subtitles": norm["retime_subtitles"],
                 "burn_subtitles": norm["burn_subtitles"],
                 "bgm": norm["bgm"], "bgm_volume": norm["bgm_volume"],
                 "bgm_duck": norm["bgm_duck"],
                 "clips": [{"path": c["path"], "start": c["start"],
                            "end": c["end"], "speed": c["speed"],
                            "volume": c["volume"], "mute": c["mute"]}
                           for c in norm["clips"]]},
        "effective": {
            "output_width": width, "output_height": height,
            "total_duration": total_dur,
            "fade_in": fade_in, "fade_out": fade_out,
            "subtitles_retimed": norm["retime_subtitles"],
            "subtitles_burned": norm["burn_subtitles"],
            "bgm": norm["bgm"],
            "bgm_volume": norm["bgm_volume"] if norm["bgm"] else None,
            "bgm_duck": norm["bgm_duck"] if norm["bgm"] else None,
            "clips": [{"path": c["path"], "speed": c["speed"],
                       "effective_duration": c["effective_duration"],
                       "effective_volume": volume * c["volume"],
                       "effective_mute": bool(mute or c["mute"])}
                      for c in norm["clips"]],
        },
        "plan_sha256": hashlib.sha256(
            json.dumps(norm, sort_keys=True, default=str).encode()).hexdigest(),
        # sha256 captured BEFORE render (source of truth for what was rendered)
        "inputs": [{"path": c["path"], "sha256": h}
                   for c, h in zip(norm["clips"], input_hashes_pre)],
        "inputs_sha256_post_render": [
            {"path": c["path"], "sha256": h}
            for c, h in zip(norm["clips"], input_hashes_post)],
        "inputs_changed_during_render": inputs_changed,
        "output_sha256": _sha256(output),
    }
    with open(output + ".provenance.json", "x") as f:
        json.dump(provenance, f, indent=2, sort_keys=True)

    return {"output": output, "duration": meta["duration"],
            "width": meta["width"], "height": meta["height"],
            "has_audio": meta["has_audio"], "clips": n,
            "profile": profile,
            "inputs_changed_during_render": inputs_changed,
            "provenance": output + ".provenance.json"}
