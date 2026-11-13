import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from creator_tools import pipeline_control as pc

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "pipeline-control" / "checkout-service.pipeline.json"


def spec():
    return json.loads(EXAMPLE.read_text())


class PipelineControlTests(unittest.TestCase):
    def test_example_validates_and_finds_the_slow_stage(self):
        res = pc.run("validate", EXAMPLE)
        self.assertEqual(res["runs"], 416)
        self.assertEqual(res["figures"]["stage"]["status"], "worse")
        self.assertEqual(res["figures"]["cost"]["status"], "worse")
        data = pc.derive(pc.validate_spec(spec()))
        self.assertEqual(data["focus"], "integ")

    def test_flow_line_cards_and_agent_evidence_agree(self):
        data = pc.derive(pc.validate_spec(spec()))
        stage = next(s for s in data["stages"] if s["id"] == data["focus"])
        fig = data["figures"][0]
        self.assertEqual(stage["base"], fig["ref"])
        self.assertEqual(stage["latest"], fig["latest"])
        self.assertIn(f"{fig['ref']:.1f} min", data["derivedEvidence"][0])
        cost = data["figures"][1]
        self.assertAlmostEqual(cost["weeklyExtra"], round((cost["latest"] - cost["ref"]) * cost["runsPerDay"] * 7, 2))

    def test_cost_is_rate_times_runner_minutes(self):
        s = spec()
        s["runs"] = [{"id": "a", "date": "2026-01-01", "status": "passed", "stage_minutes": {"commit": 1, "build": 9}},
                     {"id": "b", "date": "2026-01-02", "status": "passed", "stage_minutes": {"commit": 1, "build": 19}}]
        s["runner_rate_usd_per_min"] = 0.01
        s["baseline"] = {"until": "2026-01-01"}
        cost = next(f for f in pc.derive(pc.validate_spec(s))["figures"] if f["id"] == "cost")
        self.assertEqual(cost["values"], [0.1, 0.2])
        self.assertEqual((cost["ref"], cost["latest"], cost["status"]), (0.1, 0.2, "worse"))

    def test_fixed_baseline_does_not_drift_and_rolling_is_labelled(self):
        s = spec()
        fixed = pc.derive(pc.validate_spec(s))["figures"][0]
        self.assertEqual(fixed["refMode"], "fixed")
        self.assertIn("up to Nov 3", fixed["refLabel"])
        del s["baseline"]
        rolling = pc.derive(pc.validate_spec(s))["figures"][0]
        self.assertEqual((rolling["refMode"], rolling["refLabel"]), ("rolling", "previous 7 days"))

    def test_queue_is_derived_from_waiting_runs(self):
        data = pc.derive(pc.validate_spec(spec()))
        self.assertEqual(data["queue"], {"integ": 6})

    def test_extra_views_are_derived_and_consistent(self):
        data = pc.derive(pc.validate_spec(spec()))
        v = data["volume"]
        for i in range(len(v["reach"]) - 1):
            self.assertEqual(v["reach"][i] - v["drop"][i], v["reach"][i + 1])
        self.assertIn("Security scan", v["headline"])
        self.assertEqual(len(v["runs"]), v["reach"][0])
        stops = [r["stop"] for r in v["runs"]]
        for i, n in enumerate(v["drop"]):
            self.assertEqual(stops.count(i), n)
        self.assertEqual(len(v["reachPrev"]), len(v["reach"]))
        w = data["waterfall"]
        self.assertAlmostEqual(w["total"], round(sum(r["actual"] or 0 for r in w["rows"]), 1), places=1)
        self.assertIn("Integration", w["headline"])
        h = data["heat"]
        self.assertEqual(data["days"][h["changeDay"]], "Nov 4")
        self.assertEqual(len(h["rows"]), 8)

    def test_rejects_bad_input(self):
        bad = [
            lambda s: s.pop("runs"),
            lambda s: s.update(runner_rate_usd_per_min=-1),
            lambda s: s["runs"][0]["stage_minutes"].update(nope=1),
            lambda s: s["runs"][0].update(status="failed", failed_stage=None),
            lambda s: s.update(baseline={"until": "2030-01-01"}),
            lambda s: s["live"]["runs"].append({"stage": "nope", "state": "running"}),
            lambda s: s["agent"].update(stage="nope"),
        ]
        for mutate in bad:
            s = copy.deepcopy(spec())
            mutate(s)
            with self.assertRaises(ValueError):
                pc.validate_spec(s)

    def test_render_escapes_text_and_refuses_overwrite(self):
        s = spec()
        s["agent"]["finding"] = "<script>alert(1)</script>"
        s["live"]["runs"][0]["message"] = "</script><b>x"
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "s.json"
            src.write_text(json.dumps(s))
            out = Path(d) / "p.html"
            res = pc.run("render", src, out, style_name="linear.app")
            h = out.read_text()
            self.assertNotIn("<script>alert(1)", h)
            self.assertNotIn("</script><b>", h)
            self.assertEqual(res["style"], "linear.app")
            self.assertIn('data-theme="dark"', h)
            self.assertEqual(len(re.findall(r"<script", h)), 2)
            with self.assertRaises(FileExistsError):
                pc.run("render", src, out)


if __name__ == "__main__":
    unittest.main()


def test_cards_give_press_feedback_and_custom_titles():
    import json
    from pathlib import Path
    from creator_tools import pipeline_control as pc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/pipeline-control/checkout-service.pipeline.json").read_text())
    spec["figure_titles"] = {"lead": "Ask to reply"}
    spec["agent"]["badge"] = "Owner review waiting"
    html = pc.render_html(pc.validate_spec(spec))
    for needle in ("function pulse", "navigator.vibrate", ".pc-pulse", "show where this is on the flow line", "Ask to reply", "Owner review waiting"):
        assert needle in html, needle
    assert "Commit to production" not in html


def test_unreached_stage_is_not_zero():
    import json
    from pathlib import Path
    from creator_tools import pipeline_control as pc
    spec = json.loads((Path(__file__).resolve().parents[1] / "examples/pipeline-control/checkout-service.pipeline.json").read_text())
    spec["stages"].append({"id": "never", "name": "Never"})
    data = pc.derive(pc.validate_spec(spec))
    st = next(s for s in data["stages"] if s["id"] == "never")
    assert st["latest"] is None and st["base"] is None
