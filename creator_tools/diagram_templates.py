"""Presentation templates layered on top of a rendered Archify HTML file.

The upstream Archify output is never modified in place: a template is a
wrapper-owned <style> + <script> injected before </body>. ``full`` injects
nothing, so the original viewer stays byte-identical to upstream delivery.

Templates
---------
full       Original Archify UI (toolbar, chapters, PATH/MAP/LENS, passport).
presenter  Title + guided chapters + diagram + zoom. Clicking a component opens
           a detail panel (what it does / why / example) instead of the
           semantic passport. Tooling (export, style, radar, lens...) hidden.
story      Guided chapters + graph only (no toolbar, cards, PATH/MAP/LENS); click
           opens the detail panel. For embedding the guided walkthrough.
embed      Graph only, sized to its iframe. Click opens the same detail panel
           as a compact sheet. No toolbar, chapters, cards or nav.
minimal    Graph only, static: no detail panel, no controls. For screenshots.

Individual parts can also be toggled with ``hide`` / ``show``.

Details: an optional sidecar JSON keyed by node id,
``{"node_id": {"what": "...", "why": "...", "example": "..."}}``.
Missing entries fall back to the node's own authored label/sublabel and the
guided-view notes that mention it; nothing is invented.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

PARTS = ('toolbar', 'header', 'chapters', 'cards', 'nav', 'zoom', 'passport', 'legend', 'grid', 'details')

TEMPLATES = {
    'full':      {'hide': [], 'details': False},
    'presenter': {'hide': ['toolbar', 'nav', 'passport'], 'details': True},
    'story':     {'hide': ['toolbar', 'header', 'cards', 'nav', 'passport', 'legend', 'grid'], 'details': True},
    'embed':     {'hide': ['toolbar', 'header', 'chapters', 'cards', 'nav', 'passport', 'legend', 'grid'], 'details': True},
    'minimal':   {'hide': ['toolbar', 'header', 'chapters', 'cards', 'nav', 'zoom', 'passport', 'legend', 'grid'], 'details': False},
}

DETAIL_FIELDS = ('what', 'why', 'example')


def resolve(template='full', hide=None, show=None):
    if template not in TEMPLATES:
        raise ValueError(f'Unknown template {template!r}; choose from {", ".join(TEMPLATES)}')
    spec = TEMPLATES[template]
    hidden = set(spec['hide'])
    details = spec['details']
    for part in hide or []:
        if part not in PARTS:
            raise ValueError(f'Unknown part {part!r}; choose from {", ".join(PARTS)}')
        if part == 'details':
            details = False
        else:
            hidden.add(part)
    for part in show or []:
        if part not in PARTS:
            raise ValueError(f'Unknown part {part!r}; choose from {", ".join(PARTS)}')
        if part == 'details':
            details = True
        else:
            hidden.discard(part)
    if details:
        hidden.add('passport')  # the detail panel replaces the passport
    return {'template': template, 'hide': sorted(hidden), 'details': details}


def load_details(path, diagram):
    if path is None:
        return {}
    data = json.loads(Path(path).expanduser().read_text())
    if not isinstance(data, dict):
        raise ValueError('Details file must be a JSON object keyed by node id')
    authored_nodes = diagram.get('nodes', []) or diagram.get('components', [])
    ids = {n.get('id') for n in authored_nodes if isinstance(n, dict)}
    unknown = sorted(set(data) - ids)
    if unknown:
        raise ValueError('Details reference unknown node ids: ' + ', '.join(unknown))
    clean = {}
    for node_id, entry in data.items():
        if not isinstance(entry, dict):
            raise ValueError(f'Details for {node_id!r} must be an object')
        extra = set(entry) - set(DETAIL_FIELDS)
        if extra:
            raise ValueError(f'Details for {node_id!r} have unknown fields: {", ".join(sorted(extra))}')
        for field in DETAIL_FIELDS:
            value = entry.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f'Details {node_id}.{field} must be non-empty text')
        clean[node_id] = {k: v.strip() for k, v in entry.items()}
    return clean


def model(diagram, details):
    """Minimal graph model the wrapper needs; built from the authored JSON only."""
    nodes = {}
    for n in diagram.get('nodes', []) or diagram.get('components', []):
        if isinstance(n, dict) and n.get('id'):
            nodes[n['id']] = {'label': str(n.get('label') or n['id']),
                              'sublabel': str(n.get('sublabel') or n.get('description') or ''),
                              'type': str(n.get('type') or n.get('kind') or '')}
    edges = []
    for e in diagram.get('edges', []) or diagram.get('relationships', []) or diagram.get('connections', []):
        if isinstance(e, dict):
            src, dst = e.get('from') or e.get('source'), e.get('to') or e.get('target')
            if src in nodes and dst in nodes:
                edges.append({'from': src, 'to': dst, 'label': str(e.get('label') or '')})
    views = []
    for v in (diagram.get('meta') or {}).get('views', []) or []:
        if isinstance(v, dict):
            views.append({'label': str(v.get('label') or v.get('id') or ''),
                          'note': str(v.get('note') or ''),
                          'focus': [f for f in v.get('focus', []) if f in nodes]})
    return {'nodes': nodes, 'edges': edges, 'views': views, 'details': details}


_CSS = {
    'toolbar': '.toolbar{display:none!important}',
    'header': '.header{display:none!important}',
    'chapters': '#guided-views,.share-chapter-cue{display:none!important}',
    'cards': '.cards{display:none!important}',
    'nav': ('#btn-route-probe,#btn-overview-map,#btn-semantic-lens,#btn-node-finder,#btn-diagram-guide,'
            '#route-probe,#semantic-lens,#overview-map,#node-finder,#diagram-guide{display:none!important}'),
    'zoom': '.diagram-nav{display:none!important}',
    'passport': '#focus-chip{display:none!important}',
    'legend': 'svg [data-cc-legend]{display:none!important}',
    'grid': 'svg [data-cc-grid]{display:none!important}',
}

_BASE_CSS = """
#cc-detail{position:fixed;top:16px;right:16px;bottom:16px;width:min(380px,calc(100vw - 32px));z-index:60;
  background:var(--cc-panel,#11161d);color:var(--cc-ink,#e6edf3);border:1px solid var(--cc-line,#2a3441);
  border-radius:16px;box-shadow:0 24px 60px -20px rgba(0,0,0,.55);padding:22px 22px 18px;overflow:auto;
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  transform:translateX(calc(100% + 24px));transition:transform .22s ease;}
#cc-detail[data-open="true"]{transform:none}
#cc-detail{color-scheme:dark;scrollbar-width:thin;scrollbar-color:var(--cc-line,#2a3441) transparent}
html[data-theme="light"] #cc-detail{color-scheme:light}
#cc-detail::-webkit-scrollbar{width:10px}
#cc-detail::-webkit-scrollbar-track{background:transparent}
#cc-detail::-webkit-scrollbar-thumb{background:var(--cc-line,#2a3441);border-radius:10px;border:3px solid var(--cc-panel,#11161d)}
#cc-detail::-webkit-scrollbar-thumb:hover{background:var(--cc-muted,#9fb0bf)}
#cc-detail .cc-eyebrow{font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--cc-accent,#7ec99b)}
#cc-detail h2{font-size:22px;line-height:1.2;margin:8px 34px 4px 0;font-weight:650}
#cc-detail .cc-sub{color:var(--cc-muted,#9fb0bf);margin:0 0 14px}
#cc-detail h3{font:600 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--cc-muted,#9fb0bf);margin:16px 0 6px}
#cc-detail p{margin:0}
#cc-detail .cc-example{background:var(--cc-soft,#18212b);border-radius:10px;padding:10px 12px}
#cc-detail ul{margin:0;padding-left:18px}
#cc-detail button.cc-link{background:none;border:0;padding:0;color:var(--cc-accent,#7ec99b);cursor:pointer;font:inherit;text-align:left}
#cc-detail button.cc-link:hover{text-decoration:underline}
#cc-detail .cc-close{position:absolute;top:14px;right:14px;width:30px;height:30px;border-radius:8px;border:1px solid var(--cc-line,#2a3441);
  background:transparent;color:inherit;font-size:18px;line-height:1;cursor:pointer}
