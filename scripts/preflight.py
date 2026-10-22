#!/usr/bin/env python3
"""Read-only checks. No install, download, output file or directory creation."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
from audio_common import VERSION, tool_path, model_files, probe_audio

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio')
    parser.add_argument('--model-dir')
    parser.add_argument('--work-dir')
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = parser.parse_args()
    checks = {'python_3_9_or_newer': sys.version_info >= (3, 9), 'audio_selected': bool(args.audio)}
    details = {'skill_version': VERSION, 'python': sys.executable,
               'python_version': platform.python_version(), 'platform': platform.platform()}
    paths = {}
    for name in ('ffmpeg', 'ffprobe'):
        try:
            paths[name] = tool_path(name, getattr(args, name))
            checks[name] = True
            details[name] = paths[name]
        except ValueError as error:
            checks[name] = False
            details[name] = str(error)
    try:
        details['faster_whisper'] = importlib.metadata.version('faster-whisper')
        checks['asr_package_present'] = True
    except importlib.metadata.PackageNotFoundError:
        checks['asr_package_present'] = False
    details['runtime_import_and_model_load'] = 'not tested by this read-only inspection; validate with a short sample'
    if args.model_dir:
        try:
            details['model_dir'] = str(model_files(args.model_dir))
            checks['local_model'] = True
        except ValueError as error:
            checks['local_model'] = False
            details['model_error'] = str(error)
    else:
        checks['local_model'] = False
        details['model_error'] = 'Select an existing local CTranslate2 directory, or approve a model download.'
    if args.audio:
        source = Path(args.audio).expanduser().resolve()
        checks['source_readable'] = source.is_file() and os.access(source, os.R_OK)
        if checks['source_readable'] and paths.get('ffprobe'):
            try:
                details['audio'] = probe_audio(source, paths['ffprobe'])
                checks['audio_probe'] = True
            except Exception as error:
                checks['audio_probe'] = False
                details['audio_error'] = str(error)
    if args.work_dir:
        directory = Path(args.work_dir).expanduser().resolve()
        ancestor = directory
        while not ancestor.exists():
            ancestor = ancestor.parent
        checks['work_parent_writable'] = ancestor.is_dir() and os.access(ancestor, os.W_OK)
        details['work_dir'] = str(directory)
        details['work_dir_created'] = False
    result = {'ready_for_sample': all(checks.values()), 'checks': checks, 'details': details,
              'manual_decisions': ['delivery destination and formats if unspecified',
                                   'directory replacement/confirmation',
                                   'approval before any install/download/upload',
                                   'speaker-name mapping and unclear speech when necessary']}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready_for_sample'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
