"""Offline evidence-backed reading pages. Python stdlib only; no source fetching.

figure_digest hashes UTF-8 canonical JSON of the entire figure except verification:
sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False.
A matching supplied digest establishes input identity, not source authenticity.
"""
import hashlib
import html
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be nonempty text')
    return value


def _number(value, label):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(label + ' must be a finite number (not boolean)')
    return value


def _url(value):
    value = _text(value, 'source.url')
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise ValueError('Unsafe source URL')
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http', 'https') and parsed.hostname
                 and not parsed.username and not parsed.password)
        parsed.port  # also reject malformed ports
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('source.url must be an absolute http(s) URL without credentials')
    return value


def figure_digest(figure):
    """Return SHA256 of the canonical figure payload, excluding verification."""
    _object(figure, 'figure')
    payload = {key: value for key, value in figure.items() if key != 'verification'}
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('Figure is not canonical finite UTF-8 JSON: ' + str(exc)) from exc
    return hashlib.sha256(encoded).hexdigest()


def _components(value, label, positive=False):
    values = value if isinstance(value, list) else [value]
    if not values:
        raise ValueError(label + ' cannot be empty')
    for number in values:
        _number(number, label)
        if number < 0 or (positive and number == 0):
            raise ValueError(label + (' must be positive' if positive else ' must be nonnegative'))
    return [_number(number, label) for number in values]


def validate(document):
    """Validate all evidence and derive the sole numeric fact model. No writes."""
    _object(document, 'story')
    _text(document.get('title'), 'title')
    _text(document.get('introduction'), 'introduction')
    figures = document.get('figures')
    if not isinstance(figures, list) or not figures:
        raise ValueError('figures must be a nonempty array')
    facts, identities = [], set()
    for figure in figures:
        f = _object(figure, 'figure')
        identity = _text(f.get('id'), 'figure.id')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', identity) or identity in identities:
            raise ValueError('Figure ids must be unique safe anchors: ' + identity)
        identities.add(identity)
        for field in ('title', 'question', 'interpretation', 'unit'):
            _text(f.get(field), 'figure.' + field)
        source = _object(f.get('source'), 'source')
        _url(source.get('url'))
        _text(source.get('label'), 'source.label')
        extract = _object(f.get('extract'), 'extract')
        _text(extract.get('id'), 'extract.id')
        stamp = _text(extract.get('time'), 'extract.time')
        try:
            parsed_time = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if parsed_time.tzinfo is None:
                raise ValueError('timezone required')
        except ValueError as exc:
            raise ValueError('extract.time requires an ISO-8601 timestamp with timezone') from exc
        if extract.get('mode') not in ('local', 'query'):
            raise ValueError('extract.mode must be local or query')
        if extract['mode'] == 'query':
            _text(extract.get('query'), 'extract.query (exact executed query)')
        elif 'query' in extract:
            raise ValueError('Local mode must not declare an executed query')
        kind = f.get('kind')
        if kind not in ('scalar', 'pooled_ratio'):
            raise ValueError('figure.kind must be scalar or pooled_ratio')
        points = f.get('points')
        if not isinstance(points, list) or not points:
            raise ValueError('points must be a nonempty array in intended display order')
        values, inputs = [], []
        for point in points:
            point = _object(point, 'point')
            _text(point.get('period'), 'point.period')
            if kind == 'scalar':
                value = _number(point.get('value'), 'point.value')
                inputs.append({'value': value})
            else:
                observed = _components(point.get('observed'), 'observed')
                predicted = _components(point.get('predicted'), 'predicted', positive=True)
                if len(observed) != len(predicted):
                    raise ValueError('observed and predicted must have matching component counts')
                try:
                    numerator, denominator = math.fsum(observed), math.fsum(predicted)
                    value = numerator / denominator
                except (OverflowError, ZeroDivisionError) as exc:
                    raise ValueError('Pooled calculation overflow or zero denominator') from exc
                _number(value, 'derived pooled ratio')
                inputs.append({'observed': observed, 'predicted': predicted,
                               'sum_observed': numerator, 'sum_predicted': denominator})
            values.append(value)
        delta = _number(values[-1] - values[0], 'derived delta')
        digest = figure_digest(f)
        verification_label = 'Not verified'
        if 'verification' in f:
            check = _object(f['verification'], 'verification')
            expected = _number(check.get('expected_latest'), 'verification.expected_latest')
            if (check.get('digest') != digest or check.get('status') != 'passed'
                    or expected != values[-1]):
                raise ValueError('Supplied verification is stale, failed, or disagrees with derived latest')
            verification_label = 'Supplied checks passed'
        facts.append({'id': identity, 'values': values, 'latest': values[-1], 'delta': delta,
                      'inputs': inputs, 'digest': digest, 'verification': verification_label})
    return {'valid': True, 'figures': facts}


