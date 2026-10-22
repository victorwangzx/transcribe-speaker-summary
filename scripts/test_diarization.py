"""Offline interface/alignment tests, not model accuracy tests."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from diarize_local import align, attribute, run, validate_turns

class DiarizationTests(unittest.TestCase):
    def test_switch_splits_words(self):
        turns = [{'start': 0., 'end': 1., 'speaker': 'A'}, {'start': 1., 'end': 2., 'speaker': 'B'}]
        segments = [{'start': 0., 'end': 2., 'text': '甲乙', 'words': [
            {'start': 0., 'end': .8, 'word': '甲'}, {'start': 1.2, 'end': 2., 'word': '乙'}]}]
        result = align(segments, turns)
        self.assertEqual([p['speaker'] for p in result], ['A','B'])
        self.assertEqual(''.join(p['text'] for p in result), '甲乙')
        self.assertTrue(all(p['source_segment_text'] == '甲乙' for p in result))

    def test_ambiguity(self):
        self.assertEqual(attribute(0, 1, [dict(start=0,end=1,speaker='A'),dict(start=.5,end=1,speaker='B')])[0], '说话人待确认')
        self.assertEqual(attribute(0, 1, [dict(start=0,end=.2,speaker='A')])[1], 'insufficient_coverage')
        self.assertEqual(attribute(0, 1, [])[1], 'no_voice_match')

    def test_missing_words_preserved(self):
        original = dict(start=0,end=2,text='原句')
        result = align([original], [dict(start=0,end=1,speaker='A'),dict(start=1,end=2,speaker='B')])
        self.assertEqual(result[0]['text'], '原句')
        self.assertEqual(result[0]['speaker'], '说话人待确认')

    def test_bad_times(self):
        with self.assertRaises(ValueError):
            validate_turns([dict(start=0,end=float('nan'),speaker='A')])

    def test_pipeline_contract_and_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); audio=root/'audio.wav'; audio.write_bytes(b'fixture')
            model=root/'model'; model.mkdir(); (model/'config.yaml').write_text('fixture')
            asr=root/'asr.jsonl'; asr.write_text(json.dumps(dict(start=0,end=1,text='hi'))+'\n')
            args=argparse.Namespace(audio=str(audio), pipeline_dir=str(model), work_dir=str(root/'out'), segments=str(asr), num_speakers=None)
            def factory(path):
                self.assertEqual(path, str(model.resolve()))
                def pipeline(source, **kwargs):
                    self.assertEqual(source, str(audio.resolve())); self.assertEqual(kwargs,{})
                    return SimpleNamespace(speaker_diarization=[(SimpleNamespace(start=0,end=1),'S0')])
                return pipeline
            run(args,factory)
            out=json.loads((root/'out'/'aligned.json').read_text())
            self.assertEqual(out['segments'][0]['speaker'],'说话人 1')
            self.assertEqual(audio.read_bytes(),b'fixture')
            with self.assertRaises(ValueError): run(args,factory)

if __name__ == '__main__': unittest.main()
