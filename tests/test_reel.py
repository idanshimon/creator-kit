import argparse
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from creator_tools import reel, showcase

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "reel"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e2b4f1a60000000049454e44ae426082")


def _have_render():
    try:
        showcase.find_chrome()
    except Exception:
        return False
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class ReelSpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def spec(self, data, name="s.json"):
        p = self.tmp / name
        p.write_text(json.dumps(data))
        return p

    def test_every_template_has_example_and_script(self):
        for t in reel.TEMPLATES:
            self.assertTrue((EXAMPLES / f"{t}.json").is_file(), t)
            self.assertTrue((reel.TEMPLATE_DIR / f"{t}.js").is_file(), t)
            spec = json.loads((EXAMPLES / f"{t}.json").read_text())
            self.assertEqual(spec["template"], t)
            reel.validate(spec)

    def test_examples_build_self_contained_html(self):
        for t in reel.TEMPLATES:
            html = reel.render_html(reel.build(json.loads((EXAMPLES / f"{t}.json").read_text()), EXAMPLES))
            self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
            self.assertNotIn("https://", html)
            for banned in ("Date.now", "new Date", "setTimeout", "setInterval", "Math.random"):
                self.assertNotIn(banned, html, f"{t}: {banned}")
            self.assertIn("window.__advance", html)
            self.assertIn(f"R.templates", html)

    def test_validation_errors(self):
        bad = [
            {"template": "nope", "beats": [{"text": "x"}]},
            {"template": "kinetic", "beats": []},
            {"template": "kinetic", "format": "3:2", "beats": [{"text": "x"}]},
            {"template": "stat", "beats": [{"label": "no value"}]},
            {"template": "before-after", "beats": [{"text": "only before"}]},
            {"template": "kinetic", "beats": [{"kind": "end", "text": "only end"}]},
            {"template": "kinetic", "beats": ["string"]},
            {"template": "kinetic", "fps": 29, "beats": [{"text": "x"}]},
        ]
        for spec in bad:
            with self.assertRaises(reel.ReelError, msg=spec):
                reel.validate(spec)
        with self.assertRaises(reel.ReelError):
            reel.timed_beats("kinetic", [{"text": "x", "duration": 0.1}])

    def test_safe_zones(self):
        z = reel.safe_zone("9:16", "tiktok")
        self.assertEqual((z["t"], z["r"], z["b"], z["l"]), reel.SAFE_916["tiktok"])
        cross = reel.safe_zone("9:16")
        for p in ("tiktok", "reels", "shorts"):
            t, r, b, l = reel.SAFE_916[p]
            # cross must be at least as strict as TikTok on every edge, and clear the widest rail of Reels.
            if p == "tiktok":
                self.assertTrue(cross["t"] >= t and cross["r"] >= r and cross["b"] >= b and cross["l"] >= l)
        self.assertEqual(reel.safe_zone("1:1")["t"], reel.FEED_MARGIN["1:1"])
        with self.assertRaises(reel.ReelError):
            reel.safe_zone("9:16", "myspace")

    def test_durations_and_timeline_sync(self):
        beats = reel.timed_beats("kinetic", [{"text": "a"}, {"text": "b", "duration": 3}, {"kind": "end", "text": "c"}])
        self.assertEqual([(b["start"], b["end"]) for b in beats], [(0, 1.8), (1.8, 4.8), (4.8, 7.4)])
        self.assertTrue(beats[-1]["last"])
        tl = {"slides": [{"start": 0.0, "end": 2.5, "speech_duration": 2.0}, {"start": 2.5, "end": 4.0, "speech_duration": 1.2}],
              "total_duration": 4.0}
        beats = reel.timed_beats("kinetic", [{"text": "Hello *big* world"}, {"text": "two"}, {"text": "after", "duration": 1}], tl)
        self.assertEqual(beats[0]["end"], 2.5)
        self.assertEqual([w["w"] for w in beats[0]["words"]], ["Hello", "big", "world"])
        self.assertAlmostEqual(beats[0]["words"][-1]["e"], 2.0, places=2)
        self.assertEqual((beats[2]["start"], beats[2]["end"]), (4.0, 5.0))

    def test_formats_palette_and_media(self):
        (self.tmp / "shot.png").write_bytes(PNG)
        spec = {"template": "phone", "screen": "shot.png", "beats": [{"text": "x", "zoom": {"x": .5, "y": .2, "scale": 2}}],
                "background": "shot.png"}
        m = reel.build(spec, self.tmp, fmt="16:9", style="mission-control")
        self.assertEqual((m["W"], m["H"]), (1920, 1080))
        self.assertTrue(m["screen"].startswith("data:image/png;base64,"))
        self.assertTrue(m["background"].startswith("data:image/png;base64,"))
        self.assertEqual(m["style"], "mission-control")
        from creator_tools import styles
        self.assertGreaterEqual(styles.contrast(m["hi"], m["pal"]["bg"]), 4.5)
        noir = reel.palette("noir")
        self.assertNotEqual(noir["hi"].lower(), noir["pal"]["accent"].lower())  # neutral accent replaced by a hue
        with self.assertRaises(reel.ReelError):
            reel.build({**spec, "screen": "missing.png"}, self.tmp)
        (self.tmp / "clip.mp4").write_bytes(b"x")
        with self.assertRaises(reel.ReelError):
            reel.build({**spec, "screen": "clip.mp4"}, self.tmp)

    def test_html_only_and_refuse_overwrite(self):
        p = self.spec({"template": "quote", "format": "1:1", "beats": [{"text": "Hi *there*", "author": "A B"}]})
        out = self.tmp / "out"
        r = reel.make(p, out, html_only=True, show_safe=True, log=lambda m: None)
        self.assertEqual(r["size"], [1080, 1080])
        html = Path(r["html"]).read_text()
        self.assertIn('"showSafe": true', html)
        with self.assertRaises(reel.ReelError):
            reel.make(p, out, html_only=True, log=lambda m: None)

    def test_argparse_wiring(self):
        ap = argparse.ArgumentParser()
        reel.add_arguments(ap)
        a = ap.parse_args(["--spec", "s.json", "--output", "o", "--format", "4:5", "--safe-zones", "--gif", "--platform", "tiktok"])
        self.assertEqual((a.format, a.safe_zones, a.gif, a.platform, a.html_only), ("4:5", True, True, "tiktok", False))

    @unittest.skipUnless(_have_render(), "needs Chrome + ffmpeg")
    def test_render_with_audio(self):
        wav = self.tmp / "n.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2", str(wav)], check=True)
        tl = self.tmp / "timeline.json"
        tl.write_text(json.dumps({"slides": [{"start": 0, "end": 1.2, "speech_duration": 1.0}], "total_duration": 1.2}))
        p = self.spec({"template": "kinetic", "format": "1:1", "fps": 24, "progress": False,
                       "beats": [{"text": "Frame *exact*"}], "narration": {"timeline": "timeline.json", "audio": "n.wav"}})
        r = reel.make(p, self.tmp / "out", log=lambda m: None)
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type,width,height",
                                                    "-show_entries", "format=duration", "-of", "json", r["video"]]))
        kinds = {s["codec_type"]: s for s in probe["streams"]}
        self.assertEqual(kinds["video"]["codec_name"], "h264")
        self.assertEqual((kinds["video"]["width"], kinds["video"]["height"]), (1080, 1080))
        self.assertEqual(kinds["audio"]["codec_name"], "aac")
        self.assertAlmostEqual(float(probe["format"]["duration"]), 1.2, delta=0.15)
        self.assertTrue(Path(r["poster"]).is_file())
        self.assertFalse((self.tmp / "out" / ".reel-silent.mp4").exists())


if __name__ == "__main__":
    unittest.main()
