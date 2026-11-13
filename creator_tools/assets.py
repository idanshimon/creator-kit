"""Explicitly invoked Azure asset calls; no implicit uploads or paid retries."""
import base64
import datetime
import hashlib
import json
import mimetypes
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from creator_tools.models import access_token, request_json, select_model, validate_endpoint


def _output(path):
    out = Path(path).expanduser().resolve()
    if out.exists() or out.with_suffix(out.suffix + '.provenance.json').exists():
        raise FileExistsError('Output or provenance exists; choose a new output path')
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _save(out, data, metadata):
    record = {**metadata, 'output':str(out), 'sha256':hashlib.sha256(data).hexdigest(),
              'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with out.open('xb') as f:
        f.write(data)
    with out.with_suffix(out.suffix + '.provenance.json').open('x') as f:
        json.dump(record, f, indent=2)
    return record


def generate_image(inventory, model_id, prompt, output, size='1024x1024', quality='low'):
    out = _output(output)
    if out.suffix.lower() != '.png':
        raise ValueError('Image output must be .png')
    if size not in ('1024x1024','1536x1024','1024x1536') or quality not in ('low','medium','high'):
        raise ValueError('Unsupported image size or quality')
    selected = select_model(inventory, model_id, 'image')
    if not selected['model'].startswith('gpt-image'):
        raise ValueError('This adapter supports GPT Image models only')
    url = validate_endpoint(selected['endpoint']) + '/openai/deployments/' + urllib.parse.quote(selected['deployment'],safe='') + '/images/generations?api-version=2025-04-01-preview'
    result = request_json(url, {'prompt':prompt,'n':1,'size':size,'quality':quality,'output_format':'png'},
                          {'Authorization':'Bearer ' + access_token(inventory['subscription'])})
    try:
        data = base64.b64decode(result['data'][0]['b64_json'], validate=True)
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('Provider returned no valid base64 image') from None
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Provider result is not PNG; nothing saved')
    return _save(out, data, {'operation':'image-generation','model':model_id,'prompt':prompt,'size':size,'quality':quality})


def post_multipart(url, fields, source, headers):
    boundary = 'CreatorBoundary' + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    # Fixed neutral filename prevents CRLF injection and disclosing the user's filename.
    suffix = source.suffix.lower()
    mime = mimetypes.guess_type('media'+suffix)[0] or 'application/octet-stream'
    chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="media{suffix}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    chunks.extend([source.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()])
    req = urllib.request.Request(url, data=b''.join(chunks), headers={**headers,'Content-Type':'multipart/form-data; boundary='+boundary}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Azure transcription HTTP {e.code}; verify access, deployment and media format') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Azure transcription network failure; no automatic upload retry') from None


def transcribe(inventory, model_id, source, output):
    out = _output(output)
    path = Path(source).expanduser().resolve()
    if out.suffix.lower() != '.srt':
        raise ValueError('Transcription output must be .srt')
    if not path.is_file() or path.suffix.lower() not in ('.wav','.mp3','.m4a','.mp4','.mpeg','.mpga','.webm'):
        raise ValueError('Provide a supported local audio/video file')
    if not 0 < path.stat().st_size < 25 * 1024 * 1024:
        raise ValueError('Whisper upload must be nonempty and under 25 MiB; extract/compress audio first')
    selected = select_model(inventory, model_id, 'transcription')
    if selected['model'] != 'whisper':
        raise ValueError('SRT adapter supports whisper only; diarization models require a different response contract')
    url = validate_endpoint(selected['endpoint']) + '/openai/deployments/' + urllib.parse.quote(selected['deployment'],safe='') + '/audio/transcriptions?api-version=2024-10-21'
    srt = post_multipart(url, {'response_format':'srt'}, path, {'Authorization':'Bearer '+access_token(inventory['subscription'])})
    if not re.search(r'\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}', srt):
        raise ValueError('No timed subtitles returned; nothing saved')
    return _save(out, srt.encode(), {'operation':'transcription','model':model_id,'source':str(path),
                                  'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