def _escape(value):
    return html.escape(str(value), quote=True)


def _display(value):
    return format(value, '.6g')


def _chart(figure, fact):
    # Normalize before subtraction to keep SVG coordinates finite at extreme magnitudes.
    values = fact['values']
    scale = max(abs(v) for v in values) or 1
    scaled = [v / scale for v in values]
    low, high = min(0, min(scaled)), max(0, max(scaled))
    span = high - low or 1
    coords = [(70 + (i / max(1, len(values) - 1)) * 620,
               210 - ((v - low) / span) * 170) for i, v in enumerate(scaled)]
    line = ' '.join('%.3f,%.3f' % p for p in coords)
    dots = ''.join('<circle cx="%.3f" cy="%.3f" r="5"><title>%s: %s %s</title></circle>' %
                   (x, y, _escape(point['period']), _display(value), _escape(figure['unit']))
                   for (x, y), point, value in zip(coords, figure['points'], values))
    labels = ''.join('<text x="14" y="%.3f">%s</text>' %
                     (210 - i * 85, _display((low + i * span / 2) * scale)) for i in range(3))
    return ('<svg viewBox="0 0 740 260" role="img" aria-labelledby="chart-%s">'
            '<title id="chart-%s">%s. Values in source order; full periods and inputs in Explain.</title>'
            '<path class="axis" d="M70 25V210H700"/>%s'
            '<polyline points="%s"/>%s'
            '<text x="70" y="245">First period</text>'
            '<text x="700" y="245" text-anchor="end">Latest period</text></svg>') % (
                figure['id'], figure['id'], _escape(figure['title']), labels, line, dots)


