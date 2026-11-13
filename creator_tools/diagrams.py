"""Pinned, local Archify integration. Not an OS sandbox or a video renderer."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'integrations/archify-lock.json'
TYPES = ('architecture', 'workflow', 'sequence', 'dataflow', 'lifecycle')


def child_environment():
    """Do not forward API keys, Node overrides, repo roots or upstream flags."""
    keys = ('PATH', 'HOME', 'TMPDIR', 'TEMP', 'TMP', 'SystemRoot', 'WINDIR')
    return {**{k: os.environ[k] for k in keys if k in os.environ},
            'ARCHIFY_UPDATE_CHECK_DISABLED': '1'}


def verify_install(root=ROOT):
    vendor = Path(root)/'archify'
    if not vendor.is_dir():
        raise RuntimeError('Archify missing. Run creator.py diagram install --archive <pinned archify.zip>; see docs/DIAGRAMS.md')
    lock = json.loads(LOCK.read_text())
    if vendor.is_symlink():
        raise RuntimeError('Archify integrity failure: vendor is a symlink')
    actual = set()
    for p in vendor.rglob('*'):
        if p.is_symlink():
            raise RuntimeError('Archify integrity failure: symlink in package')
        if p.is_file():
            name = p.relative_to(vendor).as_posix()
            actual.add(name)
            if hashlib.sha256(p.read_bytes()).hexdigest() != lock['files'].get(name):
                raise RuntimeError(f'Archify integrity failure: {name}')
    if actual != set(lock['files']):
        raise RuntimeError('Archify integrity failure: package files missing')
    return vendor


def install(archive, root=ROOT):
    """Explicit local archive only; no network, package manager or overwrite."""
    root = Path(root)
    destination = root/'archify'
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Archify directory exists; preserve it and review any upgrade manually')
    lock = json.loads(LOCK.read_text())
    data = Path(archive).expanduser().read_bytes()
    if hashlib.sha256(data).hexdigest() != lock['sha256']:
        raise ValueError('Archify archive SHA-256 does not match the reviewed pin')
    # Staging is on the target volume; never extract arbitrary zip paths.
    with tempfile.TemporaryDirectory(prefix='.archify-install-', dir=root) as tmp:
        staging = Path(tmp)
        vendor = staging/'archify'
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            seen = set()
            for item in z.infolist():
                if item.is_dir():
                    continue
                p = PurePosixPath(item.filename)
                if (len(p.parts) < 2 or p.parts[0] != 'archify' or '..' in p.parts
                        or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16)):
                    raise ValueError('Unsafe Archify archive path')
                name = p.relative_to('archify').as_posix()
                content = z.read(item)
                if name in seen or hashlib.sha256(content).hexdigest() != lock['files'].get(name):
                    raise ValueError('Archify archive file integrity mismatch')
                seen.add(name)
                target = vendor/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            if seen != set(lock['files']):
                raise ValueError('Archify archive files missing')
        verify_install(staging)
        # Exclusive mkdir avoids replacing an installation created concurrently.
        destination.mkdir()
        try:
            for child in vendor.iterdir():
                shutil.move(str(child), str(destination/child.name))
        except BaseException:
            shutil.rmtree(destination)
            raise
    verify_install(root)
    return {'ok': True, 'version': lock['version'], 'path': str(destination),
            'sha256': lock['sha256']}


def reject_remote_brands(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'brand' and not (isinstance(item, str) and re.fullmatch(r'[A-Za-z0-9._-]+', item)):
                raise ValueError('Remote/object brand capture is disabled; use a bundled brand ID or omit brand')
            reject_remote_brands(item)
    elif isinstance(value, list):
        for item in value:
            reject_remote_brands(item)


def _showcase_bridge_script(dwell_ms: float = 2500.0):
    """Deterministic window.__ready / __advance(ms) / __done() bridge for Archify HTML."""
    dwell = max(250, int(round(float(dwell_ms))))
    return f"""
