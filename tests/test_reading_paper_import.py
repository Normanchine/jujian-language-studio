"""Isolated importer integration: no API calls, credentials or personal data."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QUrl
from reading_paper_import import ReadingPaperImportBridge
from reading import ReadingBridge
from reading_structure import validate_extraction, source_chunks

SAMPLE = '''Passage 1  Community gardens

The community garden opens every Sunday. Volunteers grow vegetables and share them with neighbors.

1. When does the garden open?
A. Monday
B. Sunday
C. Friday
D. Tuesday
Answer: B

2. What do volunteers grow?
A. Trees
B. Flowers
C. Vegetables
D. Nothing
'''


class PaperImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / 'reading/personal-papers.json'
        self.bridge = ReadingPaperImportBridge(self.path)

    def wait(self, bridge=None):
        bridge = bridge or self.bridge
        deadline = time.monotonic() + 5
        while bridge.view['busy'] and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.app.processEvents()
        self.assertFalse(bridge.view['busy'])

    def test_import_practice_submit_reopen_duplicate_and_immutable_history(self):
        reader = ReadingBridge(self.folder / 'reading', papers=[])
        importer = reader.paperImporter
        self.assertTrue(importer.parse(SAMPLE, 'Garden paper', 'en', 'garden.md'))
        self.assertEqual('', importer.save(True))  # Missing answer cannot be graded.
        importer.setAnswer(0, 1, 'C')
        self.assertEqual('', importer.save(False))
        identity = importer.save(True)
        self.assertTrue(identity)
        self.assertTrue(reader.open(identity))
        reader.answer('B'); reader.chooseQuestion(1); reader.answer('C')
        self.assertTrue(reader.submit())
        self.assertEqual(2, reader.view['correct'])
        attempts = list((self.folder / 'reading/attempts').glob('*.json'))
        before = {p.name: p.read_bytes() for p in attempts}
        self.assertEqual(identity, importer.save(True))
        self.assertEqual(1, len(importer.stored_papers()))
        reader.leave()
        reopened = ReadingBridge(self.folder / 'reading', papers=[])
        self.assertTrue(reopened.open(identity))
        self.assertEqual(2, reopened.view['correct'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in attempts})
        raw = next((self.folder / 'reading/import-sources').glob('*.json'))
        self.assertEqual(SAMPLE, json.loads(raw.read_text())['raw'])
        reopened.leave()
        self.assertTrue(reopened.paperImporter.remove(identity))
        self.assertFalse(reopened.paperImporter.stored_papers())
        self.assertEqual(before, {p.name: p.read_bytes() for p in attempts})
        self.assertTrue((self.folder / 'reading/retired-papers' / (identity + '.json')).exists())
        self.assertTrue(reopened.paperImporter.parse(SAMPLE, 'Garden paper', 'en', 'garden.md'))
        reopened.paperImporter.setAnswer(0, 1, 'C')
        self.assertEqual(identity, reopened.paperImporter.save(True))
        self.assertTrue(reopened.open(identity))
        self.assertEqual(2, reopened.view['correct'])
        reopened.leave()

    def test_two_and_six_options_reject_unavailable_letter(self):
        text = SAMPLE.split('1. When')[0] + '''1. What is shared?
A. One
B. Two
C. Three
D. Four
E. Five
F. Vegetables
Answer: F
'''
        reader = ReadingBridge(self.folder / 'reading', papers=[])
        self.assertTrue(reader.paperImporter.parse(text, 'Six', 'en', 'six.md'))
        identity = reader.paperImporter.save(True)
        self.assertTrue(reader.open(identity))
        reader.answer('G'); self.assertEqual('', reader.view['selected'])
        reader.answer('F'); self.assertEqual('F', reader.view['selected'])
        self.assertTrue(reader.submit()); self.assertEqual(1, reader.view['correct'])
        reader.leave()
        text = text.replace('C. Three\nD. Four\nE. Five\nF. Vegetables', '').replace('Answer: F', 'Answer: B')
        self.assertTrue(self.bridge.parse(text, 'Two', 'en', 'two.md'))
        identity = self.bridge.save(True)
        self.assertTrue(identity)

    def test_failed_write_keeps_preview_and_old_library(self):
        self.bridge.parse(SAMPLE, 'Garden', 'en', 'garden.md')
        self.bridge.skipUnanswered()
        identity = self.bridge.save(True)
        original = self.path.read_bytes()
        self.bridge.setAnswer(0, 0, 'A')
        with patch('reading_paper_import.atomic_json', side_effect=OSError('disk full')):
            self.assertEqual('', self.bridge.save(True))
        self.assertEqual(original, self.path.read_bytes())
        self.assertTrue(self.bridge.view['parsed'])
        self.assertEqual(identity, self.bridge.stored_papers()[0]['id'])

    def test_source_validation_rejects_rewrite_and_invented_answer(self):
        payload = {'papers': [{'title': 'Garden', 'body': SAMPLE.split('\n\n')[1], 'questions': [
            {'number': '1', 'stem': 'When does the garden open?', 'options': ['Monday', 'Sunday', 'Friday', 'Tuesday'],
             'answer': 'B', 'answer_quote': '1 B'}]}]}
        parsed = validate_extraction(payload, SAMPLE, 'en')
        self.assertEqual('B', parsed['papers'][0]['questions'][0]['answer'])  # Bound by exact rule-parsed question.
        invented = copy.deepcopy(payload)
        invented['papers'][0]['questions'][0]['options'][0] = 'Every month'
        self.assertEqual([], validate_extraction(invented, SAMPLE, 'en')['papers'])
        invented['papers'][0]['body'] = 'This is an invented passage that is not in the document.'
        self.assertEqual([], validate_extraction(invented, SAMPLE, 'en')['papers'])

    def test_cancelled_ai_and_manual_answer_do_not_get_overwritten(self):
        release = threading.Event()
        started = threading.Event()
        def requester(*args, **kwargs):
            started.set(); release.wait(3)
            return {'answers': [{'number': 2, 'answer': 'C', 'explanation': '原文提到蔬菜',
                                  'quote': 'Volunteers grow vegetables and share them with neighbors.'}]}
        self.bridge.requester = requester
        self.bridge.parse(SAMPLE, 'Garden', 'en', 'garden.md')
        self.bridge.fillAnswers('local')
        self.assertTrue(started.wait(1))
        self.bridge.setAnswer(0, 1, 'D')
        release.set(); self.wait()
        self.assertEqual('D', self.bridge.view['questions'][1]['answer'])
        self.bridge.parse(SAMPLE, 'Garden', 'en', 'garden.md')
        release.clear(); started.clear(); self.bridge.fillAnswers('local')
        self.assertTrue(started.wait(1))
        self.bridge.invalidate(); release.set()
        for _ in range(20):
            self.app.processEvents(); time.sleep(.005)
        self.assertFalse(self.bridge.view['parsed'])

    def test_file_conversion_uses_snapshot_and_ui_signal(self):
        source = self.folder / 'source.pdf'; source.write_bytes(b'fake PDF adapter fixture')
        called = []
        def converter(path, output, mode, python, language, pages, cancel, progress, **kwargs):
            called.append((path, mode, language, pages)); progress('fixture progress')
            return SAMPLE
        self.bridge.converter = converter
        ready = []
        self.bridge.sourceReady.connect(lambda *values: ready.append(values))
        self.bridge.loadFile(QUrl.fromLocalFile(str(source)).toString(), 'local', 'python.exe', '1-2', 'en')
        self.wait()
        self.assertEqual('1-2', called[0][3]); self.assertEqual(SAMPLE, ready[0][0])
        self.assertEqual(SAMPLE, self.bridge.view['raw'])

    def test_long_paper_batches_repeat_passage_and_preserve_all_questions(self):
        body = 'Passage 1 Garden\n\nThe community garden opens on Sunday.\n\n'
        questions = '\n\n'.join(f'{i}. Which option is correct?\nA. First option\nB. Second option' for i in range(1, 25))
        chunks = source_chunks(body + questions, limit=400)
        self.assertGreater(len(chunks), 1)
        all_numbers = []
        for chunk in chunks:
            self.assertIn('The community garden opens on Sunday.', chunk)
            all_numbers.extend(q['number'] for p in __import__('reading_quiz').parse_reading_papers(chunk, 'en')['papers'] for q in p['questions'])
        self.assertEqual(list(range(1, 25)), all_numbers)

    def test_corrupt_library_is_preserved_and_blocks_new_import(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('{broken', encoding='utf-8')
        importer = ReadingPaperImportBridge(self.path)
        self.assertFalse(importer.parse(SAMPLE, 'Garden', 'en', 'sample.md'))
        self.assertEqual('{broken', self.path.read_text())

    def test_automatic_preparation_separates_AI_key_from_question_preview(self):
        def requester(*args, **kwargs):
            return {'answers': [{'number': 2, 'answer': 'C', 'explanation': '原文提到蔬菜',
                                  'quote': 'Volunteers grow vegetables and share them with neighbors.'}]}
        self.bridge.requester = requester
        self.bridge.prepareAutomatically(SAMPLE, 'Garden', 'en', 'sample.md', 'local')
        self.wait()
        self.assertEqual(0, self.bridge.view['missing'])
        paper_id = self.bridge.save(True)
        self.assertTrue(paper_id)
        reader = ReadingBridge(self.folder / 'reading', papers=[])
        reader.open(paper_id)
        self.assertNotIn('answer', reader.view['question'])
        self.assertNotIn('explanation', reader.view['question'])
        reader.answer('B'); reader.chooseQuestion(1)
        self.assertNotIn('answer', reader.view['question'])
        reader.answer('C'); reader.submit()
        self.assertEqual('C', reader.view['question']['answer'])
        self.assertEqual('ai', reader.view['question']['answerSource'])
        reader.leave()

    def test_model_chunks_keep_document_wide_source_answers(self):
        from multipaper_fixture import raw_text
        from reading_quiz import parse_reading_papers
        def requester(prompt, *args, **kwargs):
            chunk = prompt.split('<source>\n', 1)[1].rsplit('\n</source>', 1)[0]
            papers = parse_reading_papers(chunk, 'en')['papers']
            # Simulate a formatter that returns no keys from its isolated chunk.
            for p in papers:
                for q in p['questions']:
                    q.update(answer='', answer_quote='', explanation='')
            return {'papers': papers, 'skipped': []}
        self.bridge.requester = requester
        self.bridge.organize(raw_text(), 'Three passages', 'en', 'paper.md', 'local')
        self.wait()
        self.assertEqual(3, len(self.bridge.view['papers']))
        self.assertEqual(['B', 'D', 'A', 'C', 'B', 'D'], [q['answer'] for q in self.bridge.view['questions']])
        self.assertEqual(0, self.bridge.view['missing'])

    def test_formatter_failures_preserve_recognized_papers_without_endless_calls(self):
        from multipaper_fixture import raw_text
        calls = []
        def requester(*args, **kwargs):
            calls.append(True)
            raise ValueError('truncated model JSON')
        self.bridge.requester = requester
        self.bridge.organize(raw_text(), 'Three passages', 'en', 'paper.md', 'local')
        self.wait()
        self.assertEqual(2, len(calls))
        self.assertEqual(3, len(self.bridge.view['papers']))
        self.assertEqual(6, self.bridge.view['questionCount'])
        self.assertEqual(0, self.bridge.view['missing'])
        self.assertTrue(self.bridge.view['warnings'])


if __name__ == '__main__':
    unittest.main()
