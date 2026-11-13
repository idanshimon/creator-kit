import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from creator_tools import crawler, showcase

SKILL = """---
name: demo
---
# Demo skill
Use when the user asks for a demo.
## Steps
You must run `make test` before every merge.
Never push to main without approval from the user.
Try to keep things simple and relevant as needed.
Read references/api.md for the endpoint list.
## Pitfalls
Do not use --force on shared branches.
"""


class CrawlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "SKILL.md"
        self.src.write_text(SKILL)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_routes_and_viewer(self):
        r = crawler.run(self.src, self.tmp / "out", log=lambda m: None)
        data = json.loads(Path(r["json"]).read_text())
        routes = {n["text"][:20]: n["route"] for n in data["nodes"]}
        self.assertEqual(routes["Never push to main w"], "human")
        self.assertEqual(routes["Do not use --force o"], "code")
        vague = [n for n in data["nodes"] if n["vague"]]
        self.assertTrue(any("simple" in n["vague"] for n in vague))
        self.assertTrue(all(n["route"] != "code" for n in vague), "vague wording must not route to code")
        html = Path(r["viewer"]).read_text()
        self.assertIn("const DATA=", html)
        self.assertEqual(r["method"], "keyword heuristic, no model call")
        self.assertTrue(0 <= r["spec_score"] <= 100)

    def test_refuses_existing_output(self):
        (self.tmp / "out").mkdir()
        with self.assertRaises(FileExistsError):
            crawler.run(self.src, self.tmp / "out")


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
class ShowcaseTests(unittest.TestCase):
    def test_deterministic_record(self):
        try:
            showcase.find_chrome()
        except showcase.ShowcaseError:
            self.skipTest("Chrome not installed")
        tmp = Path(tempfile.mkdtemp())
        try:
            page = tmp / "p.html"
            page.write_text("""<body style="margin:0;background:#000"><div id=b style="width:20px;height:20px;background:#f00;position:absolute"></div>
<script>let t=0;window.__advance=ms=>{t+=ms;b.style.left=(t/10)+'px'};window.__done=()=>t>=2000;window.__ready=true</script>""")
            r = showcase.record(page, tmp / "o.mp4", width=320, height=180, fps=10, log=None)
            self.assertTrue(r["deterministic"])
            self.assertEqual(r["frames"], 30)  # 2s until done + 1s hold
            probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
                                             "-of", "csv=p=0", str(tmp / "o.mp4")]).decode().replace(",", " ").split()
            self.assertEqual(probe, ["h264"])
            with self.assertRaises(showcase.ShowcaseError):
                showcase.record(page, tmp / "o.mp4", log=None)
        finally:
            shutil.rmtree(tmp)


class ModelRoutingTests(unittest.TestCase):
    def test_crawl_azure_requires_consent_before_inventory(self):
        import contextlib, io
        import creator
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "SKILL.md"
            src.write_text(SKILL)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = creator.main(["--inventory", str(Path(t) / "missing.json"), "crawl", "--scorer", "azure",
                                   "--input", str(src), "--output", str(Path(t) / "out")])
            self.assertNotEqual(rc, 0)
            self.assertIn("--allow-cloud", err.getvalue())
            self.assertFalse((Path(t) / "out").exists())

    def test_best_mini_picks_highest_version(self):
        from creator_tools import models
        inv = {"accounts": []}
        rows = [{"id": f"a/{d}", "deployment": d, "capability": "chat", "state": "Succeeded"}
                for d in ["gpt-4.1-mini", "gpt-5-mini", "gpt-5.4-mini", "gpt-5.4", "gpt-4o-mini", "o3-mini"]]
        orig = models.model_rows
        models.model_rows = lambda _inv: rows
        try:
            self.assertEqual(models.best_mini(inv), "a/gpt-5.4-mini")
        finally:
            models.model_rows = orig

    def test_route(self):
        from creator_tools.crawl_model import route
        self.assertEqual(route({"A": .97, "B": .01, "C": .0, "D": .01, "E": .01})[1], "code")
        self.assertEqual(route({"A": .1, "B": .2, "C": .65, "D": .05, "E": 0})[1], "human")
        self.assertEqual(route({"A": .0, "B": .5, "C": .0, "D": .5, "E": 0})[1], "human")   # undecided
        self.assertEqual(route({"A": .8, "B": .1, "C": .0, "D": .1, "E": 0})[1], "model")   # rule but not sure enough


if __name__ == "__main__":
    unittest.main()
