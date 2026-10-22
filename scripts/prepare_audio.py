#!/usr/bin/env python3
"""Normalize locally after a work-directory choice. Never overwrite source/existing output."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from audio_common import probe_audio, tool_path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--out-dir', required=True, help='User-selected/approved temporary working directory')
    parser.add_argument('--chunk-seconds', type=int, default=0)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = parser.parse_args()
    if args.chunk_seconds < 0:
        parser.error('--chunk-seconds cannot be negative')
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        parser.error('Source does not exist')
    ffmpeg, ffprobe = tool_path('ffmpeg', args.ffmpeg), tool_path('ffprobe', args.ffprobe)
    info = probe_audio(source, ffprobe)
    directory = Path(args.out_dir).expanduser().resolve()
    wav = directory / (source.stem + '.mono16k.wav')
    chunks = directory / 'chunks'
    if wav == source or wav.exists() or (args.chunk_seconds and chunks.exists()):
        parser.error('Output already exists or aliases source; choose a new working directory')
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source), '-vn',
                    '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
    if args.chunk_seconds:
        chunks.mkdir()
        subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(wav),
                        '-f', 'segment', '-segment_time', str(args.chunk_seconds),
                        '-c', 'copy', str(chunks / 'chunk_%06d.wav')], check=True)
    print(json.dumps({'source': str(source), 'wav': str(wav), 'audio': info,
                      'chunks_dir': str(chunks) if args.chunk_seconds else None}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
