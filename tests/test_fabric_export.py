"""Offline deployment-kit contract; all work stays under TMPDIR."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


HTML = b'''<!doctype html>\r\n<html lang="en"><head><meta charset="utf-8"><style>
body { color: #123; } .off {display:none}
</style></head><body><h1>Trusted snapshot</h1><a href="https://example.org/source">Source</a>
<svg viewBox="0 0 10 10"><path d="M0 0L10 10"/></svg>
<script>document.querySelector('h1').addEventListener('click', () => document.body.classList.toggle('off'));</script>
</body></html>\r\n'''


class FabricExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        # macOS TMPDIR uses /var -> /private/var; use its canonical path.
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'story.html'
        self.source.write_bytes(HTML)
        self.out = self.root / 'kit'

    def package(self, **kwargs):
        try:
            module = importlib.import_module('creator_tools.fabric_export')
        except ModuleNotFoundError:
            self.fail('Missing deployment-kit API creator_tools.fabric_export.package_site')
        return module.package_site(self.source, self.out, **kwargs)

    def invalid(self, fragment):
        # Isolate cases so a failed refusal cannot mask later missing guards.
        self.invalid_count = getattr(self, 'invalid_count', 0) + 1
        self.out = self.root / f'invalid-{self.invalid_count}'
        self.source.write_text('<!doctype html><html><head></head><body>' + fragment + '</body></html>')
        before = self.source.read_bytes()
        with self.assertRaises(ValueError):
            self.package()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(os.path.lexists(self.out))

    def test_exact_bytes_manifest_and_only_explicit_input(self):
        (self.root / '.env').write_text('SECRET=do-not-copy')
        result = self.package()
        json.dumps(result)
        self.assertEqual(result['status'], 'local-deployment-kit')
        self.assertFalse(result['deployed'])
        self.assertEqual(result['output_dir'], str(self.out))
        self.assertEqual(self.source.read_bytes(), HTML)
        self.assertEqual((self.out / 'site/index.html').read_bytes(), HTML)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        actual = sorted(str(p.relative_to(self.out)) for p in self.out.rglob('*') if p.is_file())
        self.assertEqual(actual, ['.gitignore', 'README.md', 'manifest.json', 'package.json',
                                 'rayfin/rayfin.yml', 'scripts/build.mjs', 'site/index.html'])
        self.assertEqual(sorted(manifest['files']), sorted(set(actual) - {'manifest.json'}))
        for path, entry in manifest['files'].items():
            data = (self.out / path).read_bytes()
            self.assertEqual(entry, {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        self.assertEqual(result['manifest_sha256'], hashlib.sha256((self.out / 'manifest.json').read_bytes()).hexdigest())
        self.assertFalse((self.out / 'package-lock.json').exists())

    def test_config_pins_protected_services(self):
        self.package(app_name='evidence-story-2')
        pkg = json.loads((self.out / 'package.json').read_text())
        self.assertEqual(pkg['devDependencies'], {'@microsoft/rayfin-cli': '1.36.2'})
        self.assertEqual(pkg['name'], 'evidence-story-2')
        self.assertEqual(pkg['scripts']['build'], 'node scripts/build.mjs')
        self.assertEqual(pkg['engines']['node'], '20.x || 22.x || 24.x')
        config = (self.out / 'rayfin/rayfin.yml').read_text()
        for expected in ['id: evidence-story-2', 'fabric:\n      enabled: true',
                         'password:\n      enabled: false', 'assetAccess: protected',
                         'folder: dist', 'buildCommand: npm run build',
                         'data:\n    enabled: false', 'storage:\n    enabled: false',
                         'functions:\n    enabled: false', 'allowedRedirectUris: []']:
            self.assertIn(expected, config)
        readme = (self.out / 'README.md').read_text()
        for phrase in ['npm install', 'npx rayfin login', 'npx rayfin up --workspace-id <workspace-id>',
                       'npx rayfin up staticapp deploy', 'row-level security', 'capacity', 'region',
                       'workload', 'permissions', 'trusted', 'not deployed', 'Node 20/22/24']:
            self.assertIn(phrase, readme)
        ignore = (self.out / '.gitignore').read_text()
        for entry in ['.env', '.deployments.json', 'node_modules/', 'dist/']:
            self.assertIn(entry, ignore)

    def test_packaging_never_invokes_subprocess(self):
        with patch('subprocess.run', side_effect=AssertionError('no external calls')), \
             patch('subprocess.Popen', side_effect=AssertionError('no external calls')):
            self.package()

    def test_invalid_slug_no_partial_output(self):
        for name in ['', '../bad', 'HasCaps', 'space name', 'a;b', '-lead', 'trail-', 'a_b', 'x' * 64, None]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.package(app_name=name)
                self.assertFalse(os.path.lexists(self.out))

    def test_existing_directory_file_and_dangling_symlink_preserved(self):
        self.out.mkdir()
        marker = self.out / 'keep'
        marker.write_text('keep')
        with self.assertRaises(FileExistsError):
            self.package()
        self.assertEqual(marker.read_text(), 'keep')
        shutil.rmtree(self.out)
        self.out.write_text('keep-file')
        with self.assertRaises(FileExistsError):
            self.package()
        self.assertEqual(self.out.read_text(), 'keep-file')
        self.out.unlink()
        self.out.symlink_to(self.root / 'missing')
        with self.assertRaises(FileExistsError):
            self.package()
        self.assertTrue(self.out.is_symlink())

    def test_platform_tmpdir_alias_is_supported(self):
        # macOS /var is a platform alias; nested TMPDIR paths must work as-is.
        self.out = Path(self.temp.name) / 'kit'
        self.package()
        self.assertEqual((self.out / 'site/index.html').read_bytes(), HTML)

    def test_missing_directory_input_and_symlink_input(self):
        self.source.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.package()
        self.source.mkdir()
        with self.assertRaises(ValueError):
            self.package()
        self.source.rmdir()
        target = self.root / 'target.html'
        target.write_bytes(HTML)
        self.source.symlink_to(target)
        with self.assertRaises(ValueError):
            self.package()
        self.assertFalse(self.out.exists())

    def test_output_under_symlink_parent_refused(self):
        real = self.root / 'real'
        real.mkdir()
        link = self.root / 'link'
        link.symlink_to(real, target_is_directory=True)
        self.out = link / 'kit'
        with self.assertRaises(ValueError):
            self.package()
        self.assertFalse((real / 'kit').exists())

    def test_external_relative_runtime_dependencies_refused(self):
        cases = ['<script src="https://cdn.test/a.js"></script>', '<script src="./a.js"></script>',
                 '<link rel="stylesheet" href="a.css">', '<link rel="preconnect" href="https://x.test">',
                 '<img src="pic.png">', '<img srcset="data:image/png;base64,YQ== 1x, https://x.test/a 2x">',
                 '<iframe src="data:text/html,hi"></iframe>', '<object data="a.pdf"></object>',
                 '<embed src="a.pdf">', '<video poster="poster.png"></video>', '<audio src="a.mp3"></audio>',
                 '<svg><image href="picture.svg"/></svg>', '<svg><use xlink:href="a.svg#x"/></svg>',
                 '<div style="background:url(//x.test/a)"></div>', '<style>@import "a.css";</style>',
                 '<style>p{background:URL(\'../a.png\')}</style>', '<base href="https://x.test">',
                 '<meta http-equiv="refresh" content="0;url=https://x.test">',
                 '<form action="https://x.test"><input type="submit"></form>',
                 '<a href="https://example.org" ping="https://x.test">source</a>',
                 '<img src="data:image/svg+xml,%3Csvg%20onload=alert(1)%3E">']
        for case in cases:
            with self.subTest(case=case):
                self.invalid(case)

    def test_obvious_inline_network_and_dynamic_loaders_refused(self):
        cases = ['fetch("https://x.test")', 'window.fetch("/api")', 'new XMLHttpRequest()',
                 'new WebSocket("wss://x.test")', 'navigator.sendBeacon("/log", "x")',
                 'import("./module.js")', 'import x from "./module.js";',
                 'new EventSource("/events")', 'new Worker("worker.js")',
                 'document.createElement("script")', 'location.href = "https://x.test"',
                 'window.open("https://x.test")', 'eval("fetch(1)")']
        for code in cases:
            with self.subTest(code=code):
                self.invalid('<script>' + code + '</script>')
        self.invalid('<button onclick="fetch(\'/api\')">Go</button>')

    def test_additional_obvious_runtime_loaders_refused(self):
        for code in ['export { value } from "./module.js";',
                     'navigator.serviceWorker.register("./sw.js")',
                     'new Image().src = "https://x.test/tracker"',
                     'document.write("<img src=https://x.test/tracker>")']:
            with self.subTest(code=code):
                self.invalid('<script type="module">' + code + '</script>')
        for fragment in ['<style>p{background:image-set("https://x.test/a.png" 1x)}</style>',
                         '<svg><image id="pic"/><set href="#pic" attributeName="href" to="https://x.test/a"/></svg>']:
            with self.subTest(fragment=fragment):
                self.invalid(fragment)

    def test_embedded_raster_and_fragment_sources_allowed(self):
        self.source.write_text('<!doctype html><html><body><img src="data:image/png;base64,YQ==">'
                               '<style>p{background:url(data:image/png;base64,YQ==)}</style>'
                               '<svg><use href="#shape"/></svg><a href="#figure">Figure</a></body></html>')
        self.package()

    def test_offline_csp_meta_is_supported(self):
        self.source.write_bytes(HTML.replace(b'<meta charset="utf-8">',
            b'<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
            b'content="default-src \'none\'; script-src \'unsafe-inline\'; connect-src \'none\'">'))
        self.package()
        self.assertEqual((self.out / 'site/index.html').read_bytes(), self.source.read_bytes())

    def test_csp_reporting_dependency_refused(self):
        self.invalid('<meta http-equiv="Content-Security-Policy" content="report-uri https://x.test">')

    def test_invalid_html_encoding_and_empty_input(self):
        for data in [b'', b'not HTML', b'<html><body>\xff</body></html>']:
            self.source.write_bytes(data)
            with self.assertRaises(ValueError):
                self.package()
            self.assertFalse(self.out.exists())

    def node(self):
        node = shutil.which('node')
        if node is None:
            self.fail('Node required for executable local build acceptance')
        return subprocess.run([node, str(self.out / 'scripts/build.mjs')], cwd=self.root,
                              text=True, capture_output=True)

    def test_node_build_exact_bytes_and_no_secrets(self):
        self.package()
        (self.out / '.env').write_text('SECRET=do-not-copy')
        result = self.node()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SHA256 verified', result.stdout)
        self.assertEqual((self.out / 'dist/index.html').read_bytes(), HTML)
        self.assertEqual([p.name for p in (self.out / 'dist').iterdir()], ['index.html'])
        self.assertFalse((self.out / 'node_modules').exists())

    def test_tampered_site_fails_before_dist_mutation(self):
        self.package()
        self.assertEqual(self.node().returncode, 0)
        before = (self.out / 'dist/index.html').read_bytes()
        (self.out / 'site/index.html').write_bytes(HTML + b'changed')
        result = self.node()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('integrity', result.stderr.lower())
        self.assertEqual((self.out / 'dist/index.html').read_bytes(), before)

    def test_extra_site_and_symlink_build_boundaries(self):
        self.package()
        (self.out / 'site/.env').write_text('SECRET')
        self.assertNotEqual(self.node().returncode, 0)
        self.assertFalse((self.out / 'dist').exists())
        (self.out / 'site/.env').unlink()
        (self.out / 'site/index.html').unlink()
        (self.out / 'site/index.html').symlink_to(self.source)
        self.assertNotEqual(self.node().returncode, 0)
        self.assertFalse((self.out / 'dist').exists())

    def test_dist_symlink_refused(self):
        self.package()
        external = self.root / 'external'
        external.mkdir()
        (external / 'keep').write_text('keep')
        (self.out / 'dist').symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.node().returncode, 0)
        self.assertEqual((external / 'keep').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