CSS = """
:root{color-scheme:light;--bg:#f4f3ef;--surface:#fff;--text:#172e37;--muted:#50656c;--line:#c9d5d5;--accent:#006b62;--wash:#e6f3ef}
:root[data-theme=dark]{color-scheme:dark;--bg:#111d24;--surface:#192b33;--text:#e3eeee;--muted:#afc6c9;--line:#3a525b;--accent:#6ee0c3;--wash:#203c3e}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:2rem}body{margin:0;overflow-wrap:anywhere;background:var(--bg);color:var(--text);font:17px/1.65 system-ui,-apple-system,sans-serif}a{color:var(--accent);overflow-wrap:anywhere}button,summary,a{touch-action:manipulation}button{font:inherit;color:var(--text);border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:.5rem .85rem;cursor:pointer}a:focus-visible,summary:focus-visible,button:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.shell{max-width:1320px;margin:auto;padding:2rem 3rem;display:grid;grid-template-columns:235px minmax(0,1fr);gap:3.5rem}aside{align-self:start;position:sticky;top:2rem}aside p,.eyebrow{font-size:.75rem;text-transform:uppercase;letter-spacing:.13em;color:var(--muted);font-weight:750}nav a{display:block;text-decoration:none;padding:.75rem;border-left:3px solid var(--line);font-size:.9rem}nav a[aria-current=true]{border-color:var(--accent);background:var(--wash);font-weight:700}main,section,figure{min-width:0}header{padding:1rem 0 2.5rem;border-bottom:1px solid var(--line)}h1{font-size:clamp(2rem,4vw,3.8rem);letter-spacing:-.04em;line-height:1.13;margin:.7rem 0 1.5rem}h2{font-size:1.9rem;letter-spacing:-.03em;line-height:1.2}h3{font-size:1rem;margin:1.3rem 0 .4rem}p{overflow-wrap:anywhere}.intro{font-size:1.2rem;color:var(--muted);max-width:65ch}section{padding:2rem 0 3rem;scroll-margin-top:2rem}figure{background:var(--surface);border:1px solid var(--line);border-radius:16px;margin:1.4rem 0;padding:1.6rem}figcaption{font-size:.8rem;color:var(--muted)}.metrics{display:flex;flex-wrap:wrap;gap:2rem}.metric strong{display:block;font-size:2.2rem;line-height:1.3;letter-spacing:-.03em}.metric span{color:var(--muted);font-size:.85rem}.badge{display:inline-block;font-size:.75rem;font-weight:650;border:1px solid var(--line);border-radius:99px;padding:.2rem .7rem}.interpretation{border-left:3px solid var(--accent);padding-left:1rem}svg{display:block;width:100%;height:auto;margin:1.5rem 0;color:var(--accent)}svg polyline{fill:none;stroke:currentColor;stroke-width:3}svg circle{fill:currentColor}svg .axis{fill:none;stroke:var(--line);stroke-width:1}svg text{fill:var(--muted);font:12px system-ui}details{border-top:1px solid var(--line);margin-top:1.4rem;padding-top:1rem}summary{cursor:pointer;font-weight:700;color:var(--accent)}.evidence{font-size:.9rem;overflow-wrap:anywhere}dl{margin:.5rem 0}dt{font-weight:700;margin-top:.7rem}dd{margin:0;color:var(--muted)}code,pre{font: .85rem/1.6 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}pre{padding:1rem;background:var(--wash);border-radius:8px}.point{border-bottom:1px solid var(--line);padding:.65rem 0}.point p{margin:.2rem 0}.note{font-size:.8rem;color:var(--muted)}footer{border-top:1px solid var(--line);padding:2rem 0;color:var(--muted);font-size:.8rem}@media(max-width:760px){svg text{font-size:34px}.shell{display:block;padding:1.2rem}aside{position:static;margin-bottom:2rem}nav{margin:1rem 0}nav a{padding:.5rem .75rem}header{padding-top:0}figure{padding:1rem}h2{font-size:1.6rem}.metrics{gap:1rem}.metric strong{font-size:1.8rem}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{aside,button{display:none}.shell{display:block}details{display:block}body{background:white;color:black}}
"""

JS = """
const root=document.documentElement, button=document.getElementById('theme');
button.addEventListener('click',()=>{const dark=root.dataset.theme!=='dark';root.dataset.theme=dark?'dark':'light';button.setAttribute('aria-pressed',String(dark));button.textContent=dark?'Use light theme':'Use dark theme';});
const links=[...document.querySelectorAll('nav a')];
function mark(id){links.forEach(a=>a.setAttribute('aria-current',String(a.hash==='#'+id)));}
links.forEach(a=>a.addEventListener('click',()=>mark(a.hash.slice(1))));
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)mark(entry.target.id);}}, {rootMargin:'-10% 0px -55% 0px'});document.querySelectorAll('section').forEach(section=>observer.observe(section));}
"""


