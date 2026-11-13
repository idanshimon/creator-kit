"""Offline code-authored GSAP compositions; never edits or upgrades vendor code."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def doctor(*, root=None):
    """Verify the exact local runtime and return non-secret dependency metadata."""
    base = Path(root) if root is not None else ROOT
    lock = json.loads((base / 'integrations/gsap-lock.json').read_text())
    for candidate in lock['runtime_candidates']:
        runtime = base / candidate
        if not runtime.is_file():
            continue
        version = json.loads((runtime.parent.parent / 'package.json').read_text())['version']
        if version != lock['version']:
            raise ValueError(f'GSAP version mismatch: expected {lock["version"]}, got {version}')
        digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
        if digest != lock['runtime_sha256']:
            raise ValueError('GSAP runtime checksum mismatch; restore the pinned dependency, do not edit the lock blindly')
        return {'version': version, 'runtime': str(runtime.resolve()), 'runtime_sha256': digest,
                'integrity_verified': True, 'license_url': lock['license_url']}
    raise ValueError('Pinned GSAP runtime not found; restore the HyperFrames dependencies first; no automatic download')


def create(output, title, subtitle='One timeline. Every frame in its place.', *, root=None):
    """Create a new directory containing a standalone HTML, manifest and license."""
    for label, value, limit in [('title', title, 120), ('subtitle', subtitle, 240)]:
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f'{label} must be a single-line string of at most {limit} characters')
        if label == 'title' and not value.strip():
            raise ValueError('title must not be blank')
    destination = Path(output).expanduser()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'Refusing to overwrite {destination}')
    dependency = doctor(root=root)
    runtime = Path(dependency['runtime']).read_text()
    # HTML's parser terminates script elements even when the text is inside JS strings.
    runtime = re.sub(r'</script', r'<\\/script', runtime, flags=re.IGNORECASE)
    template = (ROOT / 'templates/motion/gsap/template.html').read_text()
    replacements = {
        'RUNTIME': runtime,
        'TITLE': html.escape(title.strip()),
        'SUBTITLE': html.escape(subtitle),
        'TITLE_SIZE': str(46 if len(title) > 80 else 66 if len(title) > 45 else 92),
    }
    document = re.sub(r'@@(RUNTIME|TITLE|SUBTITLE|TITLE_SIZE)@@', lambda m: replacements[m[1]], template)
    license_text = (ROOT / 'integrations/gsap-license.txt').read_text()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()  # atomic conflict check; do not reuse a directory
    paths = []
    result = {'html': str((destination / 'index.html').resolve()), 'duration_seconds': 8,
              'composition_id': 'gsap-motion', 'runtime': dependency,
              'capture': 'showcase', 'offline': True, 'audio': False}
    try:
        for name, text in [('index.html', document), ('GSAP-LICENSE.txt', license_text),
                           ('manifest.json', json.dumps(result, indent=2) + '\n')]:
            path = destination / name
            with path.open('x') as handle:
                handle.write(text)
            paths.append(path)
    except Exception:
        for path in paths:
            path.unlink()
        try:
            destination.rmdir()
        except OSError:
            pass
        raise
    return result
