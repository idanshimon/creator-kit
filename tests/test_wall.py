import tempfile
import unittest
from pathlib import Path

from creator_tools import wall


class WallTests(unittest.TestCase):
    def _src(self, d, n=5):
        src = Path(d) / "src"; src.mkdir()
        for i in range(n):
            (src / f"shot{i}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return src

    def test_renders_offline_page_with_assets_and_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            res = wall.render(self._src(d), Path(d) / "out", "No two pages look alike")
            html = (Path(d) / "out" / "index.html").read_text()
            self.assertEqual(res["tiles"], 5)
            self.assertEqual(res["style"], "noir")
            self.assertEqual(len(list((Path(d) / "out" / "assets").iterdir())), 5)
            self.assertIn('<span class="tail">look alike</span>', html)
            self.assertIn("window.__advance", html)
            self.assertIn("<b>5</b><span>pieces</span>", html)  # derived, not invented
            self.assertNotIn("http", html.split("<script>")[0].replace("http-equiv", ""))
            self.assertNotIn("__", html.replace("__ready", "").replace("__advance", "").replace("__done", "").replace("__render", ""))

    def test_refuses_overwrite_and_too_few_items(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"; out.mkdir()
            with self.assertRaises(wall.WallError):
                wall.render(self._src(d), out, "T")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(wall.WallError):
                wall.render(self._src(d, 2), Path(d) / "o", "T")

    def test_rejects_script_href_and_escapes_title(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._src(d)
            with self.assertRaises(wall.WallError):
                wall.render(src, Path(d) / "o", "T", cta_href="javascript:alert(1)", cta_label="x")
            wall.render(src, Path(d) / "o2", "<b>x</b> y")
            self.assertNotIn("<b>x</b>", (Path(d) / "o2" / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
