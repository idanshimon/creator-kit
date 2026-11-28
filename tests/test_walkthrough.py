import argparse
import json
import tempfile
import unittest
from pathlib import Path

from creator_tools import walkthrough as wt

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "walkthrough"


class WalkthroughTests(unittest.TestCase):
    def test_example_spec_valid_and_targets_inside_image(self):
        spec = wt.load_spec(EX / "pipeline-control.walkthrough.json")
        self.assertEqual(len(spec["steps"]), 5)
        for s in spec["steps"]:
            w, h = wt.png_size(s["image"])
            t = s["target"]
            self.assertLessEqual(t["x"] + t["w"], w)
            self.assertLessEqual(t["y"] + t["h"], h)

    def test_validation_errors(self):
        bad = [
            {},
            {"steps": [{"narration": "x"}]},
            {"steps": [{"image": "a.png", "url": "http://x", "narration": "x"}]},
            {"steps": [{"url": "http://x", "narration": "x"}]},
            {"steps": [{"url": "http://x", "selector": "#a", "narration": ""}]},
            {"steps": [{"url": "http://x", "selector": "#a", "narration": "x", "annotations": ["laser"]}]},
            {"steps": [{"url": "http://x", "target": {"x": 1, "y": 1, "w": 0, "h": 2}, "narration": "x"}]},
            {"accent": "orange", "steps": [{"url": "http://x", "selector": "#a", "narration": "x"}]},
            {"accent": "#12345", "steps": [{"url": "http://x", "selector": "#a", "narration": "x"}]},
            {"theme": "sepia", "steps": [{"url": "http://x", "selector": "#a", "narration": "x"}]},
        ]
        for spec in bad:
            with self.assertRaises(wt.WalkthroughError, msg=spec):
                wt.validate_spec(spec)

    def test_script_matches_narrate_contract(self):
        from creator_tools import narrate
        spec = wt.load_spec(EX / "pipeline-control.walkthrough.json")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "SCRIPT.md"
            wt.write_script(spec, p)
            items = narrate.parse_script(p)
            self.assertEqual([i["text"] for i in items], [s["narration"] for s in spec["steps"]])
            with self.assertRaises(FileExistsError):
                wt.write_script(spec, p)

    def test_html_embeds_timeline_and_is_offline(self):
        spec = wt.load_spec(EX / "pipeline-control.walkthrough.json")
        steps = [{**s, "src": "assets/x.png", "iw": 1440, "ih": 900} for s in spec["steps"]]
        slides, t = [], 0.0
        for s in spec["steps"]:
            slides.append({"start": t, "end": t + 3, "speech_duration": 2.4, "text": s["narration"]})
            t += 3
        html = wt.build_html(spec, steps, {"slides": slides, "total_duration": t})
        self.assertIn("window.__ready", html)
        self.assertIn("window.__advance", html)
        self.assertNotIn("/*__WALKTHROUGH_DATA__*/null", html)
        self.assertNotRegex(html, r"(src|href)=\"https?://")
        self.assertIn('"total": 15.0', html)
        for ctrl in ('id="player"', 'id="btn-play"', 'id="btn-prev"', 'id="btn-next"',
                     'id="btn-replay"', 'id="btn-cap"', 'id="btn-speed"', 'id="step-dots"'):
            self.assertIn(ctrl, html)
        with self.assertRaises(wt.WalkthroughError):
            wt.build_html(spec, steps, {"slides": slides[:2], "total_duration": 6})

    def test_optional_accent_and_theme(self):
        raw = json.loads((EX / "pipeline-control.walkthrough.json").read_text())
        raw["accent"] = "#38e1cf"
        raw["theme"] = "light"
        spec = wt.validate_spec(raw, base=EX)
        self.assertEqual(spec["accent"], "#38e1cf")
        self.assertEqual(spec["theme"], "light")
        steps = [{**s, "src": "assets/x.png", "iw": 1440, "ih": 900} for s in spec["steps"]]
        slides = [{"start": i * 2.0, "end": i * 2.0 + 2.0, "speech_duration": 1.5, "text": s["narration"]}
                  for i, s in enumerate(spec["steps"])]
        html = wt.build_html(spec, steps, {"slides": slides, "total_duration": len(slides) * 2.0})
        self.assertIn('"accent": "#38e1cf"', html)
        self.assertIn('"theme": "light"', html)

    def test_refuses_existing_output(self):
        ap = wt.add_arguments(argparse.ArgumentParser())
        with tempfile.TemporaryDirectory() as d:
            args = ap.parse_args(["--spec", str(EX / "pipeline-control.walkthrough.json"), "--output", d])
            with self.assertRaises(FileExistsError):
                wt.run(args, log=lambda *_: None)

    def test_html_only_with_reused_narration(self):
        """End-to-end up to HTML with a fake narration dir (no TTS, no Chrome)."""
        spec = json.loads((EX / "pipeline-control.walkthrough.json").read_text())
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for s in spec["steps"]:
                s["image"] = str(EX / s["image"])
            (d / "spec.json").write_text(json.dumps(spec))
            nd = d / "narr"
            nd.mkdir()
            slides = [{"start": i * 2.0, "end": i * 2.0 + 2, "speech_duration": 1.5, "text": s["narration"]}
                      for i, s in enumerate(spec["steps"])]
            (nd / "timeline.json").write_text(json.dumps({"slides": slides, "total_duration": 10.0}))
            ap = wt.add_arguments(argparse.ArgumentParser())
            args = ap.parse_args(["--spec", str(d / "spec.json"), "--output", str(d / "out"),
                                  "--narration", str(nd), "--html-only"])
            r = wt.run(args, log=lambda *_: None)
            self.assertTrue(Path(r["html"]).exists())
            self.assertTrue((d / "out" / "assets" / "step-05.png").exists())
            self.assertIn("## Step 5 (Frame 5)", (d / "out" / "SCRIPT.md").read_text())


if __name__ == "__main__":
    unittest.main()