def render_html(document, report):
    """All untrusted content goes into escaped HTML text/attributes, never JavaScript."""
    rail, sections = [], []
    for index, (f, fact) in enumerate(zip(document['figures'], report['figures']), 1):
        e = f['extract']
        rail.append('<a href="#story-%s" aria-current="%s">%02d · %s</a>' %
                    (f['id'], str(index == 1).lower(), index, _escape(f['title'])))
        rows = []
        for point, value, inputs in zip(f['points'], fact['values'], fact['inputs']):
            if f['kind'] == 'scalar':
                calculation = 'value = ' + _display(value)
            else:
                calculation = ('sum(observed) / sum(predicted) = %s / %s = %s; observed=%s; predicted=%s' %
                               (_display(inputs['sum_observed']), _display(inputs['sum_predicted']),
                                _display(value), json.dumps(inputs['observed']), json.dumps(inputs['predicted'])))
            rows.append('<div class="point"><strong>%s</strong><p>%s %s</p><code>%s</code></div>' %
                        (_escape(point['period']), _display(value), _escape(f['unit']), _escape(calculation)))
        query = ('<h3>Exact executed query (source-supplied)</h3><pre>%s</pre>' % _escape(e['query'])
                 if e['mode'] == 'query' else '<h3>Local-file extract</h3><p>No executed model query is declared.</p>')
        sections.append('''<section id="story-%s" aria-labelledby="heading-%s">
<p class="eyebrow">Figure %02d · %s</p><h2 id="heading-%s">%s</h2><p>%s</p>
<figure><div class="metrics"><div class="metric"><span>Latest · %s</span><strong>%s <small>%s</small></strong></div>
<div class="metric"><span>Change from first period</span><strong>%s <small>%s</small></strong></div></div>%s
<figcaption>Source-ordered observations, not a continuous calendar scale. Units: %s. Display: six significant digits; evidence retains raw inputs.</figcaption>
<details><summary>Explain this figure</summary><div class="evidence">
<h3>Verification</h3><span class="badge">%s</span><p>Supplied checks bind input identity and expected latest only; this is not independent source certification.</p>
<dl><dt>Source</dt><dd><a href="%s" rel="noreferrer noopener">%s</a><br>%s</dd>
<dt>Extract identity</dt><dd>%s</dd><dt>Extraction time</dt><dd>%s</dd>
<dt>Figure SHA256 (excluding verification)</dt><dd><code>%s</code></dd></dl>%s
<h3>Calculation inputs and source periods</h3>%s
<p>Latest = last supplied point. Delta = latest − first = %s − %s = %s %s. No interpolation or causal inference.</p>
</div></details></figure><div class="interpretation"><h3>Human interpretation</h3><p>%s</p>
<p class="note">Author-supplied interpretation, not a calculated or independently verified conclusion.</p></div></section>''' % (
            f['id'], f['id'], index, _escape(f['kind']), f['id'], _escape(f['title']), _escape(f['question']),
            _escape(f['points'][-1]['period']), _display(fact['latest']), _escape(f['unit']),
            _display(fact['delta']), _escape(f['unit']), _chart(f, fact), _escape(f['unit']), fact['verification'],
            _escape(f['source']['url']), _escape(f['source']['label']), _escape(f['source']['url']),
            _escape(e['id']), _escape(e['time']), fact['digest'], query, ''.join(rows),
            _display(fact['latest']), _display(fact['values'][0]), _display(fact['delta']), _escape(f['unit']),
            _escape(f['interpretation'])))
    return '''<!doctype html><!-- Design manifest: artifact_class=narrative reading page;
 audience=readers inspecting a static extract; primary_question=what changed and what supports it;
 data_lifecycle=offline snapshot; data_semantics=source-ordered scalar/pooled-ratio observations;
 provenance=figure-local source, period, extract and supplied checks; density=sparse narrative, detailed evidence;
 chart_rationale=ordinal line chart with a zero-inclusive per-figure scale;
 overrides=native controls and inline assets only (offline requirement), rail supports arbitrary figure counts,
 human interpretation is separate from calculated facts; no causal or source-authenticity certification.
--><html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>%s</title><style>%s</style></head><body><div class="shell"><aside>
<p>Evidence / Data stories</p><button id="theme" type="button" aria-pressed="false">Use dark theme</button>
<nav aria-label="Story figures">%s</nav><p class="note">A static snapshot.<br>Inspect the evidence before acting.</p></aside><main>
<header><p class="eyebrow">An evidence-backed reading page</p><h1>%s</h1><p class="intro">%s</p></header>
%s<footer>Offline snapshot · No source requests, backend or live refresh. Source links open only when followed. Review the full extract before sharing.</footer>
</main></div><script>%s</script></body></html>''' % (
        _escape(document['title']), CSS, ''.join(rail), _escape(document['title']),
        _escape(document['introduction']), ''.join(sections), JS)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key: ' + key)
        result[key] = value
    return result


def run(action, input_path, output_path=None):
    document = json.loads(Path(input_path).expanduser().read_text(encoding='utf-8'),
                          object_pairs_hook=_unique_keys)
    report = validate(document)
    if action == 'validate':
        return report
    if action != 'render' or not output_path:
        raise ValueError('Expected validate or render with output')
    requested = Path(output_path).expanduser()
    if requested.is_symlink():
        raise FileExistsError('Output exists as a symlink; select a new path')
    output = requested.absolute()
    if output.suffix.lower() != '.html':
        raise ValueError('Output must be a new .html path')
    # Finish validation and encoding before creating any output or directory.
    content = render_html(document, report).encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle:
        handle.write(content)
    return {**report, 'output': str(output), 'offline': True}
