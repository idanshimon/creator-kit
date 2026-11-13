import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from creator_tools import bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _write(self, rel, content):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
        return p

    def test_inventory_fields_and_checksum(self):
        payload = b"hello world\n"
        self._write("notes.txt", payload)
        self._write("render.mp4", b"\x00\x00fakevideo")
        result = bundle.build(self.tmp)
        by_path = {a["path"]: a for a in result["artifacts"]}
        self.assertIn("notes.txt", by_path)
        note = by_path["notes.txt"]
        self.assertEqual(note["type"], "text")
        self.assertEqual(note["bytes"], len(payload))
        self.assertEqual(note["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertIn("T", note["mtime"])
        self.assertEqual(by_path["render.mp4"]["type"], "video")
        self.assertIn("generated_at", result)

    def test_videos_and_cover(self):
        self._write("render.mp4", b"\x00video")
        self._write("poster.png", b"\x89PNG")
        self._write("frame.png", b"\x89PNG")
        result = bundle.build(self.tmp)
        self.assertEqual([v["path"] for v in result["videos"]], ["render.mp4"])
        self.assertIn("duration", result["videos"][0])
        self.assertEqual(result["cover"], "poster.png")

    def test_cover_null_when_no_images(self):
        self._write("notes.txt", "x")
        self.assertIsNone(bundle.build(self.tmp)["cover"])

    def test_open_decisions_from_crawl(self):
        crawl = {
            "nodes": [
                {"section": "Steps", "text": "Never push to main without approval",
                 "route": "human", "scores": {"approval": 0.9}},
                {"section": "Steps", "text": "Run make test", "route": "code", "scores": {}},
            ]
        }
        self._write("crawl.json", json.dumps(crawl))
        decisions = bundle.build(self.tmp)["open_decisions"]
        human = [d for d in decisions if d["kind"] == "crawl-human-route"]
        self.assertEqual(len(human), 1)
        self.assertEqual(human[0]["section"], "Steps")
        self.assertIn("approval", human[0]["scores"])
        self.assertEqual(human[0]["source"], "crawl.json")

    def test_open_decisions_from_provenance(self):
        self._write("plan.json.provenance.json",
                    json.dumps({"operation": "metadata-only-edit-plan", "review_required": True}))
        self._write("done.json.provenance.json",
                    json.dumps({"operation": "x", "review_required": False}))
        decisions = bundle.build(self.tmp)["open_decisions"]
        prov = [d for d in decisions if d["kind"] == "provenance-review-required"]
        self.assertEqual(len(prov), 1)
        self.assertEqual(prov[0]["source"], "plan.json.provenance.json")

    def test_write_refuses_overwrite(self):
        self._write("notes.txt", "x")
        out = bundle.write_manifest(self.tmp)
        self.assertTrue(Path(out).exists())
        with self.assertRaises(FileExistsError):
            bundle.write_manifest(self.tmp)

    def test_manifest_excludes_itself(self):
        self._write("notes.txt", "x")
        bundle.write_manifest(self.tmp)
        result = bundle.build(self.tmp)
        self.assertNotIn("manifest.json", [a["path"] for a in result["artifacts"]])


if __name__ == "__main__":
    unittest.main()
