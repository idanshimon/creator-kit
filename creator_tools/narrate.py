"""First-party narration runner & zero-delta timeline builder.

Supports:
  - `azure`  (Azure AI Speech DragonHD / Neural voices via Entra `Bearer aad#<rid>#<token>`,
              requires `--allow-cloud`, gates on >=20 KiB RIFF WAV payload)
  - `f5`     (Idan's offline F5-TTS voice clone at `~/projects/ai/local-voice/say.py`,
              with volumedetect peak verification)
  - `kokoro` (Offline HyperFrames Kokoro voice via `npx hyperframes tts`)
  - `qwen3`  (Local Qwen3-TTS via MLX: stock voices + instruct, or clone with --ref/--ref-text)
  - `chatterbox` (Local Chatterbox Multilingual V3 via MLX: built-in voice or clone; 23 languages incl. Hebrew)
              Models: integrations/voice-models.json; weights auto-download to local/models/hf.

Also builds a zero-delta `narration.wav` + `timeline.json` from generated WAVs
and per-line dwell pauses, asserting `abs(ffprobe(narration.wav) - timeline_total) <= 0.05`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from creator_tools import local_tts, models

ENGINES = ("azure", "f5", "kokoro", *local_tts.ENGINES)

DEFAULT_VOICE_AZURE = "en-US-Andrew:DragonHDLatestNeural"
DEFAULT_VOICE_KOKORO = "af_heart"
LOCAL_VOICE_SAY = Path(os.environ.get("CREATOR_F5_SAY", str(Path.home() / "projects" / "ai" / "local-voice" / "say.py"))).expanduser()
MIN_AZURE_WAV_BYTES = 20000

_HEADING_RE = re.compile(r"^#{2,3}\s+(.*?)\(\s*frame\s+(\d+)\s*\)\s*$", re.IGNORECASE)
_SPEAKER_RE = re.compile(r"^\*\*speaker\s*:\*\*\s*(.+)$", re.IGNORECASE)
_VOICE_RE = re.compile(r"^\*\*voice\s*:\*\*\s*(.+)$", re.IGNORECASE)
_DWELL_RE = re.compile(r"^\*\*dwell\s*:\*\*\s*([0-9.]+)\s*s?\s*$", re.IGNORECASE)


def escape_ssml(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_ssml(text: str, voice: str, rate: str = "-6%", style: str | None = None) -> str:
    escaped = escape_ssml(text)
    inner = f'<prosody rate="{escape_ssml(rate)}">{escaped}</prosody>'
    if style:
        inner = f'<mstts:express-as style="{escape_ssml(style)}">{inner}</mstts:express-as>'
        ns = ' xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts"'
    else:
        ns = ' xmlns="http://www.w3.org/2001/10/synthesis"'
    return f'<speak version="1.0"{ns} xml:lang="en-US"><voice name="{escape_ssml(voice)}">{inner}</voice></speak>'


def parse_script(source, cast: dict | None = None, default_voice: str | None = None,
                 default_dwell: float = 0.6) -> list[dict]:
    """Parse either a JSON lines spec or a HyperFrames `SCRIPT.md` into ordered line items.

    Each returned item is:
      {"id": "01", "frame": 1, "title": str, "speaker": str|None,
       "voice": str|None, "text": str, "dwell": float}
    """
    cast = {str(k).upper(): v for k, v in (cast or {}).items()}
    p = Path(source).expanduser().resolve()
    raw = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        data = json.loads(raw)
        items = data.get("lines", data) if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            raise ValueError("Script JSON must contain a non-empty list of lines")
        out = []
        for idx, row in enumerate(items, 1):
            if not isinstance(row, dict) or not str(row.get("text", "")).strip():
                raise ValueError(f"Line {idx} must be an object with non-empty text")
            spk = str(row["speaker"]).strip() if row.get("speaker") else None
            voice = row.get("voice") or (cast.get(spk.upper()) if spk else None) or default_voice
            line_id = str(row.get("id") or f"{idx:02d}")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", line_id):
                raise ValueError(f"Invalid line id: {line_id}")
            out.append({
                "id": line_id,
                "frame": int(row.get("frame", idx)),
                "title": str(row.get("title", f"Frame {idx}")),
                "speaker": spk,
                "voice": voice,
                "text": str(row["text"]).strip(),
                "dwell": float(row.get("dwell", default_dwell)),
            })
        return out

    # Markdown parser matching HyperFrames `## Title (Frame N)` contract
    lines_out = []
    cur = None
    spoken = []

    def flush():
        nonlocal cur, spoken
        if cur is not None:
            txt = " ".join(s.strip() for s in spoken if s.strip()).strip()
            if not txt:
                raise ValueError(f"Frame {cur['frame']} ({cur['title']}) has no spoken text")
            cur["text"] = txt
            if not cur.get("voice"):
                spk = cur.get("speaker")
                cur["voice"] = (cast.get(spk.upper()) if spk else None) or default_voice
            lines_out.append(cur)
        cur = None
        spoken = []

    for raw_ln in raw.splitlines():
        m = _HEADING_RE.match(raw_ln.strip())
        if m:
            flush()
            title = m.group(1).strip(" —-\t")
            fnum = int(m.group(2))
            cur = {
                "id": f"{fnum:02d}",
                "frame": fnum,
                "title": title or f"Frame {fnum}",
                "speaker": None,
                "voice": None,
                "dwell": float(default_dwell),
            }
            continue
        if cur is None:
            continue
        stripped = raw_ln.strip()
        if not stripped:
            continue
        ms = _SPEAKER_RE.match(stripped)
        if ms:
            cur["speaker"] = ms.group(1).strip()
            continue
        mv = _VOICE_RE.match(stripped)
        if mv:
            cur["voice"] = mv.group(1).strip()
            continue
        md = _DWELL_RE.match(stripped)
        if md:
            cur["dwell"] = float(md.group(1))
            continue
        if stripped.startswith("**") and ":" in stripped:
            continue
        if raw_ln.startswith(("    ", "\t")):
            spoken.append(stripped)
    flush()
    if not lines_out:
        raise ValueError(
            "No frames parsed from script; headings must match '## Title (Frame N)' with 4-space indented spoken lines"
        )
    return lines_out


def speech_account(inventory: dict, account_name: str | None = None) -> dict:
    accounts = [a for a in inventory.get("accounts", []) if a.get("kind") == "SpeechServices"]
    if account_name:
        accounts = [a for a in accounts if a.get("account") == account_name]
    if not accounts:
        raise ValueError("No SpeechServices account in inventory; run discover or pass --speech-account")
    acc = accounts[0]
    sub = inventory.get("subscription")
    rg = acc.get("resource_group")
    name = acc.get("account")
    loc = acc.get("location")
    if not (sub and rg and name and loc):
        raise ValueError("SpeechServices inventory entry missing subscription, resource_group, account, or location")
    if not re.fullmatch(r"[a-z0-9]+", loc):
        raise ValueError(f"Invalid Azure region for SpeechServices: {loc}")
    rid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{name}"
    return {"account": name, "resource_group": rg, "location": loc, "resource_id": rid, "subscription": sub}


def speech_key_config(env=None) -> dict | None:
    """Key-based Azure Speech config from AZURE_SPEECH_KEY + AZURE_SPEECH_REGION, else None."""
    env = os.environ if env is None else env
    key = (env.get("AZURE_SPEECH_KEY") or "").strip()
    region = (env.get("AZURE_SPEECH_REGION") or "").strip().lower()
    if not key and not region:
        return None
    if not (key and region):
        raise ValueError("Set both AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (or neither, to use Entra inventory)")
    if not re.fullmatch(r"[a-z0-9]+", region):
        raise ValueError(f"Invalid AZURE_SPEECH_REGION: {region}")
    return {"account": f"key:{region}", "location": region, "key": key}


def synthesize_azure_line(text: str, voice: str, out_wav: Path, *, region: str,
                          resource_id: str | None = None, token: str | None = None,
                          key: str | None = None, rate: str = "-6%", style: str | None = None) -> int:
    ssml = build_ssml(text, voice=voice, rate=rate, style=style).encode("utf-8")
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    if key:
        auth = {"Ocp-Apim-Subscription-Key": key}
    elif resource_id and token:
        auth = {"Authorization": f"Bearer aad#{resource_id}#{token}"}
    else:
        raise ValueError("Azure Speech needs a key or an Entra resource_id + token")
    headers = {
        **auth,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
        "User-Agent": "creator-kit-narrate",
    }
    req = urllib.request.Request(url, data=ssml, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Azure Speech HTTP {e.code}: verify key/region (or Speech User role) and voice name") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Azure Speech connection failed or timed out; no automatic retry") from None
    if len(payload) < MIN_AZURE_WAV_BYTES or not payload.startswith(b"RIFF"):
        raise ValueError(
            f"Azure Speech returned invalid/undersized audio ({len(payload)} bytes < {MIN_AZURE_WAV_BYTES}); refusing to save error body"
        )
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with out_wav.open("xb") as f:
        f.write(payload)
    return len(payload)


def synthesize_f5_line(text: str, out_wav: Path, *, ref_wav: str | None = None,
                       speed: float = 1.0, say_script: Path = LOCAL_VOICE_SAY) -> int:
    if not say_script.is_file():
        raise RuntimeError(f"Local F5-TTS script not found at {say_script}")
    cmd = [str(say_script), "--speed", str(speed), "-o", str(out_wav)]
    if ref_wav:
        cmd += ["--ref", str(Path(ref_wav).expanduser().resolve())]
    cmd.append(text)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out_wav.is_file():
        raise RuntimeError("F5-TTS synthesis failed: " + (proc.stderr or proc.stdout or "")[-400:])
    size = out_wav.stat().st_size
    if size < 4096:
        out_wav.unlink(missing_ok=True)
        raise ValueError("F5-TTS produced undersized WAV")
    return size


def synthesize_kokoro_line(text: str, voice: str, out_wav: Path, *, root: Path) -> int:
    hf_dir = root / "hyperframes"
    npx = shutil.which("npx")
    if not npx or not hf_dir.is_dir():
        raise RuntimeError("HyperFrames npx not available for local Kokoro synthesis")
    env = dict(os.environ)
    om_py = root / "OpenMontage" / ".venv" / "bin" / "python"
    if om_py.is_file():
        env.setdefault("HYPERFRAMES_PYTHON", str(om_py))
    proc = subprocess.run(
        [npx, "hyperframes", "tts", text, "--voice", voice, "--output", str(out_wav)],
        cwd=str(hf_dir), env=env, capture_output=True, text=True, timeout=180
    )
    if proc.returncode != 0 or not out_wav.is_file() or out_wav.stat().st_size < 4096:
        out_wav.unlink(missing_ok=True)
        raise RuntimeError("Kokoro TTS failed: " + (proc.stderr or proc.stdout or "")[-400:])
    return out_wav.stat().st_size


def _probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        stderr=subprocess.DEVNULL, timeout=30
    ).decode().strip()
    return float(out)


def assemble_timeline(items: list[dict], voice_dir: Path, out_dir: Path, *, sample_rate: int = 24000) -> dict:
    """Build `timeline.json` and concatenated `narration.wav` with exact dwell silence gaps."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required to assemble narration timeline")
    slides = []
    cursor = 0.0
    speech_total = 0.0
    with tempfile.TemporaryDirectory(prefix="creator-narration-") as tmp:
        tmp_path = Path(tmp)
        concat_files = []
        for idx, item in enumerate(items):
            wav = voice_dir / f"{item['id']}.wav"
            dur = round(_probe_duration(wav), 4)
            dwell = round(max(0.0, float(item.get("dwell", 0.6))), 4)
            norm_wav = tmp_path / f"norm-{idx:03d}.wav"
            subprocess.run(
                [ffmpeg, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-i", str(wav), "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le",
                 str(norm_wav)],
                check=True, timeout=60
            )
            norm_dur = _probe_duration(norm_wav)
            concat_files.append(norm_wav)
            if dwell > 0:
                gap_wav = tmp_path / f"gap-{idx:03d}.wav"
                subprocess.run(
                    [ffmpeg, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                     "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
                     "-t", f"{dwell:.4f}", "-c:a", "pcm_s16le", str(gap_wav)],
                    check=True, timeout=30
                )
                concat_files.append(gap_wav)
            slide_total = round(norm_dur + dwell, 4)
            slides.append({
                "id": item["id"],
                "frame": item["frame"],
                "title": item["title"],
                "speaker": item.get("speaker"),
                "voice": item.get("voice"),
                "audio": f"voice/{item['id']}.wav",
                "start": round(cursor, 4),
                "speech_duration": round(norm_dur, 4),
                "dwell": dwell,
                "duration": slide_total,
                "end": round(cursor + slide_total, 4),
                "text": item["text"],
            })
            cursor += slide_total
            speech_total += norm_dur

        list_file = tmp_path / "concat.txt"
        list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in concat_files), encoding="utf-8")
        narration_wav = out_dir / "narration.wav"
        subprocess.run(
            [ffmpeg, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(list_file),
             "-c", "copy", str(narration_wav)],
            check=True, timeout=120
        )

    measured_total = round(_probe_duration(narration_wav), 4)
    timeline_total = round(cursor, 4)
    delta = round(measured_total - timeline_total, 4)
    if abs(delta) > 0.05:
        raise RuntimeError(
            f"Narration timeline delta {delta:+.4f}s exceeds 0.05s gate ({measured_total}s vs {timeline_total}s)"
        )
    timeline = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "slides": slides,
        "speech_duration": round(speech_total, 4),
        "total_duration": timeline_total,
        "measured_narration_duration": measured_total,
        "sync_delta_seconds": delta,
        "narration_wav": str(narration_wav),
        "narration_sha256": hashlib.sha256(narration_wav.read_bytes()).hexdigest(),
    }
    timeline_path = out_dir / "timeline.json"
    with timeline_path.open("x", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, allow_nan=False)
        f.write("\n")
    return timeline


