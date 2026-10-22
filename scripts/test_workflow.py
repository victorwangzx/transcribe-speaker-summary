"""Offline behavioral tests using synthetic audio; no model/provider installation."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from audio_common import sha256_file, tool_path, probe_audio
from export_transcript import export
from transcribe_local import run

class FakeModel:
    def __init__(self, *args, **kwargs):
        self.calls = 0
    def transcribe(self, *args, **kwargs):
        self.calls += 1
        s = SimpleNamespace(start=0.1, end=1.1, text='原始中文 Agent', avg_logprob=-.2,
                            no_speech_prob=.1, words=[])
        return iter([s]), None

class EmptyModel(FakeModel):
    def transcribe(self, *args, **kwargs):
        return iter([]), None

class InterruptedModel(FakeModel):
    def transcribe(self, *args, **kwargs):
        if self.calls:
            raise RuntimeError('simulated interruption')
        return super().transcribe(*args, **kwargs)

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='transcribe-skill-test-')
        self.root = Path(self.tmp.name)
        self.ffmpeg = tool_path('ffmpeg', os.environ.get('TEST_FFMPEG'))
        self.ffprobe = tool_path('ffprobe', os.environ.get('TEST_FFPROBE'))
        self.source = self.root / '含空格 audio.wav'
        subprocess.run([self.ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                        'anullsrc=r=16000:cl=mono', '-t', '65', str(self.source)], check=True)
        self.original_hash = sha256_file(self.source)
        self.model = self.root / 'model'
        self.model.mkdir()
        for name in ('model.bin', 'config.json', 'tokenizer.json'):
            (self.model / name).write_text('{}')
        self.args = argparse.Namespace(audio=str(self.source), model_dir=str(self.model),
            work_dir=str(self.root / 'work'), ffmpeg=self.ffmpeg, ffprobe=self.ffprobe,
            chunk_seconds=30, beam_size=1, threads=1, language='zh', terms_file=None, resume=False)
    def tearDown(self):
        self.assertEqual(self.original_hash, sha256_file(self.source))
        self.tmp.cleanup()
    def quiet_run(self, factory=FakeModel):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(self.args, model_factory=factory)
    def test_continuous_time_and_duplicate_free_resume(self):
        result = self.quiet_run()
        rows = [json.loads(x) for x in (Path(self.args.work_dir) / 'segments.jsonl').read_text().splitlines()]
        self.assertEqual([r['start'] for r in rows], [.1, 30.1, 60.1])
        self.assertEqual(result['coverage']['end'], 65)
        before = (Path(self.args.work_dir) / 'segments.jsonl').read_bytes()
        self.args.resume = True
        def no_model_needed(*a, **k):
            self.fail('completed resume must not reload model')
        self.quiet_run(no_model_needed)
        self.assertEqual(before, (Path(self.args.work_dir) / 'segments.jsonl').read_bytes())
    def test_interrupted_chunk_resume(self):
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            self.quiet_run(InterruptedModel)
        directory = Path(self.args.work_dir)
        self.assertEqual(len(list((directory / 'chunks').glob('*.json'))), 1)
        self.assertFalse((directory / 'run.lock').exists())
        self.args.resume = True
        self.quiet_run()
        rows = [json.loads(x) for x in (directory / 'segments.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['id'] for r in rows}), 3)
    def test_empty_chunks_are_covered_not_dropped(self):
        result = self.quiet_run(EmptyModel)
        self.assertEqual(result['empty_chunks'], [0, 1, 2])
        self.assertEqual(result['completed_chunks'], 3)
        self.assertEqual((Path(self.args.work_dir) / 'segments.jsonl').read_text(), '')
    def test_changed_model_blocks_resume(self):
        self.quiet_run()
        (self.model / 'model.bin').write_text('changed')
        self.args.resume = True
        with self.assertRaisesRegex(ValueError, 'source/model/settings changed'):
            self.quiet_run()
    def test_changed_terms_blocks_resume(self):
        terms = self.root / 'terms.txt'; terms.write_text('Agent')
        self.args.terms_file = str(terms)
        self.quiet_run(); self.args.resume = True; terms.write_text('OA')
        with self.assertRaisesRegex(ValueError, 'source/model/settings changed'):
            self.quiet_run()
    def test_active_lock_is_not_removed(self):
        directory = Path(self.args.work_dir); directory.mkdir(); (directory / 'run.lock').write_text('active')
        with self.assertRaisesRegex(ValueError, 'Run lock exists'):
            self.quiet_run()
        self.assertEqual((directory / 'run.lock').read_text(), 'active')
    def test_incompatible_ffprobe_is_explained(self):
        with patch('audio_common.subprocess.run', return_value=SimpleNamespace(stdout='invalid-json')):
            with self.assertRaisesRegex(ValueError, 'real audio-capable ffprobe'):
                probe_audio(self.source, self.ffprobe)
    def test_preflight_missing_model_does_not_create_workdir(self):
        script = Path(__file__).with_name('preflight.py')
        directory = self.root / 'not-created'
        result = subprocess.run([os.sys.executable, str(script), '--audio', str(self.source),
            '--model-dir', str(self.root / 'missing'), '--work-dir', str(directory),
            '--ffmpeg', self.ffmpeg, '--ffprobe', self.ffprobe], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['checks']['local_model'])
        self.assertFalse(directory.exists())
    def test_prepare_preserves_original_and_refuses_existing_output(self):
        script = Path(__file__).with_name('prepare_audio.py')
        command = [os.sys.executable, str(script), str(self.source), '--out-dir', str(self.root / 'prepared'),
                   '--ffmpeg', self.ffmpeg, '--ffprobe', self.ffprobe]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        wav = Path(json.loads(first.stdout)['wav']); expected = sha256_file(wav)
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(expected, sha256_file(wav))
    def test_exports_are_chosen_and_do_not_overwrite(self):
        text = '# 转录\n\n[00:00:01—00:00:02] 说话人待确认：中文 **Agent**。\n'
        source = self.root / 'reviewed.md'; source.write_text(text)
        out = self.root / 'final'
        export(source, out / 'chosen.txt', 'txt')
        self.assertEqual([p.name for p in out.iterdir()], ['chosen.txt'])
        self.assertIn('中文 Agent', (out / 'chosen.txt').read_text())
        with self.assertRaises(ValueError):
            export(source, out / 'chosen.txt', 'txt')
        with self.assertRaises(ValueError):
            export(source, out / 'not.doc', 'docx')
        self.assertEqual(source.read_text(), text)

if __name__ == '__main__':
    unittest.main()
