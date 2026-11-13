import json
import tempfile
import unittest
from pathlib import Path

from creator_tools import mission_control, styles

TEXT = ("ink", "muted", "faint", "accent", "critical", "concerning", "atRisk", "stable", "model", "human", "system")
SURF = ("panel", "surface", "raised", "bg")
EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "mission-control" / "finops-governance.mission.json"


class StyleLibraryTests(unittest.TestCase):
    def test_every_supported_style_meets_text_contrast_on_every_surface(self):
        listed = styles.run("list")
        self.assertGreaterEqual(listed["supported"], 70)
        names = [s["name"] for s in listed["styles"] if "unsupported" not in s]
        self.assertIn("noir", names)
        for name in names:
            st = styles.build_style(name)
            for mode, pal in st["palettes"].items():
                for t in TEXT:
                    for s in SURF:
                        r = styles.contrast(pal[t], pal[s])
                        self.assertGreaterEqual(r, 4.5, f"{name}/{mode}: {t} on {s} = {r:.2f}")
                self.assertGreaterEqual(styles.contrast(pal["onStable"], pal["stable"]), 4.5, f"{name}/{mode} approve label")

    def test_unknown_style_is_rejected(self):
        with self.assertRaises(styles.StyleError):
            styles.build_style("not-a-brand")

    def test_files_without_tokens_are_reported_not_guessed(self):
        items = {i["name"]: i for i in styles.run("list")["styles"]}
        self.assertIn("unsupported", items["kraken"])

    def test_severity_hue_is_kept(self):
        # Contrast moves lightness only; critical stays red-dominant in every style.
        for name in ("linear.app", "stripe", "claude", "nvidia"):
            for pal in styles.build_style(name)["palettes"].values():
                r, g, b = styles._hex(pal["critical"])
                self.assertGreater(r, g)
                self.assertGreater(r, b)

    def test_mission_control_render_applies_style_to_css_and_canvas(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "mc.html"
            res = mission_control.run("render", EXAMPLE, out, style_name="stripe", log=lambda m: None)
            html = out.read_text()
            self.assertEqual(res["style"], "stripe")
            self.assertEqual(res["theme"], "light")
            self.assertIn('data-theme="light"', html)
            self.assertIn("Object.assign(PALETTES.light", html)
            self.assertIn("integrations/design-md/stripe/DESIGN.md", html)
            self.assertNotIn("__STYLE_", html)

    def test_default_render_uses_native_finalized_palette(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "mc.html"
            res = mission_control.run("render", EXAMPLE, out, log=lambda m: None)
            self.assertEqual(res["style"], "mission-control")
            self.assertEqual(res["theme"], json.loads(EXAMPLE.read_text()).get("default_theme", "dark"))


if __name__ == "__main__":
    unittest.main()