#cc-detail details{margin-top:16px;border-top:1px solid var(--cc-line,#2a3441);padding-top:10px}
#cc-detail summary{cursor:pointer;color:var(--cc-muted,#9fb0bf);font-size:13px}
#cc-detail code{font:12px ui-monospace,Menlo,monospace}
html[data-theme="light"] #cc-detail{--cc-panel:#fff;--cc-ink:#18212b;--cc-line:#dbe3ea;--cc-muted:#5a6b7a;--cc-soft:#f2f6f9;--cc-accent:#1a7f37}
svg [data-node-id].cc-selected rect,svg [data-node-id].cc-selected path{filter:drop-shadow(0 0 6px var(--cc-accent,#7ec99b))}
svg g:focus-visible,svg [data-node-id]:focus-visible{outline:2px solid var(--cc-accent,#7ec99b);outline-offset:3px;border-radius:6px}
svg g:focus-visible rect,svg [data-node-id]:focus-visible rect{stroke:var(--cc-accent,#7ec99b)!important;stroke-width:2.5px!important}
"""

_PRESENTER_CSS = """
@media (min-width: 1000px){
  html[data-cc-template="presenter"] body{padding-right:404px}
  html[data-cc-template="presenter"] #cc-detail{transform:none;top:0;right:0;bottom:0;width:388px;border-radius:0;
    border-width:0 0 0 1px;box-shadow:none}
  html[data-cc-template="presenter"] #cc-detail .cc-close{display:none}
}
#cc-detail .cc-empty{color:var(--cc-muted,#9fb0bf);margin-top:10px}
"""

_EMBED_CSS = """
html,body{height:100%;margin:0;overflow:hidden}
#guided-views{margin:0 0 6px!important;border-radius:0!important}
html[data-theme="light"] body{background:#fff!important}
html[data-theme="dark"] body{background:#0b1220!important}
.container{max-width:none!important;width:100%!important;height:100%;padding:0!important;margin:0!important;display:flex;flex-direction:column}
.diagram-container{flex:1;min-height:0;margin:0!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}
.diagram-container>svg{min-width:0!important;max-width:100%!important;width:100%!important;height:100%!important;padding:0!important}
.diagram-nav{opacity:.0;transition:opacity .2s}
.diagram-container svg text{text-rendering:geometricPrecision}
.diagram-container:hover .diagram-nav,.diagram-nav:focus-within{opacity:1}
#cc-detail{top:auto;left:12px;right:12px;bottom:12px;width:auto;max-height:62%;transform:translateY(calc(100% + 24px))}
"""


def wrapper(diagram, spec, details=None):
    """Return the bytes to inject before </body>; empty for the untouched full template."""
    if spec['template'] == 'full' and not spec['hide'] and not spec['details']:
        return b''
    css = _BASE_CSS + ''.join(_CSS[p] for p in spec['hide'] if p in _CSS)
    if spec['template'] in ('embed', 'minimal', 'story'):
        css += _EMBED_CSS
    elif spec['details']:
        css += _PRESENTER_CSS
    data = json.dumps({'spec': spec, 'model': model(diagram, details or {})},
                      ensure_ascii=False).replace('<', '\\u003c')
    script = _SCRIPT.replace('__DATA__', data)
    out = (f'<style id="cc-template-style">{css}</style>\n'
           f'<script id="cc-template">{script}</script>\n')
    return out.encode('utf-8')


_FONT_LINK = re.compile(rb'<link[^>]+(?:fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>\s*', re.I)
_FONT_IMPORT = re.compile(rb'@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;?', re.I)


def apply(content: bytes, diagram, spec, details=None) -> bytes:
    inject = wrapper(diagram, spec, details)
    if not inject:
        return content
    # Wrapper templates are offline artifacts: drop the upstream Google Fonts fetch; the CSS
    # font stacks already fall back to local monospace/system fonts.
    content = _FONT_IMPORT.sub(b'', _FONT_LINK.sub(b'', content))
    marker = b'</body>'
    if marker in content:
        return content.replace(marker, inject + marker, 1)
    return content + inject


def embed_snippet(src, title='Interactive diagram', height=420):
    """<iframe> plus a tiny listener that sizes it to the diagram (no empty space)."""
    return (f'<iframe src="{html.escape(str(src), quote=True)}" title="{html.escape(title, quote=True)}" '
            f'loading="lazy" style="display:block;width:100%;height:{int(height)}px;border:0"></iframe>\n'
            '<script>addEventListener("message",function(e){if(!e.data||e.data.type!=="creator-diagram-height")return;'
            'document.querySelectorAll("iframe").forEach(function(f){if(f.contentWindow===e.source)'
            'f.style.height=Math.max(160,Math.min(1600,+e.data.height||0))+"px"})});</script>')


_SCRIPT = r"""
(function(){
  var D = __DATA__;
  var spec = D.spec, M = D.model;
  var root = document.documentElement;
  root.setAttribute('data-cc-template', spec.template);
  try {
    var q = new URLSearchParams(location.search).get('cc-template');
    if (q) root.setAttribute('data-cc-template-request', q);
  } catch (_) {}
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  // Selecting a component must not move the camera (keeps the overview readable).
  function holdCamera(){
    var v = window.Archify && Archify.view;
    if (v && v.reveal && !v.__ccHeld) {
      var reveal = v.reveal;
      v.reveal = function(ids, opts){ if (opts && opts.reason === 'focus') return null; return reveal.apply(this, arguments); };
      v.__ccHeld = true;
    }
  }

  var panel = null, current = null;
  function build(){
    panel = document.createElement('aside');
    panel.id = 'cc-detail';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'false');
    panel.setAttribute('aria-labelledby', 'cc-detail-title');
    panel.setAttribute('data-open', 'false');
    document.body.appendChild(panel);
    document.addEventListener('keydown', function(e){ if (e.key === 'Escape') close(); });
  }
  function placeholder(){
    if (!panel) build();
    panel.innerHTML = '<span class="cc-eyebrow">Details</span><h2 id="cc-detail-title">Click any component</h2>' +
      '<p class="cc-empty">Select a box in the diagram to see what it does, why it matters and an example.</p>';
  }
  function close(){
    if (!panel) return;
    if (docked()) placeholder();
    panel.setAttribute('data-open', 'false');
    current = null;
    markSelected(null);
    if (window.Archify && Archify.focus && Archify.focus.clear) { try { Archify.focus.clear(); } catch (_) {} }
  }
  function markSelected(id){
    document.querySelectorAll('svg [data-node-id].cc-selected').forEach(function(n){ n.classList.remove('cc-selected'); });
    if (id) { var g = document.querySelector('svg g[data-node-id="' + CSS.escape(id) + '"]'); if (g) g.classList.add('cc-selected'); }
  }
  function linkList(ids){
    if (!ids.length) return '<p class="cc-sub">None</p>';
    return '<ul>' + ids.map(function(x){
      var n = M.nodes[x.id];
      return '<li><button class="cc-link" type="button" data-cc-node="' + esc(x.id) + '">' + esc(n ? n.label : x.id) +
        '</button>' + (x.label ? ' <span class="cc-sub">(' + esc(x.label) + ')</span>' : '') + '</li>';
    }).join('') + '</ul>';
  }
  function open(id){
    var n = M.nodes[id]; if (!n) return;
    if (!panel) build();
    current = id;
    var d = M.details[id] || {};
    var chapters = M.views.filter(function(v){ return v.focus.indexOf(id) !== -1; });
    var ins = M.edges.filter(function(e){ return e.to === id; }).map(function(e){ return {id: e.from, label: e.label}; });
    var outs = M.edges.filter(function(e){ return e.from === id; }).map(function(e){ return {id: e.to, label: e.label}; });
    var h = '<button class="cc-close" type="button" aria-label="Close details">&times;</button>';
    h += '<span class="cc-eyebrow">' + esc(n.type || 'Component') + '</span>';
    h += '<h2 id="cc-detail-title">' + esc(n.label) + '</h2>';
    if (n.sublabel) h += '<p class="cc-sub">' + esc(n.sublabel) + '</p>';
    if (d.what) h += '<h3>What it does</h3><p>' + esc(d.what) + '</p>';
    if (d.why) h += '<h3>Why it matters</h3><p>' + esc(d.why) + '</p>';
    if (d.example) h += '<h3>Example</h3><p class="cc-example">' + esc(d.example) + '</p>';
    if (!d.what && chapters.length) {
      h += '<h3>In the story</h3><ul>' + chapters.map(function(v){
        return '<li><strong>' + esc(v.label) + '</strong>' + (v.note ? ': ' + esc(v.note) : '') + '</li>'; }).join('') + '</ul>';
    }
    h += '<h3>Receives from</h3>' + linkList(ins);
    h += '<h3>Sends to</h3>' + linkList(outs);
    h += '<details><summary>Technical details</summary><p class="cc-sub">ID <code>' + esc(id) + '</code>' +
         (chapters.length ? ' &middot; chapters: ' + esc(chapters.map(function(v){ return v.label; }).join(', ')) : '') + '</p></details>';
    panel.innerHTML = h;
    panel.scrollTop = 0;
    panel.querySelector('.cc-close').addEventListener('click', close);
    panel.querySelectorAll('[data-cc-node]').forEach(function(b){
      b.addEventListener('click', function(){ select(b.getAttribute('data-cc-node')); });
    });
    panel.setAttribute('data-open', 'true');
    markSelected(id);
  }
  function select(id){
    holdCamera();
    if (window.Archify && Archify.focus && Archify.focus.set) { try { Archify.focus.set(id); } catch (_) {} }
    open(id);
  }

  function docked(){ return spec.template === 'presenter' && innerWidth >= 1000; }
  function tagChrome(svg){
    [].forEach.call(svg.children, function(el){
      if ((el.getAttribute('fill') || '').indexOf('url(#grid') === 0) el.setAttribute('data-cc-grid', '');
    });
    [].forEach.call(svg.querySelectorAll('text'), function(t){
      if (/^\s*legend\s*$/i.test(t.textContent)) {
        var g = t; while (g.parentNode && g.parentNode !== svg) g = g.parentNode;
        if (g !== svg) g.setAttribute('data-cc-legend', '');
      }
    });
  }
  // Fit the viewBox to the real content so the graph fills the frame.
  function cropToContent(svg){
    var skip = function(el){ return el.closest('[data-cc-legend]') && spec.hide.indexOf('legend') !== -1; };
    var parts = [].filter.call(svg.querySelectorAll('rect.c-lane, g[data-node-id], text, path, line'), function(el){
      return !skip(el) && !el.closest('defs') && !(el.closest('[data-cc-grid]'));
    });
    var x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
    parts.forEach(function(el){
      try { var b = el.getBBox(); if (!b.width && !b.height) return;
        x1 = Math.min(x1, b.x); y1 = Math.min(y1, b.y); x2 = Math.max(x2, b.x + b.width); y2 = Math.max(y2, b.y + b.height); } catch (_) {}
    });
    if (!isFinite(x1)) return;
    var pad = 8;
    svg.setAttribute('viewBox', [x1 - pad, y1 - pad, (x2 - x1) + 2 * pad, (y2 - y1) + 2 * pad].map(function(v){ return Math.round(v); }).join(' '));
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  }
  function hostTheme(){
    var want = null;
    try { want = new URLSearchParams(location.search).get('theme'); } catch (_) {}
    if (want !== 'light' && want !== 'dark') want = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    if (window.Archify && Archify.theme && Archify.theme.set) { try { Archify.theme.set(want, {persist: false}); } catch (_) {} }
    root.setAttribute('data-theme', want);
  }
  function init(){
    holdCamera();
    var svg0 = document.querySelector('.diagram-container svg');
    if (svg0) tagChrome(svg0);
    if (spec.template === 'embed' || spec.template === 'minimal' || spec.template === 'story') {
      hostTheme();
      if (svg0) cropToContent(svg0);
    }
    if (spec.details && docked()) {
      placeholder();
      // Layout changed (panel column reserved): refit once, before any selection.
      try { if (Archify.view && Archify.view.reset) Archify.view.reset({automatic: true}); } catch (_) {}
    }
    var svg = document.querySelector('.diagram-container svg');
    if (spec.details && svg) {
      svg.addEventListener('click', function(ev){
        var g = ev.target.closest('[data-node-id]');
        if (g && M.nodes[g.getAttribute('data-node-id')]) open(g.getAttribute('data-node-id'));
        else if (!g) close();
      });
      svg.addEventListener('keydown', function(ev){
        if (ev.key !== 'Enter' && ev.key !== ' ') return;
        var g = ev.target.closest('[data-node-id]');
        if (g && M.nodes[g.getAttribute('data-node-id')]) open(g.getAttribute('data-node-id'));
      });
    }
    if (spec.template === 'embed' || spec.template === 'minimal') {
      try { if (window.Archify && Archify.view && Archify.view.reset) Archify.view.reset({automatic: true}); } catch (_) {}
      window.addEventListener('resize', function(){
        try { if (Archify.view && Archify.view.reset) Archify.view.reset({automatic: true}); } catch (_) {}
      });
    }
    if ((spec.template === 'embed' || spec.template === 'story') && window.parent !== window && svg0) {
      var report = function(){
        var vb = svg0.viewBox.baseVal; if (!vb || !vb.width) return;
        var gv = document.getElementById('guided-views'); var extra = (gv && gv.offsetHeight) ? gv.offsetHeight + 6 : 0;
        var h = Math.round(innerWidth * vb.height / vb.width) + 2 + extra;
        try { window.parent.postMessage({type: 'creator-diagram-height', height: h}, '*'); } catch (_) {}
      };
      report(); window.addEventListener('resize', report);
    }
    window.CreatorTemplate = { spec: spec, open: select, close: close, current: function(){ return current; } };
    root.setAttribute('data-cc-ready', 'true');
  }
  if (document.readyState === 'complete') setTimeout(init, 0);
  else window.addEventListener('load', function(){ setTimeout(init, 0); }, {once: true});
})();
"""
