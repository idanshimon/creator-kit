"""Package explicitly trusted, self-contained HTML; never install or deploy anything.

The conservative static preflight is not a sanitizer, JS interpreter or security
certification. Inline code and the data in the input remain the author's trust
and review responsibility. See docs/FABRIC-EXPORT.md.
"""
from __future__ import annotations

import base64
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil


# Deliberately conservative heuristics, not an ECMAScript/CSS parser.
_NETWORK = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|Worker|SharedWorker|"
    r"importScripts|sendBeacon|import|export|serviceWorker|eval)\b|\bnew\s+Function\b|"
    r"\bcreateElement(?:NS)?\s*\(|\blocation\s*(?:\.|\[|=)|"
    r"\.\s*(?:src|href|srcset)\s*=|\bdocument\s*\.\s*write(?:ln)?\s*\(|"
    r"\b(?:window|globalThis|self)\s*\.\s*open\s*\(", re.I
)
_DATA = re.compile(
    r"data:(?:image/(?:png|jpeg|gif|webp|avif|x-icon)|"
    r"font/(?:woff2?|ttf|otf)|audio/(?:mpeg|ogg|wav)|video/(?:mp4|webm));base64,([A-Za-z0-9+/=\s]+)", re.I
)
_RESOURCE_ATTRS = {'src', 'href', 'xlink:href', 'poster', 'background', 'data', 'manifest'}


def _embedded(value: str, *, fragment: bool = False) -> bool:
    value = value.strip()
    if fragment and value.startswith('#'):
        return True
    match = _DATA.fullmatch(value)
    if not match:
        return False
    try:
        return bool(base64.b64decode(re.sub(r'\s', '', match[1]), validate=True))
    except ValueError:
        return False


def _check_code(text: str) -> None:
    if _NETWORK.search(text):
        raise ValueError('HTML contains an obvious network/dynamic-code operation; only trusted offline artifacts are supported')


def _check_css(text: str) -> None:
    # Escaped CSS may conceal URL/import tokens: outside the supported subset.
    if ('\\' in text or re.search(r'@import\b|\b(?:-webkit-)?image-set\s*\(', text, re.I)):
        raise ValueError('CSS imports, image-set or escapes are outside the offline subset')
    for match in re.finditer(r'url\s*\((.*?)\)', text, re.I | re.S):
        if not _embedded(match[1].strip().strip('"\''), fragment=True):
            raise ValueError('CSS url() must be an embedded safe data URI or fragment')
    _check_code(text)


class _OfflineHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: set[str] = set()
        self.active: str | None = None
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        if tag in {'iframe', 'object', 'embed', 'frame', 'frameset', 'portal', 'base'}:
            raise ValueError(f'Unsupported active/external element: {tag}')
        if tag in {'script', 'style'}:
            self.active = tag
            self.chunks = []
        for key, raw in attrs:
            value = raw or ''
            if key in {'srcset', 'imagesrcset', 'ping', 'srcdoc', 'action', 'formaction', 'codebase', 'archive'}:
                raise ValueError(f'Unsupported runtime/navigation attribute: {key}')
            if key == 'http-equiv':
                content = dict(attrs).get('content') or ''
                if (tag != 'meta' or value.lower() != 'content-security-policy' or
                        re.search(r'\breport-(?:uri|to)\b', content, re.I)):
                    raise ValueError('Only non-reporting Content-Security-Policy HTTP-equiv is supported')
            if key == 'style':
                _check_css(value)
            if key.startswith('on'):
                _check_code(value)
            if key in _RESOURCE_ATTRS:
                if tag == 'a' and key == 'href':
                    if not (value.startswith('#') or re.match(r'^https?://[^\s]+$', value, re.I)):
                        raise ValueError('Source anchors must be http(s) links or local fragments')
                elif tag == 'script' or not _embedded(value, fragment=tag in {'use', 'image'}):
                    raise ValueError(f'External/relative runtime dependency: {tag}[{key}]')

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.active:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self.active:
            text = ''.join(self.chunks)
            (_check_css if tag == 'style' else _check_code)(text)
            self.active = None
            self.chunks = []

    def validate(self, text: str) -> None:
        self.feed(text)
        self.close()
        if not {'html', 'body'} <= self.tags or self.active:
            raise ValueError('Expected a complete UTF-8 HTML document with html/body and closed script/style tags')


