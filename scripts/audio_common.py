"""Standard-library helpers; no installation, network or media mutation on import."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

VERSION = '2.1.0'

def tool_path(name, override=None):
    value = str(Path(override).expanduser()) if override else shutil.which(name)
    if not value or not Path(value).is_file():
        raise ValueError(f'Missing {name}; supply its installed path. Nothing was installed.')
    return str(Path(value).resolve())

def probe_audio(source, ffprobe):
    command = [ffprobe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(source)]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError('ffprobe did not return valid JSON; verify this is a real audio-capable ffprobe, not a shim') from error
    audio = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    duration = float(data.get('format', {}).get('duration', 0))
    if not audio or duration <= 0:
        raise ValueError('No audio stream or positive duration could be confirmed.')
    return {'duration': duration, 'channels': audio[0].get('channels'),
            'sample_rate': audio[0].get('sample_rate')}

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def model_files(path):
    path = Path(path).expanduser().resolve()
    missing = [name for name in ('model.bin', 'config.json', 'tokenizer.json') if not (path / name).is_file()]
    if missing:
        raise ValueError('Local CTranslate2 model incomplete: ' + ', '.join(missing) +
                         '. A Whisper .pt file is not this format. No download was started.')
    return path

def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)

def timestamp(seconds):
    total = round(seconds * 1000)
    return f'{total // 3600000:02d}:{total // 60000 % 60:02d}:{total // 1000 % 60:02d}.{total % 1000:03d}'
