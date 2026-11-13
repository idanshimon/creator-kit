"""Bounded Archify adapter tests; real rendering runs when vendor is installed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DiagramTests(unittest.TestCase):
    def adapter(self):
        self.assertIsNotNone(importlib.util.find_spec('creator_tools.diagrams'),
                             'The diagram adapter is not implemented')
        from creator_tools import diagrams
        return diagrams

    def test_cli_command_is_discoverable(self):
        p = subprocess.run([sys.executable, str(ROOT/'creator.py'), 'diagram', '--help'],
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('install', p.stdout)
        self.assertIn('render', p.stdout)

    def test_environment_excludes_credentials_and_node_injection(self):
        d = self.adapter()
        with patch.dict(os.environ, {'FAKE_API_KEY': 'test-value', 'NODE_OPTIONS': '--bad',
                                     'ARCHIFY_UPDATE_CHECK_DISABLED': '0', 'ARCHIFY_REPO_ROOT': '/bad'}):
            env = d.child_environment()
        self.assertEqual(env['ARCHIFY_UPDATE_CHECK_DISABLED'], '1')
        for key in ['FAKE_API_KEY', 'NODE_OPTIONS', 'ARCHIFY_REPO_ROOT']:
            self.assertNotIn(key, env)

    def test_install_rejects_wrong_digest_without_creating_vendor(self):
        d = self.adapter()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            archive = root/'bad.zip'
            archive.write_bytes(b'not the approved release')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                d.install(archive, root=root)
            self.assertFalse((root/'archify').exists())

    def test_install_preserves_existing_vendor(self):
        d = self.adapter()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root/'archify').mkdir()
            marker = root/'archify/keep.txt'
            marker.write_text('keep')
            with self.assertRaises(FileExistsError):
                d.install(root/'absent.zip', root=root)
            self.assertEqual(marker.read_text(), 'keep')

    def test_missing_vendor_has_setup_guidance(self):
        d = self.adapter()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(RuntimeError, 'diagram install'):
                d.verify_install(Path(t))

    def test_brand_network_forms_rejected(self):
        d = self.adapter()
        for brand in [{'url': 'https://example.com/logo.png'}, 'https://example.com', '//example.com']:
            with self.subTest(brand=brand), self.assertRaisesRegex(ValueError, 'brand'):
                d.reject_remote_brands({'components': [{'brand': brand}]})
        d.reject_remote_brands({'components': [{'brand': 'python'}]})

    @unittest.skipUnless((ROOT/'archify/bin/archify.mjs').is_file(), 'Install pinned Archify for real render tests')
    def test_real_render_validation_and_no_overwrite(self):
        d = self.adapter()
        source = ROOT/'examples/diagrams/creator-kit.architecture.json'
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)/'new.html'
            result = d.run('render', source, target)
            self.assertTrue(result['ok'])
            self.assertIn('<svg', target.read_text())
            self.assertIn('Creator Kit', target.read_text())
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                d.run('render', source, target)
            self.assertEqual(before, target.read_bytes())
            self.assertTrue(d.run('validate', source)['ok'])
            bridged = Path(t)/'bridged.html'
            res_b = d.run('render', source, bridged, showcase_bridge=True, chapter_dwell_ms=1200)
            self.assertTrue(res_b['showcase_bridge'])
            html_b = bridged.read_text()
            self.assertIn('creator-showcase-bridge', html_b)
            self.assertIn('window.__advance', html_b)

    @unittest.skipUnless((ROOT/'archify/bin/archify.mjs').is_file(), 'Install pinned Archify for real render tests')
    def test_invalid_input_leaves_no_final_output(self):
        d = self.adapter()
        with tempfile.TemporaryDirectory() as t:
            source = Path(t)/'bad.json'
            source.write_text(json.dumps({'diagram_type': 'architecture', 'components': []}))
            target = Path(t)/'bad.html'
            with self.assertRaises((ValueError, RuntimeError)):
                d.run('render', source, target)
            self.assertFalse(target.exists())

    @unittest.skipUnless((ROOT/'archify/bin/archify.mjs').is_file(), 'Install pinned Archify for integrity tests')
    def test_tampered_install_rejected(self):
        import shutil
        d = self.adapter()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            shutil.copytree(ROOT/'archify', root/'archify')
            (root/'archify/bin/archify.mjs').write_text('// changed')
            with self.assertRaisesRegex(RuntimeError, 'integrity'):
                d.verify_install(root)


if __name__ == '__main__':
    unittest.main()
