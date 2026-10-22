#!/usr/bin/env python3
"""Local community-1 diarization and conservative word-time alignment. No downloads."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
from audio_common import VERSION, atomic_json, sha256_file


def validate_turns(turns):
    for turn in turns:
        if not (math.isfinite(turn['start']) and math.isfinite(turn['end']) and
                0 <= turn['start'] < turn['end'] and isinstance(turn['speaker'], str)):
            raise ValueError('Invalid diarization turn')
    return sorted(turns, key=lambda x: (x['start'], x['end'], x['speaker']))


def attribute(start, end, turns):
    """Require >=60% coverage and no competing voice; do not hide overlaps."""
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
        raise ValueError('Invalid ASR time interval')
    scores = {}
    for turn in turns:
        overlap = max(0, min(end, turn['end']) - max(start, turn['start']))
        if overlap > 0:
            scores[turn['speaker']] = scores.get(turn['speaker'], 0) + overlap
    ranked = sorted(scores, key=lambda k: (-scores[k], k))
    if not ranked:
        return '说话人待确认', 'no_voice_match'
    if len(ranked) > 1:
        return '说话人待确认', 'multiple_voices_or_boundary'
    if scores[ranked[0]] / (end - start) < .6:
        return '说话人待确认', 'insufficient_coverage'
    return ranked[0], 'automatic_diarization'


def align(segments, turns):
    """Split by timed words, retaining original segment metadata and exact word text."""
    result = []
    for index, segment in enumerate(segments):
        words = segment.get('words') or []
        if words:
            units = []
            for word in words:
                start, end = float(word['start']), float(word['end'])
                if not segment['start'] <= start < end <= segment['end'] + .05:
                    raise ValueError('Word outside source segment; repair timestamps before alignment')
                label, method = attribute(start, end, turns)
                if units and units[-1]['speaker'] == label and units[-1]['speaker_method'] == method:
                    units[-1]['end'] = end
                    units[-1]['text'] += word['word']
                    units[-1]['words'].append(word)
                else:
                    units.append({'start': start, 'end': end, 'text': word['word'],
                                  'words': [word], 'speaker': label, 'speaker_method': method})
            # Token text and segment text can differ: preserve both for review.
            mismatch = ''.join(w['word'] for w in words).strip() != segment['text'].strip()
        else:
            label, method = attribute(float(segment['start']), float(segment['end']), turns)
            units = [dict(segment, speaker=label, speaker_method=method)]
            mismatch = False
        for part, unit in enumerate(units):
            result.append(dict(segment, **unit, source_segment_index=index,
                               source_segment_text=segment['text'],
                               alignment_part=part, word_text_mismatch_review_required=mismatch))
    return result


def run(args, factory=None):
    source = Path(args.audio).expanduser().resolve()
    model = Path(args.pipeline_dir).expanduser().resolve()
    target = Path(args.work_dir).expanduser().resolve()
    if not source.is_file() or not (model / 'config.yaml').is_file():
        raise ValueError('Need existing audio and a complete local community-1 directory with config.yaml; see setup.md')
    if args.num_speakers is not None and args.num_speakers < 1:
        raise ValueError('num-speakers must be positive; omit to infer automatically')
    if target.exists():
        raise ValueError('Working directory already exists; choose a new directory to protect prior results')
    segments = None
    if args.segments:
        segments = [json.loads(line) for line in Path(args.segments).expanduser().read_text(encoding='utf-8').splitlines() if line.strip()]
    # Set before importing pyannote/HF. Model loading never receives a remote ID/token.
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', PYANNOTE_METRICS_ENABLED='0')
    if factory is None:
        try:
            from pyannote.audio import Pipeline
        except ImportError as error:
            raise ValueError('Missing compatible pyannote environment; obtain installation approval, see setup.md') from error
        factory = Pipeline.from_pretrained
    pipeline = factory(str(model))
    if pipeline is None:
        raise ValueError('Local pipeline could not load; no online fallback was requested')
    target.mkdir(parents=True, exist_ok=False)
    identity = {'skill_version': VERSION, 'audio_sha256': sha256_file(source),
                'model_files_sha256': {str(p.relative_to(model)): sha256_file(p)
                    for p in sorted(model.rglob('*')) if p.is_file() and '.git' not in p.parts and '.cache' not in p.parts},
                'num_speakers': args.num_speakers,
                'asr_sha256': sha256_file(Path(args.segments).expanduser()) if args.segments else None}
    for name in ('pyannote.audio', 'torch', 'torchcodec'):
        try:
            identity[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            identity[name] = None
    atomic_json(target / 'run.json', {'identity': identity, 'status': 'in_progress'})
    kwargs = {'num_speakers': args.num_speakers} if args.num_speakers else {}
    # Process the whole recording: independently clustering chunks would reset identities.
    output = pipeline(str(source), **kwargs)
    annotation = output.speaker_diarization
    turns = validate_turns([{'start': float(turn.start), 'end': float(turn.end), 'speaker': str(speaker)}
                            for turn, speaker in annotation])
    labels = {}
    for turn in turns:
        labels.setdefault(turn['speaker'], f'说话人 {len(labels) + 1}')
    for turn in turns:
        turn['speaker'] = labels[turn['speaker']]
    atomic_json(target / 'diarization.json', {'turns': turns, 'label_map': labels,
                'method': 'pyannote-community-1-local', 'names_identified': False})
    if segments is not None:
        aligned = align(segments, turns)
        atomic_json(target / 'aligned.json', {'segments': aligned})
    atomic_json(target / 'run.json', {'identity': identity, 'status': 'diarization_complete_review_pending',
                'turn_count': len(turns), 'speaker_count': len(labels),
                'alignment': 'aligned.json' if segments is not None else None,
                'empty_result_review_required': not bool(turns)})
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audio', required=True)
    p.add_argument('--pipeline-dir', required=True)
    p.add_argument('--work-dir', required=True)
    p.add_argument('--segments', help='Optional bundled ASR segments.jsonl, same full recording/time origin')
    p.add_argument('--num-speakers', type=int, help='Only set when the actual count is known')
    try:
        print(run(p.parse_args()))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