_BUILD = r'''// Dependency-free local build. Not Rayfin authentication or deployment.
import { readFile, readdir, lstat, mkdir, writeFile, rm, rename, mkdtemp } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
async function plain(target, directory = false) {
  const stat = await lstat(target);
  if (stat.isSymbolicLink() || !(directory ? stat.isDirectory() : stat.isFile())) {
    throw new Error(`Integrity: expected plain ${directory ? 'directory' : 'file'}: ${target}`);
  }
}
try {
  await plain(path.join(root, 'site'), true);
  await plain(path.join(root, 'site/index.html'));
  await plain(path.join(root, 'manifest.json'));
  const entries = await readdir(path.join(root, 'site'));
  if (entries.length !== 1 || entries[0] !== 'index.html') throw new Error('Integrity: unexpected site assets');
  const manifest = JSON.parse(await readFile(path.join(root, 'manifest.json'), 'utf8'));
  const expected = manifest.files?.['site/index.html'];
  const bytes = await readFile(path.join(root, 'site/index.html'));
  const digest = createHash('sha256').update(bytes).digest('hex');
  if (manifest.schema_version !== 1 || manifest.algorithm !== 'sha256' ||
      expected?.sha256 !== digest || expected?.bytes !== bytes.length) {
    throw new Error('Integrity: site/index.html differs from packaging manifest; repackage reviewed source');
  }
  // Everything above happens before any dist or staging mutation.
  const dist = path.join(root, 'dist');
  try { await plain(dist, true); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const staging = await mkdtemp(path.join(root, '.dist-stage-'));
  try {
    await writeFile(path.join(staging, 'index.html'), bytes, { flag: 'wx' });
    await rm(dist, { recursive: true, force: true });
    await rename(staging, dist);
  } finally { await rm(staging, { recursive: true, force: true }); }
  console.log(`SHA256 verified ${digest}; built dist/index.html (${bytes.length} bytes). Local kit only; not deployed.`);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
'''

_README = '''# Protected Fabric static deployment kit

This is a local deployment kit, **not deployed**. Packaging has not installed
Rayfin, signed in, tested permissions or proved protected hosting works.

## Review before upload

The supplied HTML is an explicitly trusted artifact, including inline active
JavaScript and any embedded data. This packager is not a sanitizer or security
certification. Its conservative static checks reject common runtime dependencies
and obvious network code; computed/obfuscated JS or browser parsing edge cases
are not proven safe. Review code, data, source rights and intended audience.
Never embed secrets. Every authorized app viewer can read the entire snapshot;
semantic-model per-viewer row-level security is NOT inherited by static extracts.
Refresh the source and create a new reviewed kit to update the snapshot.

## Local build and integrity

`node scripts/build.mjs` works without installing dependencies. `npm run build`
is equivalent. The build checks the only allowed site file against the SHA256
and byte length in manifest.json before changing dist, and copies those exact
bytes. It does not recursively copy input directories or unrelated secrets.
Extra site files and symlinks are refused. manifest.json records initial hashes
for every generated file except itself. The build enforces the site hash only:
Rayfin configuration is intentionally editable for redirect registration.
Hashes establish byte identity, not authenticity, source accuracy, safe code,
lineage, data access rights, or independent analytical verification. A party
able to alter both the HTML and manifest can defeat this unsigned check.

## Manual upload (network/cloud actions; not performed by packaging)

Use supported **Node 20/22/24** for Rayfin CLI 1.36.2 (not arbitrary newer Node).
Confirm the Fabric Apps preview workload is enabled in the intended tenant,
a workspace is assigned to a running supported capacity, the deployment region
supports the workload, and the deploying identity and intended viewers have
appropriate workspace/item permissions. Review current Microsoft prerequisites:
https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli
https://learn.microsoft.com/en-us/fabric/apps/overview

From this kit directory:

```sh
npm install
npx rayfin login
npx rayfin up --workspace-id <workspace-id>
```

There is deliberately no fabricated package-lock.json; use `npm install`, NOT
`npm ci`, for the first install. The direct CLI dependency is exactly 1.36.2;
transitive packages are not locked until installation. Review/preserve the
resulting real lockfile for reproducibility. Installation may run vendor scripts.

The first deployment prints the actual hosted URL. Add that actual redirect
URL to `services.auth.allowedRedirectUris` in local `rayfin/rayfin.yml`, then run:

```sh
npx rayfin up staticapp deploy
```

Keep actual workspace/item IDs, redirect URLs, credentials and deployment state
local and out of committed configuration. Later snapshot updates require a new
reviewed export, build and staticapp deploy. Fabric auth is enabled, password auth
is disabled, assets are protected, and data/storage/functions are disabled.
These are configuration intentions, NOT a verified live access boundary.
After deployment, read status back and open the real URL as intended allowed
and disallowed users before claiming successful protected hosting.

Inspired by Sanjay Narendran's CMS Hospital Insights thin static Rayfin wrapper:
https://github.com/SanjayNarendran/MS102-public-CMS-Hospital-Insights-fabric-rayfin-GHC
This kit deliberately supports only one self-contained offline HTML file.
'''


