"""Presentation-template layer for Archify output."""
import json
import tempfile
import unittest
from pathlib import Path

from creator_tools import diagram_templates as t

DIAGRAM = {
    'diagram_type': 'workflow',
    'meta': {'views': [{'id': 'v1', 'label': '1. Path', 'note': 'Note text', 'focus': ['a', 'b', 'ghost']}]},
    'nodes': [{'id': 'a', 'label': 'Alpha', 'sublabel': 'first'}, {'id': 'b', 'label': 'Beta</script>'}],
    'edges': [{'from': 'a', 'to': 'b', 'label': 'feeds'}, {'from': 'a', 'to': 'missing'}],
}
HTML = b'<html><body><svg></svg></body></html>'


class TemplateTests(unittest.TestCase):
    def test_full_without_chapters_is_byte_identical(self):
        spec = t.resolve('full')
        plain = {**DIAGRAM, 'meta': {}}
        self.assertEqual(t.apply(HTML, plain, spec), HTML)

    def test_full_with_chapters_adds_only_the_chapter_bar(self):
        out = t.apply(HTML, DIAGRAM, t.resolve('full'))
        self.assertIn(b'id="cc-chapters-script"', out)
        self.assertNotIn(b'id="cc-template"', out)
        self.assertEqual(out.replace(out[out.index(b'<style id="cc-chapters-style">'):out.index(b'</body>')], b''), HTML)

    def test_chapters_keep_only_known_focus_and_escape(self):
        out = t.apply(HTML, DIAGRAM, t.resolve('story')).decode()
        chap = out.split('<script id="cc-chapters-script">', 1)[1]
        data, _ = json.JSONDecoder().raw_decode(chap.split('var D = ', 1)[1])
        self.assertEqual(data['views'][0]['focus'], ['a', 'b'])
        self.assertNotIn('</script>"', out.split('cc-chapters-script')[1].split('</script>')[0])

    def test_hidden_chapters_and_empty_views(self):
        out = t.apply(HTML, DIAGRAM, t.resolve('embed')).decode()
        self.assertIn('#cc-chapters{display:none!important}', out)
        empty = {**DIAGRAM, 'meta': {'views': [{'id': 'x', 'label': 'X', 'focus': ['ghost']}]}}
        self.assertNotIn('cc-chapters-script', t.apply(HTML, empty, t.resolve('story')).decode())

    def test_showcase_bridge_drives_creator_chapters(self):
        from creator_tools import diagrams
        js = diagrams._showcase_bridge_script(1000)
        self.assertIn('CreatorChapters', js)
        self.assertNotIn('guidedViews', js)

    def test_presenter_hides_tooling_and_replaces_passport(self):
        spec = t.resolve('presenter')
        self.assertTrue(spec['details'])
        self.assertIn('passport', spec['hide'])
        self.assertIn('toolbar', spec['hide'])
        self.assertNotIn('chapters', spec['hide'])

    def test_hide_and_show_overrides(self):
        spec = t.resolve('embed', show=['header'], hide=['zoom'])
        self.assertNotIn('header', spec['hide'])
        self.assertIn('zoom', spec['hide'])
        self.assertFalse(t.resolve('presenter', hide=['details'])['details'])
        self.assertIn('passport', t.resolve('full', show=['details'])['hide'])
        with self.assertRaises(ValueError):
            t.resolve('fancy')
        with self.assertRaises(ValueError):
            t.resolve('full', hide=['everything'])

    def test_injection_is_escaped_and_once(self):
        out = t.apply(HTML, DIAGRAM, t.resolve('embed')).decode()
        self.assertEqual(out.count('id="cc-template"'), 1)
        self.assertLess(out.index('cc-template'), out.index('</body>'))
        self.assertNotIn('Beta</script>', out)

    def test_model_drops_dangling_references(self):
        m = t.model(DIAGRAM, {})
        self.assertEqual([e['to'] for e in m['edges']], ['b'])
        self.assertEqual(m['views'][0]['focus'], ['a', 'b'])

    def test_details_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'd.json'
            p.write_text(json.dumps({'a': {'what': 'Does A', 'why': 'Because'}}))
            self.assertEqual(t.load_details(p, DIAGRAM)['a']['what'], 'Does A')
            for bad in [{'zzz': {'what': 'x'}}, {'a': {'what': ''}}, {'a': {'colour': 'red'}}, ['a']]:
                p.write_text(json.dumps(bad))
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    t.load_details(p, DIAGRAM)
        self.assertEqual(t.load_details(None, DIAGRAM), {})

    def test_architecture_details_use_component_ids(self):
        diagram = {'diagram_type': 'architecture',
                   'components': [{'id': 'cue', 'label': 'Cue'}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'details.json'
            p.write_text(json.dumps({'cue': {'what': 'Authors proposed fixes'}}))
            self.assertEqual(t.load_details(p, diagram)['cue']['what'],
                             'Authors proposed fixes')
            p.write_text(json.dumps({'ghost': {'what': 'Not in the graph'}}))
            with self.assertRaisesRegex(ValueError, 'unknown node ids: ghost'):
                t.load_details(p, diagram)

    def test_embed_snippet_escapes(self):
        s = t.embed_snippet('a"b.html', title='<x>', height=400)
        self.assertIn('a&quot;b.html', s)
        self.assertIn('&lt;x&gt;', s)
        self.assertIn('height:400px', s)


if __name__ == '__main__':
    unittest.main()


def test_wrapper_templates_drop_google_fonts_and_keep_full_untouched():
    from creator_tools import diagram_templates as dt
    html = (b'<html><head><link rel="preconnect" href="https://fonts.googleapis.com">'
            b'<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono" rel="stylesheet">'
            b'<style>@import url("https://fonts.googleapis.com/css2?family=Inter");</style></head><body></body></html>')
    diagram = {"diagram_type": "architecture", "meta": {"title": "t", "views": []}, "components": [], "connections": []}
    out = dt.apply(html, diagram, dt.resolve("presenter"))
    assert b"fonts.googleapis.com" not in out and b"cc-template" in out
    assert dt.apply(html, diagram, dt.resolve("full")) == html
