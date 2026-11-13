import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from creator_tools import local_tts, narrate

ROOT = Path(__file__).resolve().parents[1]


class LocalTTSRegistryTests(unittest.TestCase):
    def test_registry_pins_every_model(self):
        reg = local_tts.registry()
        for key, m in reg["models"].items():
            self.assertRegex(m["revision"], r"^[0-9a-f]{40}$", key)
            self.assertIn(m["license"], ("apache-2.0", "mit"), key)
            for rev in (m.get("extra_repos") or {}).values():
                self.assertRegex(rev, r"^[0-9a-f]{40}$")
        self.assertTrue(reg["runtime"]["hf_home"].startswith("local/"))

    def test_model_selection(self):
        self.assertEqual(local_tts.pick_model("qwen3", clone=False)[0], "qwen3-stock")
        self.assertEqual(local_tts.pick_model("qwen3", clone=True)[0], "qwen3-clone")
        self.assertEqual(local_tts.pick_model("chatterbox", clone=True)[0], "chatterbox")
        with self.assertRaises(ValueError):
            local_tts.pick_model("kokoro", clone=False)

    def test_stock_voice_validation(self):
        _, m = local_tts.pick_model("qwen3", clone=False)
        self.assertEqual(local_tts.check_voice(m, None), "Ryan")
        self.assertEqual(local_tts.check_voice(m, "Aiden"), "Aiden")
        with self.assertRaisesRegex(ValueError, "stock voices"):
            local_tts.check_voice(m, "af_heart")

    def test_guards_before_any_model_run(self):
        with mock.patch.object(local_tts, "_run_worker") as worker:
            with self.assertRaisesRegex(ValueError, "blocked"):
                local_tts.synthesize_lines("chatterbox", [{"text": "x", "out": "/tmp/x.wav"}], lang="he")
            with self.assertRaisesRegex(ValueError, "ref-text"):
                local_tts.synthesize_lines("qwen3", [{"text": "x", "out": "/tmp/x.wav"}], ref_wav="/tmp/r.wav")
            with self.assertRaisesRegex(ValueError, "language"):
                local_tts.synthesize_lines("qwen3", [{"text": "x", "out": "/tmp/x.wav"}], lang="he")
            worker.assert_not_called()

    def test_offline_never_bootstraps_missing_runtime(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "integrations").mkdir()
            (root / "integrations/voice-models.json").write_text((ROOT / "integrations/voice-models.json").read_text())
            with mock.patch("subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "without --offline"):
                    local_tts.ensure_runtime(root, offline=True)
                run.assert_not_called()

    def test_child_env_isolates_and_points_at_project_cache(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x", "PYTHONPATH": "/leak"}):
            env = local_tts._child_env(ROOT, offline=True)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["HF_HOME"], str(ROOT / "local/models/hf"))
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")

    def test_narrate_accepts_local_engines(self):
        self.assertIn("qwen3", narrate.ENGINES)
        self.assertIn("chatterbox", narrate.ENGINES)


if __name__ == "__main__":
    unittest.main()