<script id="creator-showcase-bridge">
(function() {{
  try {{
    var DWELL = {dwell};
    var elapsed = 0;
    var step = -2;
    var done = false;
    var views = [];
    try {{
      var el = document.getElementById('archify-guided-views-data');
      views = JSON.parse(el ? el.textContent : '[]') || [];
    }} catch (_) {{ views = []; }}
    window.__ready = false;
    window.__done = function() {{ return done; }};
    window.__advance = function(ms) {{
      elapsed += Number(ms) || 0;
      var target = Math.floor(elapsed / DWELL) - 1;
      if (target === step) return;
      step = target;
      if (!window.Archify || !Archify.guidedViews) {{
        if (elapsed >= DWELL) done = true;
        return;
      }}
      if (step < 0) {{
        Archify.guidedViews.showAll({{ updateUrl: false }});
      }} else if (step < views.length) {{
        Archify.guidedViews.activate(views[step].id, {{ updateUrl: false }});
        if (Archify.guidedViews.settleHandoff) Archify.guidedViews.settleHandoff('showcase');
      }} else {{
        Archify.guidedViews.showAll({{ updateUrl: false }});
        done = true;
      }}
    }};
    var markReady = function() {{
      if (window.Archify && Archify.readerLayout && typeof Archify.readerLayout.whenStable === 'function') {{
        Archify.readerLayout.whenStable().then(function() {{ window.__ready = true; }}).catch(function() {{ window.__ready = true; }});
      }} else {{
        window.__ready = true;
      }}
    }};
    if (document.readyState === 'complete') setTimeout(markReady, 50);
    else window.addEventListener('load', function() {{ setTimeout(markReady, 50); }}, {{ once: true }});
  }} catch (_) {{ window.__ready = true; }}
}})();
</script>
"""


def run(action, source=None, output=None, quality='showcase', root=ROOT,
        showcase_bridge=False, chapter_dwell_ms: float = 2500.0,
        template='full', hide=None, show=None, details=None):
    if action not in ('doctor', 'validate', 'render'):
        raise ValueError('Unsupported diagram action')
    if quality not in ('standard', 'showcase'):
        raise ValueError('Unknown quality profile')
    from creator_tools import diagram_templates as tpl
    spec = tpl.resolve(template, hide, show)
    vendor = verify_install(root)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Archify requires Node.js >=18 on PATH')
    cli = vendor/'bin/archify.mjs'

    def invoke(args):
        try:
            result = subprocess.run([node, str(cli), *args], cwd=root,
                                    env=child_environment(), capture_output=True,
                                    text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Archify operation timed out; no final output published') from exc
        if result.returncode:
            raise RuntimeError('Archify failed: '+(result.stderr or result.stdout).strip())
        return result.stdout

    if action == 'doctor':
        return {'ok': True, 'version': json.loads(LOCK.read_text())['version'],
                'report': invoke(['doctor']).strip()}
    if source is None:
        raise ValueError('Diagram input is required')
    source = Path(source).expanduser().resolve()
    raw = source.read_bytes()
    diagram = json.loads(raw)
    if not isinstance(diagram, dict) or diagram.get('diagram_type') not in TYPES:
        raise ValueError('Input must declare a supported diagram_type')
    reject_remote_brands(diagram)
    detail_map = tpl.load_details(details, diagram)
    # Freeze the vetted input so a concurrent source edit cannot introduce a URL brand.
    with tempfile.TemporaryDirectory(prefix='creator-diagram-') as tmp:
        frozen = Path(tmp)/'input.json'
        frozen.write_bytes(raw)
        kind = diagram['diagram_type']
        if action == 'validate':
            report = json.loads(invoke(['validate', kind, str(frozen), '--quality', quality, '--json']))
            if report.get('ok') is not True:
                raise RuntimeError('Archify validation failed: '+json.dumps(report))
            return {'ok': True, 'input': str(source), 'quality': quality, 'report': report}
        if output is None:
            raise ValueError('render requires --output')
        target = Path(output).expanduser().absolute()
        if target.suffix.lower() != '.html':
            raise ValueError('Diagram output must be .html')
        if target.exists() or target.is_symlink():
            raise FileExistsError('Output exists; select a new path')
        candidate = Path(tmp)/'diagram.html'
        report = json.loads(invoke(['deliver', kind, str(frozen), str(candidate),
                                   '--quality', quality, '--json']))
        if report.get('ok') is not True or not candidate.is_file():
            raise RuntimeError('Archify delivery failed: '+json.dumps(report))
        content = candidate.read_bytes()
        content = tpl.apply(content, diagram, spec, detail_map)
        if showcase_bridge:
            bridge = _showcase_bridge_script(chapter_dwell_ms).encode('utf-8')
            if b'</body>' in content:
                content = content.replace(b'</body>', bridge + b'\n</body>', 1)
            else:
                content = content + bridge
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(content)
    return {'ok': True, 'output': str(target), 'input': str(source),
            'diagram_type': kind, 'quality': quality, 'upstream_delivery_passed': True,
            'showcase_bridge': bool(showcase_bridge),
            'template': spec, 'details_authored': sorted(detail_map),
            'input_sha256': hashlib.sha256(raw).hexdigest(),
            'output_sha256': hashlib.sha256(content).hexdigest(),
            'version': json.loads(LOCK.read_text())['version'],
            'visual_review_required': True}
