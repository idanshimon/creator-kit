import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from creator_tools import mission_ask, mission_control

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mission-control" / "finops-governance.mission.json"


class FakeRun:
    """Stands in for subprocess.run; records argv and replies with Copilot JSONL events."""
    def __init__(self, answer="Sudeep leads AI. Source: `notes/people.md`.", code=0):
        self.answer, self.code, self.argv = answer, code, None

    def __call__(self, argv, **kw):
        self.argv, self.kw = argv, kw
        ev = [{"type": "tool.execution_start", "data": {"toolName": "workiq-ask_work_iq", "arguments": {"question": "q"}}},
              {"type": "assistant.message", "data": {"content": self.answer}}]
        return subprocess.CompletedProcess(argv, self.code, "\n".join(json.dumps(e) for e in ev), "")


class MissionAskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mc_ask_"))
        (self.tmp / "repo" / "cust" / "notes").mkdir(parents=True)
        (self.tmp / "repo" / "data").mkdir()
        (self.tmp / "repo" / "secret.md").write_text("nope")
        (self.tmp / "repo" / "cust" / "notes" / "people.md").write_text("# People")
        (self.tmp / "repo" / "data" / "cited.md").write_text("# Cited")
        spec = json.loads(EXAMPLE.read_text())
        spec["entities"][0]["detail"] = {"evidence": [{"label": "data/cited.md"}]}
        self.spec = self.tmp / "spec.json"
        self.spec.write_text(json.dumps(spec))
        self.page = self.tmp / "page.html"
        self.page.write_text(mission_control.render_html(spec))
        self.cfg = mission_ask.AskConfig(self.page, self.spec, self.tmp / "repo", ["cust"], copilot="copilot")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cited_files_are_added_and_scope_is_enforced(self):
        self.assertEqual([self.cfg.rel(f) for f in self.cfg.extra_files], ["data/cited.md"])
        self.assertIsNotNone(self.cfg.resolve_source("notes/people.md"))
        self.assertIsNotNone(self.cfg.resolve_source("data/cited.md"))
        self.assertIsNone(self.cfg.resolve_source("secret.md"))
        self.assertIsNone(self.cfg.resolve_source("../../etc/passwd"))
        with self.assertRaises(ValueError):
            mission_ask.AskConfig(self.page, self.spec, self.tmp / "repo", ["../"])

    def test_argv_is_read_only_and_prompt_is_one_argv_element(self):
        fake = FakeRun()
        res = mission_ask.run_ask(self.cfg, 'who? "; rm -rf / #', {"id": self.cfg.spec["entities"][0]["id"]}, runner=fake)
        argv = fake.argv
        self.assertIn("-p", argv)
        prompt = argv[argv.index("-p") + 1]
        self.assertIn('who? "; rm -rf / #', prompt)
        self.assertIn("DASHBOARD SPEC", prompt)
        self.assertIn("not in record", prompt)
        self.assertIn(self.cfg.spec["entities"][0]["id"], prompt.split("CURRENTLY SELECTED ITEM ON SCREEN:")[1][:200])
        tools = argv[argv.index("--available-tools") + 1:argv.index("--available-tools") + 5]
        self.assertEqual(tools, ["view", "grep", "glob", "workiq-ask_work_iq"])
        for bad in ("--allow-all", "--yolo", "--allow-all-tools", "--allow-all-paths", "bash", "edit", "write"):
            self.assertNotIn(bad, argv)
        self.assertEqual(argv[argv.index("-C") + 1], str(self.cfg.context_dirs[0]))
        self.assertIn(str((self.tmp / "repo" / "data").resolve()), argv)  # --add-dir for the cited file only
        self.assertNotIn("shell", fake.kw)
        self.assertEqual(res["tools"][0]["name"], "workiq-ask_work_iq")
        self.assertEqual(res["sources"][0]["label"], "cust/notes/people.md")

    def test_cli_error_is_reported_not_faked(self):
        res = mission_ask.run_ask(self.cfg, "q", None, runner=FakeRun(answer="", code=1))
        self.assertIn("Copilot CLI exit 1", res["error"])

    def test_server_checks_host_origin_and_header(self):
        holder = {}
        t = threading.Thread(target=mission_ask.serve, args=(self.cfg,),
                             kwargs={"log": lambda m: None, "ready": lambda h, u: holder.update(h=h, u=u)}, daemon=True)
        t.start()
        for _ in range(50):
            if "u" in holder:
                break
            threading.Event().wait(0.05)
        url = holder["u"]
        try:
            with urllib.request.urlopen(url + "ask/health") as r:
                self.assertTrue(json.load(r)["ok"])
            with urllib.request.urlopen(url) as r:
                self.assertIn("Content-Security-Policy", r.headers)

            def post(headers):
                req = urllib.request.Request(url + "ask", data=b'{"question":"x"}', method="POST",
                                             headers={"Content-Type": "application/json", **headers})
                try:
                    return urllib.request.urlopen(req).status
                except urllib.error.HTTPError as e:
                    return e.code
            self.assertEqual(post({"X-MC-Ask": "1"}), 403)                              # no Origin
            self.assertEqual(post({"X-MC-Ask": "1", "Origin": "http://evil.test"}), 403)
            self.assertEqual(post({"Origin": url.rstrip("/")}), 403)                    # no custom header
            req = urllib.request.Request(url + "ask/health", headers={"Host": "evil.test"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 421)
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(url + "src?p=secret.md")
            self.assertEqual(holder["h"].server_address[0], "127.0.0.1")
        finally:
            holder["h"].shutdown()


if __name__ == "__main__":
    unittest.main()
