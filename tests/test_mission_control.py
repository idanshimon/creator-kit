import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from creator_tools import mission_control

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mission-control" / "finops-governance.mission.json"


class MissionControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mc_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cli_discoverable(self):
        p = subprocess.run(
            [sys.executable, str(ROOT / "creator.py"), "mission-control", "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("validate", p.stdout)
        self.assertIn("render", p.stdout)

    def test_validate_and_render_example_spec(self):
        v = mission_control.run("validate", EXAMPLE)
        self.assertTrue(v["ok"])
        self.assertEqual(v["sectors"], 3)
        self.assertEqual(v["entities"], 12)
        self.assertEqual(v["beats"], 7)

        out = self.tmp / "finops.html"
        r = mission_control.run("render", EXAMPLE, out, dwell_ms=1000)
        self.assertTrue(r["ok"])
        html = out.read_text(encoding="utf-8")
        self.assertIn("Agentic FinOps &amp; Cloud Reliability", html)
        self.assertIn("window.__advance", html)
        self.assertIn("WKL-014", html)
        with self.assertRaises(FileExistsError):
            mission_control.run("render", EXAMPLE, out)

    def test_rejects_unknown_sector_or_invalid_stage(self):
        bad = json.loads(EXAMPLE.read_text())
        bad["entities"][0]["sector"] = "nonexistent-sector"
        bad_path = self.tmp / "bad.json"
        bad_path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, "unknown sector"):
            mission_control.run("validate", bad_path)

        bad2 = json.loads(EXAMPLE.read_text())
        bad2["entities"][0]["stage"] = "catastrophic"
        bad_path.write_text(json.dumps(bad2))
        with self.assertRaisesRegex(ValueError, "stage"):
            mission_control.run("validate", bad_path)


if __name__ == "__main__":
    unittest.main()


def test_lint_flags_phone_overflow_and_vague_values():
    from creator_tools import mission_control as mc
    spec = {"title": "BreakingTrades · Agent Ops", "banner": "Real GitHub data · fetched 2026-11-06T16:21Z",
            "agent": {"model": "Copilot (triage + coding agent)"},
            "sectors": [{"id": "u", "label": "Unclassified items"}],
            "entities": [{"id": "#1", "sector": "u", "label": "A very long issue title that will not fit a phone row",
                          "summary": "see https://github.com/x/y/actions/runs/1",
                          "watchers": [{"key": "triage", "value": "unleveled"}]}]}
    w = " | ".join(mc.lint_spec(mc.validate_spec(spec)))
    for needle in ("BreakingTrades", "banner", "agent.model", "sector 'u'", "label is", "URL", "hides the reason"):
        assert needle in w, needle


def test_lint_is_quiet_for_the_shipped_example():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    assert [x for x in mc.lint_spec(mc.validate_spec(spec)) if "title word" in x or "URL" in x] == []


def test_attention_cue_and_reduced_motion_are_rendered():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    html = mc.render_html(mc.validate_spec(spec))
    for needle in ("function attentionRing", "prefers-reduced-motion", "needs-you", "navigator.vibrate", "overflow-wrap: anywhere"):
        assert needle in html, needle
    assert "ctx.fillRect(lx - tw / 2" not in html  # watcher labels are themed chips, not panel rectangles


def test_detail_contract_validates_and_drops_unsafe_urls():
    import json
    from pathlib import Path
    import pytest
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    e = spec["entities"][0]
    e["detail"] = {"title": "Full title", "why_you": "Level 2 needs you.",
                   "decision": {"question": "Ship it?", "options": [{"label": "Yes", "url": "javascript:alert(1)", "recommended": True},
                                                                    {"label": "No", "url": "https://example.org/x"}]},
                   "sections": [{"title": "Found", "items": ["a", "b"]}], "timeline": [{"t": "11-06 15:00", "text": "opened"}],
                   "evidence": [{"label": "run 1", "url": "https://example.org/run/1"}]}
    e["watchers"][0]["detail"] = {"text": "why this watcher", "url": "https://example.org/w"}
    norm = mc.validate_spec(spec)
    d = norm["entities"][0]["detail"]
    assert d["decision"]["options"][0]["url"] is None and d["decision"]["options"][1]["url"] == "https://example.org/x"
    assert norm["entities"][0]["watchers"][0]["detail"]["url"] == "https://example.org/w"
    bad = json.loads(json.dumps(spec)); bad["entities"][0]["detail"] = {"decision": {"options": []}}
    with pytest.raises(ValueError):
        mc.validate_spec(bad)
    html = mc.render_html(norm)
    for needle in ('id="mc-sheet"', "function openEntity", "What can I click?", "const esc ="):
        assert needle in html


def test_critical_without_decision_context_is_flagged():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    crit = [e for e in spec["entities"] if e.get("stage") == "critical"]
    for e in crit:
        e.pop("detail", None)
    w = mc.lint_spec(mc.validate_spec(spec))
    assert all(any(f"entity {e['id']} is critical" in x for x in w) for e in crit)


def test_worklist_score_never_wraps():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    html = mc.render_html(mc.validate_spec(spec))
    assert 'class="entity-score"' in html and "white-space:nowrap;flex:none" in html  # "89." / "0" split seen in a narrow rail


def test_critical_ring_clears_beat_dial_labels():
    import json, re
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    html = mc.render_html(mc.validate_spec(spec))
    crit = float(re.search(r"STAGE_RING = \{critical: ([0-9.]+)", html).group(1))
    assert crit - 0.025 >= 0.36  # hub R0 = 0.20*M, labels at R0+14px; 0.33 overlapped "1 Change"/"7 Prove"


def test_no_filler_brand_subtitle():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    assert "DECISION SUPPORT" not in mc.render_html(mc.validate_spec(spec)).upper()  # owner: says nothing


def test_decision_endpoint_is_same_origin_path_only():
    import json
    from pathlib import Path
    from creator_tools import mission_control as mc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/mission-control/finops-governance.mission.json").read_text())
    e = spec["entities"][0]
    e["detail"] = {"decision": {"question": "Q?", "endpoint": "/owner/decide", "url": "https://github.com/x/y/issues/1",
                                "options": [{"label": "Approve", "value": "approve"}, {"label": "Bad", "value": "Bad Value!"}]}}
    d = mc.validate_spec(spec)["entities"][0]["detail"]["decision"]
    assert d["endpoint"] == "/owner/decide" and d["url"].startswith("https://")
    assert d["options"][0]["value"] == "approve" and d["options"][1]["value"] == ""
    e["detail"]["decision"]["endpoint"] = "https://evil.example/steal"
    assert mc.validate_spec(spec)["entities"][0]["detail"]["decision"]["endpoint"] is None
    assert "function wireDecision" in mc.render_html(mc.validate_spec(spec))


class MissionControlBriefTests(unittest.TestCase):
    def _spec(self):
        return json.loads(EXAMPLE.read_text())

    def test_brief_optional_and_validated(self):
        spec = self._spec()
        self.assertIsNone(mission_control.validate_spec(spec)["brief"])
        eid = spec["entities"][0]["id"]
        spec["brief"] = {"lead": "Recorded call", "items": [
            {"label": "Before 9:00", "text": "Open diagrams", "entity": eid, "tone": "warn"},
            {"label": "Patterns", "lines": ["one", "two"]}]}
        norm = mission_control.validate_spec(spec)
        self.assertEqual(norm["brief"]["items"][0]["entity"], eid)
        self.assertEqual(norm["brief"]["items"][1]["lines"], ["one", "two"])
        spec["brief"]["items"][0]["entity"] = "NOPE"
        with self.assertRaises(ValueError):
            mission_control.validate_spec(spec)

    def test_brief_rendered_as_text_and_phone_topbar_wraps(self):
        spec = self._spec()
        spec["brief"] = {"lead": "<b>x</b>", "items": [{"label": "L", "text": "<script>alert(1)</script>"}]}
        html = mission_control.render_html(spec)
        self.assertIn('id="brief"', html)
        self.assertNotIn("<script>alert(1)</script>", html)  # embedded JSON escapes </ ; DOM uses textContent
        self.assertIn(".topbar { flex-wrap: wrap;", html)
        self.assertIn("lw / 2 + 6", html)  # sector labels clamped inside the canvas


class MissionControlStageSizeTests(unittest.TestCase):
    def test_canvas_tracks_stage_size(self):
        html = mission_control.render_html(json.loads(EXAMPLE.read_text()))
        self.assertIn("new ResizeObserver(", html)


class ThemedScrollbarTests(unittest.TestCase):
    def test_every_scroll_region_uses_theme_tokens_in_both_themes(self):
        html = mission_control.render_html(json.loads(EXAMPLE.read_text()))
        self.assertIn('[data-theme="dark"] { color-scheme: dark; }', html)
        self.assertIn('[data-theme="light"] { color-scheme: light; }', html)
        # Universal selector covers page, rails, worklist, detail sheet and the Ask log.
        self.assertIn("* { scrollbar-width: thin; scrollbar-color: var(--mc-scroll-thumb) var(--mc-scroll-track); }", html)
        self.assertIn("html { scrollbar-color: var(--mc-scroll-thumb) var(--mc-surface); }", html)
        self.assertIn("::-webkit-scrollbar-thumb { background: var(--mc-scroll-thumb)", html)
        self.assertRegex(html, r"--mc-scroll-thumb: color-mix\(in srgb, var\(--mc-faint\)")
        styled = mission_control.render_html(json.loads(EXAMPLE.read_text()),
                                             style=__import__("creator_tools.styles", fromlist=["x"]).build_style("linear.app"))
        self.assertIn("color-scheme: dark", styled)


class AskPaneTemplateTests(unittest.TestCase):
    def test_pane_is_present_and_disabled_without_server(self):
        html = mission_control.render_html(json.loads(EXAMPLE.read_text()))
        self.assertIn('id="btn-ask"', html)
        self.assertIn('id="mc-ask-q" aria-label="Your question" placeholder="Ask about this account…" disabled', html)
        self.assertIn("Ask is off: this page was opened as a file", html)
        self.assertIn("window.__mcSelected", html)
        self.assertIn("'X-MC-Ask': '1'", html)
