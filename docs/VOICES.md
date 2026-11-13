# Local voices (Qwen3-TTS, Chatterbox)

Two local, open-weight narration engines join `azure`, `f5` and `kokoro` in `creator.py narrate`.
They run on Apple Silicon through MLX (`mlx-audio`) and send nothing to a cloud service.

## Where things live

| What | Where | In Git |
|---|---|---|
| Model list, pinned revisions, licenses, stock voices, verified/blocked languages | `integrations/voice-models.json` | yes (single owner) |
| Runtime (Python 3.12 + pinned mlx-audio) | `local/voice-venv/` | no |
| Weights (Hugging Face cache, `HF_HOME`) | `local/models/hf/` | no |
| Read-only model views with overlay files | `local/models/overlays/` | no |
| Worker that loads a model once and writes one WAV per line | `creator_tools/voice_worker.py` | yes |

Bootstrap is automatic: if the runtime or a model is missing, the first `narrate` run creates the
venv with `uv` (from your configured package index) and downloads the weights at the pinned revision.
`--offline` forbids any download and fails instead. To prepare a machine ahead of time:

```bash
python3.13 creator.py voices fetch            # all models (~12 GB)
python3.13 creator.py voices fetch --model qwen3-stock
python3.13 creator.py voices list             # downloaded?, voices, verified languages
```

## Azure Speech: two ways to sign in

`--engine azure` always needs `--allow-cloud` (script text goes to Azure).

- **Key** (simplest, any Speech resource with local auth enabled): set
  `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` in the environment or in the repo `.env`
  (see `.env.example`; `creator.py` loads it and never overrides real env vars). Sends
  `Ocp-Apim-Subscription-Key`. This path is covered by unit tests.
- **Entra** (no key set): `--inventory` from `discover`, token from `az`. Needs the
  *Cognitive Services Speech User* role. This path was live-verified by the maintainer.

`CREATOR_F5_SAY` overrides the F5 `say.py` location (set it to your local F5 `say.py`).

## Engines

| Engine | Model (pinned) | License | Use |
|---|---|---|---|
| `qwen3` (no `--ref`) | Qwen3-TTS 1.7B CustomVoice | Apache-2.0 | Stock voices + style instruction |
| `qwen3 --ref X --ref-text "..."` | Qwen3-TTS 1.7B Base | Apache-2.0 | Clone a voice (needs the exact transcript of the reference) |
| `chatterbox` | Chatterbox Multilingual V3 | MIT | Built-in voice, or clone with `--ref` (no transcript needed) |

Stock voices: Qwen3 `Ryan` and `Aiden` (native English), `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`,
`Eric` (Chinese-native). Chatterbox `default` (its built-in reference speaker; the file is pinned
from `mlx-community/chatterbox-fp16` because the multilingual repo ships none).

```bash
# Stock narrator with a style instruction
python3.13 creator.py narrate --script SCRIPT.md --output productions/x/vo-ryan \
  --engine qwen3 --voice Ryan --instruct "Calm, warm, clear narrator. Measured pace."

# Clone your own voice from a short reference recording
python3.13 creator.py narrate --script SCRIPT.md --output productions/x/vo-clone \
  --engine qwen3 --ref voice-ref/ref.wav \
  --ref-text "$(cat voice-ref/ref.txt)"
python3.13 creator.py narrate --script SCRIPT.md --output productions/x/vo-clone-cb \
  --engine chatterbox --ref voice-ref/ref.wav
```

Output is the same as every engine: `voice/*.wav`, zero-delta `narration.wav`, `timeline.json`,
and provenance naming the model repo, revision and license. Each WAV is checked for size and a
peak above -40 dB.

## Maintainer verification (Apple Silicon M5 Pro, 64 GB)

Two-line English script, read back with Whisper large-v3-turbo; all five matched the script word for word:
Qwen3 Ryan (12.1 s audio), Qwen3 Aiden (11.9 s), Qwen3 clone of the maintainer's voice (11.6 s), Chatterbox built-in (10.4 s),
Chatterbox clone of the maintainer's voice (12.8 s). Warm Qwen3 generation was about 7 s for 12 s of audio.
A Whisper read-back proves the words, not how natural the voice sounds; listen before choosing.

Hebrew is blocked for Chatterbox: built-in and cloned voices, with guidance 0 and 0.5, produced
unintelligible speech in this MLX port. Qwen3 has no Hebrew. For Hebrew use Azure.
