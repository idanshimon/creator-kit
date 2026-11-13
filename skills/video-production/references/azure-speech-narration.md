# Azure AI Speech narration — upgrading off Kokoro

Kokoro `af_heart` is free, offline and **audibly synthetic**. That is the right
trade while you iterate on timing, and the wrong one for anything judged,
client-facing or watched by an executive. Azure AI Speech **DragonHD** voices read
as broadcast narration.

The supported path is the first-party runner, which handles auth, SSML, the
regional host, size gates and the timeline rebuild:

```bash
python3.13 creator.py narrate --script SCRIPT.md --output productions/<name>/narration \
  --engine azure --allow-cloud \
  --cast '{"HOST":"en-US-Andrew:DragonHDLatestNeural","GUIDE":"en-US-Ava:DragonHDLatestNeural"}'
```

`--allow-cloud` is mandatory: script text is sent to Azure. Sign-in options (see
`docs/VOICES.md`):

- **Key**: set `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` in the environment or
  the repo `.env`.
- **Entra** (no key set): pass `--inventory` from `python3.13 creator.py discover`;
  the token comes from `az`. Needs the *Cognitive Services Speech User* role.

The rest of this file explains what the runner does, so you can debug it or roll
your own.

## 1. Cast per narrator, not one voice for the whole piece

If the script names speakers, give each a distinct voice so handoffs are audible.
One voice reading a five-person script is the tell that nobody recorded it.

A casting that worked for a serious enterprise story (all `DragonHDLatestNeural`):

| Role in script | Voice | Why |
|---|---|---|
| Opener, warm and unhurried | `en-US-Andrew:DragonHDLatestNeural` | opens a story without sounding like an ad |
| The honest / restrained beat | `en-US-Ava:DragonHDLatestNeural` | restraint without drama |
| The demo walkthrough | `en-US-Steffan:DragonHDLatestNeural` | plain and matter-of-fact — showing, not selling |
| The limits / guardrails | `en-US-Adam:DragonHDLatestNeural` | lower, firmer; delivers limits as decisions |
| The close / the ask | `en-US-Emma:DragonHDLatestNeural` | clean, lifts at the ask |

Other tiers you may see: `:DragonHDOmniLatestNeural`, `:DragonHDFlashLatestNeural`
(faster/cheaper), `MAI-Voice-*` (rich style lists), and classic `*Neural` voices
(`en-US-AriaNeural` offers `style="narration-professional"`). Enumerate what your
resource actually serves (the regional `voices/list` endpoint) rather than
trusting a docs page.

**Audition before committing.** Render every candidate on the *hardest* line (the
restrained one, not the punchy one), prefix each with a spoken "Option N, <name>"
tag, and concatenate into one file the reviewer plays once.

## 2. Auth traps (if you call the REST API yourself)

- **`disableLocalAuth=true` means there is no key.** `az cognitiveservices account
  keys list` fails with `Failed to list key`. Don't hunt for one; use Entra.
- **A plain bearer token returns 401.** The Speech data plane needs the composite
  header `Authorization: Bearer aad#<full-resource-id>#<token>`, where the token
  comes from `az account get-access-token --resource https://cognitiveservices.azure.com`.
- **The resource's own custom-domain host returns 404.** Use the *regional* TTS
  host (`<region>.tts.speech…/cognitiveservices/v1`), even though the resource
  advertises the custom domain as its endpoint.
- **403** means the *Cognitive Services Speech User* role is missing; check with
  `az role assignment list --scope <resource-id> -o table`.

## 3. Never trust curl's exit code — gate on file size

A 401 or 400 writes a **small error body into your `.wav`** and curl exits 0. A
batch loop then reports every line "ok" while producing unplayable files.

```bash
sz=$(stat -f%z "$V/$n.wav" 2>/dev/null || stat -c%s "$V/$n.wav" 2>/dev/null || echo 0)
if [ "$sz" -gt 20000 ]; then echo "ok   $n"; else echo "FAIL $n — $(head -c 200 "$V/$n.wav")"; rm -f "$V/$n.wav"; fi
```

The threshold must be a real size, not merely non-empty — the error body is non-empty.

## 4. SSML shape

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
<voice name="en-US-Andrew:DragonHDLatestNeural"><prosody rate="-6%">TEXT</prosody></voice></speak>
```

- **Escape the text** (`&`, `<`, `>`); scripts are full of ampersands and the
  request fails opaquely without it.
- `rate="-6%"` (the runner's default `--rate`): DragonHD runs a touch quick for
  technical material; around −6% lands near 2.45 words/sec.
- Styles need `<mstts:express-as style="...">` plus the `mstts` namespace, and only
  work on voices with a non-empty `StyleList`. DragonHD voices generally have none.

## 5. Switching TTS engines invalidates the timeline — rebuild it

Azure at `-6%` ran about **18% longer** than Kokoro on an identical script
(254 s → 299 s of speech). Every scene boundary moves. After regenerating audio:

1. Re-derive `timeline.json` from the **new** `ffprobe` durations, keeping your
   per-scene dwell values.
2. Rebuild `narration.wav` by alternating line / silence of exactly `dwell`.
3. Assert `ffprobe(narration.wav) == timeline_total` to the millisecond before
   re-rendering. A delta of `+0.000s` is the gate.

`creator.py narrate` writes a fresh `timeline.json` + `narration.wav` with this
zero-delta property; pass `--dwell` to change the default pause. Then re-run the
frame render — the old MP4 is the **previous engine's cut**. Don't ship it, and
don't call the job done until the new render has finished and been muxed. Long
renders exceed typical foreground timeouts; run them in the background with a
completion notification.

## 6. Runtime changed — say so

If the piece now finishes well under target, the deliberate dwell has become
proportionally thinner. **Add dwell; don't slow the voices further** — slowed
speech sounds slowed. Surface the trade to the reviewer instead of silently
absorbing it.
