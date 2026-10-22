#!/usr/bin/env python3
"""Local CTranslate2 ASR with atomic chunk checkpoints. Does not assign speakers or export final files."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from audio_common import VERSION, atomic_json, model_files, probe_audio, sha256_file, tool_path

def dependency_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None

def flags(text, logprob):
    result = []
    if logprob < -0.8:
        result.append('low_model_score_review_required')
    if re.search(r'(.{1,12}?)\1{3,}', text):
        result.append('repeated_text_review_required')
    return result

def checked_chunk(path, index, duration, count):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data['index'] != index or not 0 <= index < count:
        raise ValueError('Checkpoint index mismatch')
    if not (0 <= data['start'] < data['end'] <= duration + 0.05):
        raise ValueError('Checkpoint duration bounds invalid')
    previous = data['start']
    for segment in data['segments']:
        if not (previous <= segment['start'] <= segment['end'] <= data['end'] + 0.05):
            raise ValueError('Checkpoint segment bounds/order invalid')
        previous = segment['start']
    return data

def run(args, model_factory=None):
    if args.chunk_seconds not in (30, 60) or args.beam_size < 1 or args.threads < 1:
        raise ValueError('Use 30/60-second chunks, positive beam size and thread count')
    source = Path(args.audio).expanduser().resolve()
    if not source.is_file():
        raise ValueError('Source audio does not exist')
    model_dir = model_files(args.model_dir)
    ffmpeg, ffprobe = tool_path('ffmpeg', args.ffmpeg), tool_path('ffprobe', args.ffprobe)
    info = probe_audio(source, ffprobe)
    duration = info['duration']
    count = math.ceil(duration / args.chunk_seconds)
    prompt = Path(args.terms_file).expanduser().read_text(encoding='utf-8').strip() if args.terms_file else ''
    if len(prompt) > 1200:
        raise ValueError('Keep terms file to <=1200 characters; do not paste instructions or full prose')
    try:
        engine_version = importlib.metadata.version('faster-whisper')
    except importlib.metadata.PackageNotFoundError:
        if model_factory is None:
            raise ValueError('faster-whisper is absent; see setup.md, obtain approval before installing')
        engine_version = 'test-double'
    identity = {
        'skill_version': VERSION, 'source': str(source), 'source_sha256': sha256_file(source),
        'model_dir': str(model_dir), 'model_files_sha256': {
            name: sha256_file(model_dir / name) for name in ('model.bin', 'config.json', 'tokenizer.json')},
        'engine': 'faster-whisper', 'engine_version': engine_version,
        'runtime_versions': {name: dependency_version(name) for name in
            ('ctranslate2', 'av', 'numpy', 'onnxruntime', 'tokenizers')},
        'language': args.language, 'chunk_seconds': args.chunk_seconds,
        'beam_size': args.beam_size, 'threads': args.threads, 'device': 'cpu',
        'compute_type': 'int8', 'terms_sha256': __import__('hashlib').sha256(prompt.encode()).hexdigest(),
        'word_timestamps': True, 'vad_filter': True, 'condition_on_previous_text': False,
        'duration': duration, 'chunk_count': count,
    }
    directory = Path(args.work_dir).expanduser().resolve()
    manifest_path = directory / 'run.json'
    chunks = directory / 'chunks'
    if manifest_path.exists():
        if not args.resume:
            raise ValueError('Existing run found; choose --resume or a different working directory')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['identity'] != identity:
            raise ValueError('Resume blocked: source/model/settings changed. Choose a new working directory')
    elif args.resume:
        raise ValueError('No run.json exists to resume')
    else:
        if chunks.exists() or (directory / 'segments.jsonl').exists():
            raise ValueError('Existing output without matching manifest; choose another working directory')
        manifest = {'identity': identity, 'status': 'in_progress'}
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'run.lock'
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Run lock exists. Verify no process is active before manually removing a stale lock')
    os.close(fd)
    audio_fd, audio_name = tempfile.mkstemp(prefix='asr-', suffix='.tmp.wav', dir=str(directory))
    os.close(audio_fd)
    temporary_audio = Path(audio_name)
    try:
        chunks.mkdir(exist_ok=True)
        manifest['status'] = 'in_progress'
        atomic_json(manifest_path, manifest)
        completed = {}
        for path in chunks.glob('*.json'):
            index = int(path.stem)
            data = checked_chunk(path, index, duration, count)
            expected_start = index * args.chunk_seconds
            if abs(data['start'] - expected_start) > .05 or abs(data['end'] - min(duration, expected_start + args.chunk_seconds)) > .05:
                raise ValueError('Checkpoint chunk interval mismatch')
            completed[index] = data
        model = None
        for index in range(count):
            if index in completed:
                continue
            if model is None:
                if model_factory is None:
                    os.environ['HF_HUB_OFFLINE'] = '1'
                    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
                    from faster_whisper import WhisperModel
                    model_factory = WhisperModel
                model = model_factory(str(model_dir), device='cpu', compute_type='int8',
                                      cpu_threads=args.threads, local_files_only=True)
            start, end = index * args.chunk_seconds, min(duration, (index + 1) * args.chunk_seconds)
            subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-y', '-ss', str(start),
                            '-i', str(source), '-t', str(end - start), '-vn', '-ac', '1',
                            '-ar', '16000', '-c:a', 'pcm_s16le', str(temporary_audio)], check=True)
            segments, _ = model.transcribe(str(temporary_audio), language=args.language,
                beam_size=args.beam_size, condition_on_previous_text=False, word_timestamps=True,
                vad_filter=True, initial_prompt=prompt or None)
            result = []
            for segment in segments:
                left, right = start + segment.start, start + segment.end
                if not 0 <= segment.start <= segment.end <= end - start + .1:
                    raise ValueError('ASR segment outside chunk; checkpoint not committed')
                text = segment.text.strip()
                result.append({'id': f'{index}:{len(result)}', 'chunk': index,
                    'start': round(left, 3), 'end': round(min(right, end), 3), 'text': text,
                    'avg_logprob': segment.avg_logprob, 'no_speech_prob': segment.no_speech_prob,
                    'speaker': '说话人待确认', 'review_flags': flags(text, segment.avg_logprob),
                    'words': [{'start': round(start + w.start, 3), 'end': round(min(start + w.end, end), 3),
                               'word': w.word, 'probability': w.probability} for w in (segment.words or [])]})
            data = {'index': index, 'start': start, 'end': end, 'segments': result,
                    'empty': not result}
            atomic_json(chunks / f'{index:06d}.json', data)
            completed[index] = data
            print(json.dumps({'completed_chunks': len(completed), 'total_chunks': count,
                              'processed_through': end}, ensure_ascii=False), flush=True)
        ordered = [completed[i] for i in range(count)]
        for i in range(count):
            checked_chunk(chunks / f'{i:06d}.json', i, duration, count)
        temp_segments = directory / 'segments.jsonl.tmp'
        with temp_segments.open('w', encoding='utf-8') as out:
            for chunk in ordered:
                for segment in chunk['segments']:
                    out.write(json.dumps(segment, ensure_ascii=False, allow_nan=False) + '\n')
        os.replace(temp_segments, directory / 'segments.jsonl')
        manifest.update(status='asr_complete_review_pending', completed_chunks=count,
            empty_chunks=[c['index'] for c in ordered if c['empty']],
            coverage={'start': 0, 'end': duration},
            note='Coverage means every audio chunk was processed, not that every spoken word was recovered.')
        atomic_json(manifest_path, manifest)
        return manifest
    finally:
        temporary_audio.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--work-dir', required=True)
    parser.add_argument('--model-dir', required=True, help='Existing local CTranslate2 model directory, not a model name')
    parser.add_argument('--language', default='zh')
    parser.add_argument('--terms-file')
    parser.add_argument('--chunk-seconds', type=int, default=60)
    parser.add_argument('--beam-size', type=int, default=5)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = parser.parse_args()
    try:
        result = run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({'status': result['status'], 'coverage': result['coverage']}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