def _record(data: bytes) -> dict:
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def package_site(input_html: str | os.PathLike, output_dir: str | os.PathLike,
                 app_name: str = 'creator-data-story') -> dict:
    """Create a new local kit from one explicitly trusted offline HTML file.

    Returns JSON-serializable metadata, never installs/runs subprocesses/cloud.
    Raises ValueError for unsupported input/name/path, FileExistsError for ANY
    existing destination (including dangling symlinks), and normal OSError for
    missing inputs/parents or IO failures. Input bytes are never modified.
    The output parent must already exist and must not itself be a symlink.
    """
    if not isinstance(app_name, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', app_name):
        raise ValueError('app_name must be a lowercase alphanumeric/hyphen slug of 1–63 characters without edge hyphens')
    source = Path(input_html).absolute()
    output = Path(output_dir).absolute()
    if os.path.lexists(output):
        raise FileExistsError(f'Refusing existing output: {output}')
    if output.parent.is_symlink():
        raise ValueError('Output parent must not be a symlink')
    if not output.parent.is_dir():
        raise FileNotFoundError(f'Output parent must already exist: {output.parent}')
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('Input must be one plain .html/.htm file, not a directory or symlink')
    data = source.read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Input must be UTF-8 HTML') from exc
    _OfflineHTML().validate(text)
    package = {'name': app_name, 'version': '1.0.0', 'private': True,
               'scripts': {'build': 'node scripts/build.mjs'},
               'engines': {'node': '20.x || 22.x || 24.x'},
               'devDependencies': {'@microsoft/rayfin-cli': '1.36.2'}}
    config = f'''id: {app_name}
name: {app_name}
version: 1.0.0
services:
  auth:
    enabled: true
    fabric:
      enabled: true
    password:
      enabled: false
    allowedRedirectUris: []
  data:
    enabled: false
  staticHosting:
    enabled: true
    folder: dist
    buildCommand: npm run build
    indexDocument: index.html
    assetAccess: protected
  storage:
    enabled: false
  functions:
    enabled: false
'''
    files = {'site/index.html': data,
             'package.json': (json.dumps(package, indent=2) + '\n').encode(),
             'rayfin/rayfin.yml': config.encode(), 'scripts/build.mjs': _BUILD.encode(),
             'README.md': _README.encode(),
             '.gitignore': b'.env\n.env.*\n**/.env\n**/.env.*\n.deployments.json\n**/.deployments.json\nnode_modules/\ndist/\n.dist-stage-*/\n'}
    manifest = {'schema_version': 1, 'algorithm': 'sha256',
                'files': {name: _record(payload) for name, payload in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    # Reserve exclusively only after all validation/serialization has succeeded.
    output.mkdir()
    try:
        for name, payload in files.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(payload)
    except BaseException:
        shutil.rmtree(output)
        raise
    return {'status': 'local-deployment-kit', 'deployed': False, 'output_dir': str(output),
            'app_name': app_name, 'manifest': str(output / 'manifest.json'),
            'manifest_sha256': _record(files['manifest.json'])['sha256'],
            'input_sha256': _record(data)['sha256'], 'files': sorted(files),
            'warnings': ['Trusted inline code and data require author review; static checks are not a sanitizer.',
                         'Not installed, authenticated or deployed; static extracts do not inherit per-viewer RLS.']}
