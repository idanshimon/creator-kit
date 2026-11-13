"""Behavioral contract tests: exercise the real CLI, no module import at collection."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def story():
    return {
        'title': 'SYNTHETIC workshop story',
        'introduction': 'Invented observations, not real-world findings.',
        'figures': [{
            'id': 'throughput', 'title': 'SYNTHETIC throughput',
            'question': 'What changed?', 'interpretation': 'Human hypothesis only.',
            'unit': 'items', 'kind': 'scalar',
            'source': {'url': 'https://example.org/synthetic', 'label': 'SYNTHETIC fixture'},
            'extract': {'id': 'synthetic-v1', 'time': '2026-10-01T12:00:00Z', 'mode': 'local'},
            'points': [
                {'period': '2025 Q1 (Jan–Mar)', 'value': 12},
                {'period': '2025 Q3 (Jul–Sep)', 'value': 18}
            ]
        }]
    }


def digest(figure):
    payload = {k: v for k, v in figure.items() if k != 'verification'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


class DataStoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def cli(self, document, action='validate', output=None):
        path = self.base / 'input.json'
        path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        args = [sys.executable, str(ROOT / 'creator.py'), 'data-story', action, '--input', str(path)]
        if action == 'render':
            args += ['--output', str(output or self.base / 'story.html')]
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)

    def test_validate_derives_latest_delta_and_digest(self):
        document = story()
        result = self.cli(document)
        self.assertEqual(result.returncode, 0, result.stderr)
        fact = json.loads(result.stdout)['figures'][0]
        self.assertEqual(fact['values'], [12, 18])
        self.assertEqual(fact['latest'], 18)
        self.assertEqual(fact['delta'], 6)
        self.assertEqual(fact['digest'], digest(document['figures'][0]))
        self.assertEqual(fact['verification'], 'Not verified')

    def test_pooled_ratio_is_ratio_of_sums_not_average_of_ratios(self):
        doc = story()
        f = doc['figures'][0]
        f['kind'] = 'pooled_ratio'
        f['points'] = [{'period': 'Unequal first window', 'observed': [1, 9], 'predicted': [2, 3]},
                       {'period': 'Unequal last window', 'observed': 3, 'predicted': 4}]
        result = self.cli(doc)
        self.assertEqual(result.returncode, 0, result.stderr)
        fact = json.loads(result.stdout)['figures'][0]
        self.assertEqual(fact['values'], [2, .75])
        self.assertEqual(fact['delta'], -1.25)

    def test_rejects_invalid_figures_and_creates_no_output(self):
        cases = []
        for value in (True, False, float('nan'), float('inf'), -float('inf'), '12', None):
            d = story(); d['figures'][0]['points'][0]['value'] = value; cases.append(d)
        for key in ('period', 'value'):
            d = story(); del d['figures'][0]['points'][0][key]; cases.append(d)
        for key in ('source', 'extract', 'interpretation'):
            d = story(); del d['figures'][0][key]; cases.append(d)
        for key in ('id', 'time', 'mode'):
            d = story(); del d['figures'][0]['extract'][key]; cases.append(d)
        for url in ('javascript:alert(1)', 'data:text/html,hi', '//evil.test', 'file:///etc/passwd',
                    'https://good.test/\nattack', 'https://u:p@example.org', 'https://'):
            d = story(); d['figures'][0]['source']['url'] = url; cases.append(d)
        d = story(); d['figures'].append(copy.deepcopy(d['figures'][0])); cases.append(d)
        d = story(); d['figures'][0]['id'] = '\" onclick=\"alert(1)'; cases.append(d)
        d = story(); d['figures'][0]['points'] = []; cases.append(d)
        d = story(); d['figures'][0]['extract']['time'] = 'yesterday'; cases.append(d)
        for observed, predicted in ((1, 0), (1, True), ([1, 2], [1, 0]), ([-1], [1]),
                                    ([1, 2], [3]), (1e308, 1e-308)):
            d = story(); f = d['figures'][0]; f['kind'] = 'pooled_ratio'
            f['points'] = [{'period': 'Window', 'observed': observed, 'predicted': predicted}]; cases.append(d)
        for index, d in enumerate(cases):
            with self.subTest(case=index):
                out = self.base / ('bad-%s.html' % index)
                result = self.cli(d, 'render', out)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn('Creator:', result.stderr)
                self.assertFalse(out.exists())

    def test_supplied_verification_binds_figure_and_expected_latest(self):
        d = story(); f = d['figures'][0]
        f['verification'] = {'digest': digest(f), 'status': 'passed', 'expected_latest': 18}
        result = self.cli(d)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['figures'][0]['verification'], 'Supplied checks passed')
        for key, value in (('digest', '0' * 64), ('status', 'failed'), ('expected_latest', 99),
                           ('expected_latest', True)):
            bad = copy.deepcopy(d); bad['figures'][0]['verification'][key] = value
            result = self.cli(bad, 'render')
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertFalse((self.base / 'story.html').exists())
        bad = copy.deepcopy(d); bad['figures'][0]['extract']['id'] = 'new-extract'
        self.assertEqual(self.cli(bad).returncode, 2)

    def test_render_has_evidence_and_safely_escapes_author_text(self):
        d = story(); hostile = '</script><script>window.PWNED=1</script>\" & <img src=x onerror=alert(1)>'
        d['title'] = hostile
        f = d['figures'][0]; f['interpretation'] = hostile
        f['extract']['mode'] = 'query'; f['extract']['query'] = hostile
        result = self.cli(d, 'render')
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.base / 'story.html').read_text(encoding='utf-8')
        self.assertNotIn(hostile, html)
        self.assertIn('&lt;/script&gt;', html)
        for text in ('<svg', '<details', '<summary', 'Explain', 'Human interpretation',
                     'Not verified', '2025 Q1 (Jan–Mar)', 'synthetic-v1', 'Exact executed query',
                     'https://example.org/synthetic', 'Calculation inputs', '12', '18'):
            self.assertIn(text, html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link ', html)

    def test_delta_metric_keeps_units_next_to_value(self):
        result = self.cli(story(), 'render')
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.base / 'story.html').read_text()
        self.assertIn('<span>Change from first period</span><strong>6 <small>items</small></strong>', content)

    def test_render_refuses_overwrite(self):
        output = self.base / 'story.html'; output.write_text('preserve me')
        result = self.cli(story(), 'render', output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), 'preserve me')

    def test_query_mode_requires_exact_query_and_local_does_not_claim_query(self):
        d = story(); d['figures'][0]['extract']['mode'] = 'query'
        self.assertEqual(self.cli(d).returncode, 2)
        d['figures'][0]['extract']['query'] = 'SELECT literal FROM synthetic_fixture'
        self.assertEqual(self.cli(d).returncode, 0)
        self.assertEqual(self.cli(story(), 'render').returncode, 0)
        html = (self.base / 'story.html').read_text()
        self.assertIn('Local-file extract', html)
        self.assertNotIn('Exact executed query', html)

    def test_figure_ids_cannot_collide_with_page_controls(self):
        from html.parser import HTMLParser
        class Ids(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids = []
            def handle_starttag(self, tag, attrs):
                self.ids.extend(value for key, value in attrs if key == 'id')
        d = story(); d['figures'][0]['id'] = 'theme'
        self.assertEqual(self.cli(d, 'render').returncode, 0)
        parser = Ids(); parser.feed((self.base / 'story.html').read_text())
        self.assertEqual(len(parser.ids), len(set(parser.ids)))

    def test_dangling_output_symlink_is_preserved(self):
        output = self.base / 'story.html'
        target = self.base / 'missing.html'
        output.symlink_to(target)
        result = self.cli(story(), 'render', output)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(output.is_symlink())
        self.assertFalse(target.exists())

    def test_duplicate_json_keys_are_rejected_without_output(self):
        path = self.base / 'duplicate.json'
        encoded = json.dumps(story()).replace('"value": 12', '"value": 999, "value": 12')
        path.write_text(encoded)
        out = self.base / 'story.html'
        result = subprocess.run([sys.executable, str(ROOT / 'creator.py'), 'data-story', 'render',
                                 '--input', str(path), '--output', str(out)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Duplicate JSON object key', result.stderr)
        self.assertFalse(out.exists())

    def test_exported_digest_helper_matches_cli(self):
        result = self.cli(story())
        self.assertEqual(result.returncode, 0, result.stderr)
        # Import only after behavioral CLI assertion, so absent feature is FAIL not collection ERROR.
        from creator_tools.data_story import figure_digest
        self.assertEqual(figure_digest(story()['figures'][0]), digest(story()['figures'][0]))


if __name__ == '__main__':
    unittest.main()
