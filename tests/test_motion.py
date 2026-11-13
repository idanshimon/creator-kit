import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
motion: Any
try:
    motion = importlib.import_module('creator_tools.motion')
except ModuleNotFoundError:
    motion = None


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(motion, 'GSAP motion feature has not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        package = self.root / 'vendor/gsap'
        (package / 'dist').mkdir(parents=True)
        # Intentional tiny fixture; browser/render verification uses the real bundle.
        self.runtime = package / 'dist/gsap.min.js'
        self.runtime.write_text('/*! GSAP fixture; retain this notice */\nwindow.gsap={};')
        self.meta = package / 'package.json'
        self.meta.write_text(json.dumps({'version': '3.15.0'}))
        (self.root / 'integrations').mkdir()
        self.lock = self.root / 'integrations/gsap-lock.json'
        self.lock.write_text(json.dumps({
            'version': '3.15.0', 'runtime_sha256': hashlib.sha256(self.runtime.read_bytes()).hexdigest(),
            'runtime_candidates': ['vendor/gsap/dist/gsap.min.js'],
            'license_url': 'https://gsap.com/standard-license/',
        }))

    def test_doctor_checks_version_and_digest(self):
        report = motion.doctor(root=self.root)
        self.assertEqual(report['version'], '3.15.0')
        self.assertTrue(report['integrity_verified'])

    def test_missing_bundle_fails(self):
        self.runtime.unlink()
        with self.assertRaisesRegex(ValueError, 'missing|not found|unavailable'):
            motion.doctor(root=self.root)

    def test_modified_bundle_fails(self):
        self.runtime.write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'checksum|integrity'):
            motion.doctor(root=self.root)

    def test_wrong_version_fails(self):
        self.meta.write_text('{"version":"0.0.1"}')
        with self.assertRaisesRegex(ValueError, 'version'):
            motion.doctor(root=self.root)

    def test_create_embeds_runtime_and_escapes_copy(self):
        result = motion.create(self.root/'new', '<script>alert(1)</script>', 'A & B', root=self.root)
        text = Path(result['html']).read_text()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', text)
        self.assertIn('A &amp; B', text)
        self.assertIn('GSAP fixture; retain this notice', text)
        self.assertNotIn('<script>alert(1)</script>', text)
        self.assertNotIn('<script src=', text)
        self.assertEqual(result['duration_seconds'], 8)
        self.assertTrue((self.root/'new/manifest.json').is_file())
        self.assertIn('https://gsap.com/standard-license/', (self.root/'new/GSAP-LICENSE.txt').read_text())

    def test_existing_directory_is_preserved(self):
        destination=self.root/'existing'
        destination.mkdir()
        marker=destination/'keep.txt'
        marker.write_text('untouched')
        with self.assertRaises(FileExistsError):
            motion.create(destination, 'Title', root=self.root)
        self.assertEqual(marker.read_text(),'untouched')

    def test_existing_file_is_preserved(self):
        destination=self.root/'file'
        destination.write_text('untouched')
        with self.assertRaises(FileExistsError):
            motion.create(destination, 'Title', root=self.root)
        self.assertEqual(destination.read_text(),'untouched')

    def test_invalid_copy_does_not_create_destination(self):
        for value in ['', '  ', 'x'*121, 'bad\x00title', 'line\nbreak']:
            with self.subTest(value=repr(value)):
                destination=self.root/'invalid'
                with self.assertRaises(ValueError):
                    motion.create(destination,value,root=self.root)
                self.assertFalse(destination.exists())

    def test_invalid_subtitle_is_rejected(self):
        for value in ['x'*241, 'bad\x00subtitle', None]:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    motion.create(self.root/'invalid-subtitle','Title',value,root=self.root)

    def test_failed_integrity_has_no_output_side_effects(self):
        self.runtime.write_text('tampered')
        with self.assertRaises(ValueError):
            motion.create(self.root/'not-created','Title',root=self.root)
        self.assertFalse((self.root/'not-created').exists())

    def test_script_endings_cannot_escape_inline_runtime(self):
        self.runtime.write_text('/*! GSAP */ window.test="</script>";')
        data=json.loads(self.lock.read_text())
        data['runtime_sha256']=hashlib.sha256(self.runtime.read_bytes()).hexdigest()
        self.lock.write_text(json.dumps(data))
        result=motion.create(self.root/'escaped','Title',root=self.root)
        self.assertNotIn('window.test="</script>"',Path(result['html']).read_text())


class MotionCliTests(unittest.TestCase):
    def test_cli_exposes_motion_actions(self):
        result=subprocess.run([sys.executable,str(ROOT/'creator.py'),'motion','--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('doctor',result.stdout)
        self.assertIn('create',result.stdout)


if __name__=='__main__':
    unittest.main()