def run(script_path, output_dir, *, engine="azure", inventory=None, speech_account_name=None,
        cast=None, default_voice=None, rate="-6%", dwell=0.6, ref_wav=None, speed=1.0,
        allow_cloud=False, root=None, ref_text=None, lang="en", instruct=None,
        offline=False) -> dict:
    if engine not in ENGINES:
        raise ValueError("engine must be one of: " + ", ".join(ENGINES))
    if engine == "azure" and not allow_cloud:
        raise ValueError("Azure Speech narration sends script text to Azure; pass --allow-cloud")
    out = Path(output_dir).expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Output exists; select a new directory: {out}")
    if default_voice is None and engine in ("azure", "kokoro", "f5"):
        default_voice = DEFAULT_VOICE_AZURE if engine == "azure" else DEFAULT_VOICE_KOKORO

    items = parse_script(script_path, cast=cast, default_voice=default_voice, default_dwell=dwell)
    speech_info = None
    token = None
    if engine == "azure":
        speech_info = None if inventory else speech_key_config()
        if speech_info is None:
            if not inventory:
                raise ValueError("Azure Speech needs AZURE_SPEECH_KEY + AZURE_SPEECH_REGION, or --inventory from discover")
            speech_info = speech_account(inventory, speech_account_name)
            token = models.access_token(speech_info["subscription"])

    out.mkdir(parents=True, exist_ok=False)
    voice_dir = out / "voice"
    voice_dir.mkdir()
    root_path = Path(root or Path(__file__).resolve().parents[1])

    local_info = None
    if engine in local_tts.ENGINES:
        local_info = local_tts.synthesize_lines(
            engine,
            [{"text": it["text"], "voice": it["voice"], "instruct": instruct,
              "out": str(voice_dir / f"{it['id']}.wav")} for it in items],
            ref_wav=ref_wav, ref_text=ref_text, lang=lang, speed=speed, offline=offline,
            root=root_path)
    for item in ([] if local_info else items):
        wav_path = voice_dir / f"{item['id']}.wav"
        if engine == "azure":
            assert speech_info is not None
            synthesize_azure_line(
                item["text"], item["voice"] or DEFAULT_VOICE_AZURE, wav_path,
                region=speech_info["location"], resource_id=speech_info.get("resource_id"),
                token=token, key=speech_info.get("key"), rate=rate
            )
        elif engine == "f5":
            synthesize_f5_line(item["text"], wav_path, ref_wav=ref_wav, speed=speed)
        else:
            synthesize_kokoro_line(item["text"], item["voice"] or DEFAULT_VOICE_KOKORO, wav_path, root=root_path)

    timeline = assemble_timeline(items, voice_dir, out)
    provenance = {
        "operation": f"narration-{engine}",
        "engine": engine,
        "script": str(Path(script_path).expanduser().resolve()),
        "speech_account": speech_info["account"] if speech_info else None,
        "local_model": ({k: local_info[k] for k in ("model", "repo", "revision", "license")}
                        if local_info else None),
        "lines": len(items),
        "total_duration": timeline["total_duration"],
        "measured_narration_duration": timeline["measured_narration_duration"],
        "sync_delta_seconds": timeline["sync_delta_seconds"],
        "narration_sha256": timeline["narration_sha256"],
        "review_required": False,
    }
    with (out / "timeline.json.provenance.json").open("x", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, allow_nan=False)
        f.write("\n")
    return {
        "output": str(out),
        "engine": engine,
        "lines": len(items),
        "timeline": str(out / "timeline.json"),
        "narration_wav": str(out / "narration.wav"),
        "total_duration": timeline["total_duration"],
        "sync_delta_seconds": timeline["sync_delta_seconds"],
    }
