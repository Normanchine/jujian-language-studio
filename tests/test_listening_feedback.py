"""Regression coverage for saved annotations, media replacement and ASR repeats."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import study
from linguistics import cached_display_tokens, display_tokens
from core.subtitle_timing import repair_collapsed_repetitions


def prompt(number, start, collapsed=False):
    body = '会社で女の人と男の人が話しています'
    prefix = f'{number}番'
    words = [{'text': prefix, 'start': start, 'end': start + 1}]
    words += [{'text': ch, 'start': start + 1 + (0 if collapsed else i * .2),
               'end': start + 1 + (0 if collapsed else (i + 1) * .2)} for i, ch in enumerate(body)]
    return {'start': start, 'end': words[-1]['end'], 'text': prefix + ' ' + body,
            'words': words, 'translation': 'Old translation', 'analysis': {}}


class SubtitleTimingTests(unittest.TestCase):
    def test_collapsed_repeat_keeps_number_and_recovery_evidence(self):
        source = [prompt(5, 0), prompt(5, 35, True)]
        before = copy.deepcopy(source)
        fixed, audit = repair_collapsed_repetitions(source)
        self.assertEqual(source, before)
        self.assertEqual(fixed[1]['text'], '5番')
        self.assertEqual(fixed[1]['end'], 36)
        self.assertEqual(fixed[1]['translation'], '')
        self.assertEqual(audit[0]['original'], before[1])
        self.assertEqual(repair_collapsed_repetitions(fixed), (fixed, []))

    def test_real_repeat_reviewed_and_unaligned_are_preserved(self):
        first = prompt(5, 0)
        for following in (prompt(5, 35), {**prompt(5, 35, True), 'reviewed': True},
                          {**prompt(5, 35, True), 'analysis': {'model': 'manual'}},
                          {**prompt(5, 35, True), 'words': []}, prompt(5, 200, True)):
            with self.subTest(following=following):
                source = [first, following]
                self.assertEqual(repair_collapsed_repetitions(source), (source, []))

    def test_collapsed_new_text_is_not_removed(self):
        source = [prompt(5, 35, True)]
        self.assertEqual(repair_collapsed_repetitions(source), (source, []))


class SavedAnnotationTests(unittest.TestCase):
    def test_saved_annotations_skip_dictionary(self):
        words = [{'text': '私', 'start': 0, 'end': 1}, {'text': 'です', 'start': 1, 'end': 2}]
        tokens = display_tokens('私です', words)
        raw = [{'text': '私です', 'start': 0, 'end': 2, 'words': words, 'tokens': tokens,
                'analysis': {'source_text': '私です', 'vocabulary': [{'surface': '私', 'meaning': '我'}]}}]
        with patch.object(study, 'display_tokens', side_effect=AssertionError('unnecessary dictionary load')), \
             patch('enrich_job.display_tokens', side_effect=AssertionError('analysis reloaded dictionary')):
            self.assertEqual(study.validate_segments(raw, 2, reuse_tokens=True)[0]['tokens'], tokens)
        changed = [{**words[0], 'end': .7}, {**words[1], 'start': .7}]
        self.assertIsNone(cached_display_tokens('私です', changed, tokens))
        self.assertIsNone(cached_display_tokens('彼です', words, tokens))

    def test_english_gaps_reuse_exact_word_times(self):
        words = [{'text': 'Hello,', 'start': 0, 'end': .3}, {'text': 'world.', 'start': 1, 'end': 2}]
        tokens = display_tokens('Hello, world.', words, 'en')
        self.assertEqual(cached_display_tokens('Hello, world.', words, tokens, 'en'), tokens)

    def test_probe_survives_restart_but_invalidates_on_media_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / 'audio.wav'
            media.write_bytes(b'original')
            path = Path(temporary) / 'project.json'
            path.write_text(json.dumps({'media_path': str(media), 'language': 'en', 'segments': []}), encoding='utf-8')
            study._inspect_unchanged_media.cache_clear()
            with patch.object(study, 'inspect_media', return_value=(False, 10)) as probe:
                project = study.read_project(path)
                study.read_project(path)
                self.assertEqual(probe.call_count, 1)
                path.write_text(json.dumps(project), encoding='utf-8')
                study._inspect_unchanged_media.cache_clear()  # A new process has no in-memory cache.
                study.read_project(path)
                self.assertEqual(probe.call_count, 1)
                media.write_bytes(b'replacement media')
                study.read_project(path)
                self.assertEqual(probe.call_count, 2)


if __name__ == '__main__':
    unittest.main()
