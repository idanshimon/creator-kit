"""Exercise the actual CLI, not a mock adapter or a generated command string."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FabricCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'creator.py'), *args], cwd=ROOT, capture_output=True, text=True)

    def test_fabric_package_help_is_discoverable(self):
        p = self.run_cli('fabric', 'package', '--help')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('--input', p.stdout)
        self.assertIn('--output', p.stdout)
        self.assertIn('--name', p.stdout)

    def test_cli_packages_explicit_html_without_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'story.html'
            source.write_text('<!doctype html><html><head><title>Synthetic fixture</title></head><body><h1>Local test</h1></body></html>')
            target = base / 'fabric-kit'
            p = self.run_cli('fabric', 'package', '--input', str(source), '--output', str(target), '--name', 'test-story')
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIsInstance(json.loads(p.stdout), dict)
            self.assertEqual((target / 'site/index.html').read_bytes(), source.read_bytes())
            self.assertTrue((target / 'rayfin/rayfin.yml').is_file())
            again = self.run_cli('fabric', 'package', '--input', str(source), '--output', str(target), '--name', 'test-story')
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((target / 'site/index.html').read_bytes(), source.read_bytes())

    def test_missing_source_is_clean_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'kit'
            p = self.run_cli('fabric', 'package', '--input', str(Path(tmp) / 'missing.html'), '--output', str(target))
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn('Traceback', p.stderr)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
