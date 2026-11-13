import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import creator
from creator_tools import narrate

FFMPEG = shutil.which("ffmpeg")

SAMPLE_SCRIPT_MD = """# Capstone Script

## Opening Hook (Frame 1)
**Speaker:** TIM
**Dwell:** 0.4

    Show me who is getting worse, and show me why.

## The Honest Turn (Frame 2)
**Speaker:** LAURA
**Dwell:** 0.5

    To see one patient, he opens three systems & re-types the chart.
"""


class NarrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="narrate_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_script_md_and_casting(self):
        md = self.tmp / "SCRIPT.md"
        md.write_text(SAMPLE_SCRIPT_MD)
        items = narrate.parse_script(
            md,
            cast={"TIM": "en-US-Andrew:DragonHDLatestNeural", "LAURA": "en-US-Ava:DragonHDLatestNeural"},
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "01")
        self.assertEqual(items[0]["voice"], "en-US-Andrew:DragonHDLatestNeural")
        self.assertAlmostEqual(items[0]["dwell"], 0.4)
        self.assertEqual(items[1]["id"], "02")
        self.assertEqual(items[1]["voice"], "en-US-Ava:DragonHDLatestNeural")
        self.assertIn("&", items[1]["text"])

    def test_ssml_escapes_xml_entities(self):
        ssml = narrate.build_ssml("A & B < C > D", voice="en-US-Ava:DragonHDLatestNeural", rate="-6%")
        self.assertIn("A &amp; B &lt; C &gt; D", ssml)
        self.assertNotIn("A & B", ssml)

    def test_azure_narrate_requires_allow_cloud_before_inventory(self):
        md = self.tmp / "SCRIPT.md"
        md.write_text(SAMPLE_SCRIPT_MD)
        err = io.StringIO()
        import contextlib
        with contextlib.redirect_stderr(err):
            rc = creator.main([
                "--inventory", str(self.tmp / "missing.json"),
                "narrate", "--engine", "azure",
                "--script", str(md),
                "--output", str(self.tmp / "out"),
            ])
        self.assertNotEqual(rc, 0)
        self.assertIn("--allow-cloud", err.getvalue())
        self.assertFalse((self.tmp / "out").exists())

    def test_azure_rejects_undersized_error_body(self):
        out_wav = self.tmp / "bad.wav"
        fake_resp = io.BytesIO(b"401 Unauthorized")
        with patch("urllib.request.urlopen", return_value=fake_resp):
            with self.assertRaisesRegex(ValueError, "undersized"):
                narrate.synthesize_azure_line(
                    "hello", "en-US-Andrew:DragonHDLatestNeural", out_wav,
                    resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/acc",
                    region="eastus", token="tok"
                )
        self.assertFalse(out_wav.exists())

    def test_azure_key_auth_sends_subscription_key_header(self):
        out_wav = self.tmp / "ok.wav"
        seen = {}
        def fake_open(req, timeout=0):
            seen.update({k.lower(): v for k, v in req.header_items()})
            seen["url"] = req.full_url
            return io.BytesIO(b"RIFF" + b"\0" * 30000)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            narrate.synthesize_azure_line("hello", "en-US-AvaNeural", out_wav, region="eastus", key="k123")
        self.assertEqual(seen["ocp-apim-subscription-key"], "k123")
        self.assertNotIn("authorization", seen)
        self.assertEqual(seen["url"], "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1")

    def test_speech_key_config_env(self):
        self.assertIsNone(narrate.speech_key_config({}))
        cfg = narrate.speech_key_config({"AZURE_SPEECH_KEY": "k", "AZURE_SPEECH_REGION": "EastUS"})
        assert cfg is not None
        self.assertEqual(cfg["location"], "eastus")
        with self.assertRaisesRegex(ValueError, "both"):
            narrate.speech_key_config({"AZURE_SPEECH_KEY": "k"})
        with self.assertRaisesRegex(ValueError, "Invalid"):
            narrate.speech_key_config({"AZURE_SPEECH_KEY": "k", "AZURE_SPEECH_REGION": "east us/x"})

    def test_azure_run_without_key_or_inventory_explains(self):
        md = self.tmp / "SCRIPT.md"
        md.write_text(SAMPLE_SCRIPT_MD)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "AZURE_SPEECH_KEY"):
                narrate.run(md, self.tmp / "o", engine="azure", allow_cloud=True)

    @unittest.skipUnless(FFMPEG, "ffmpeg required")
    def test_assemble_timeline_zero_delta_with_mocked_azure(self):
        assert FFMPEG is not None
        md = self.tmp / "SCRIPT.md"
        md.write_text(SAMPLE_SCRIPT_MD)
        inv = {
            "subscription": "sub-123",
            "accounts": [{
                "account": "speech1",
                "resource_group": "rg-speech",
                "kind": "SpeechServices",
                "location": "eastus",
            }],
        }

        def fake_synth(text, voice, out_wav, **kwargs):
            # Verify composite Bearer aad#<rid>#<token> contract components were resolved
            self.assertIn("/subscriptions/sub-123/resourceGroups/rg-speech/", kwargs["resource_id"])
            self.assertEqual(kwargs["region"], "eastus")
            self.assertEqual(kwargs["token"], "fake-aad-token")
            subprocess.run(
                [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=440:sample_rate=24000:duration=1.0",
                 "-c:a", "pcm_s16le", str(out_wav)],
                check=True
            )
            return out_wav.stat().st_size

        out_dir = self.tmp / "narration_out"
        with patch("creator_tools.models.access_token", return_value="fake-aad-token"), \
             patch("creator_tools.narrate.synthesize_azure_line", side_effect=fake_synth):
            res = narrate.run(
                md, out_dir, engine="azure", inventory=inv,
                cast={"TIM": "v1", "LAURA": "v2"}, allow_cloud=True
            )
        self.assertEqual(res["lines"], 2)
        self.assertLessEqual(abs(res["sync_delta_seconds"]), 0.05)
        tl = json.loads(Path(res["timeline"]).read_text())
        self.assertAlmostEqual(tl["total_duration"], 2.9, delta=0.05)
        self.assertTrue(Path(res["narration_wav"]).is_file())


if __name__ == "__main__":
    unittest.main()
