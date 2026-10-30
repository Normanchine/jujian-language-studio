"""Actual local DOCX/PDF conversion and independent multi-passage exercises."""
import json
import sys
from pathlib import Path
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
from PySide6.QtCore import QCoreApplication
from document_conversion import convert_document
from reading import ReadingBridge
from reading_structure import canonical
from multipaper_fixture import PAPERS

app = QCoreApplication.instance() or QCoreApplication([])
folder = ROOT / 'test-download/multipaper-20261030'
output = ROOT / 'release-verification/multipaper-20261030'
output.mkdir(parents=True, exist_ok=True)
report = []

for extension in ('docx', 'pdf'):
    source = folder / ('three-passages.' + extension)
    print('Converting', extension, flush=True)
    raw = convert_document(source, folder / ('converted-' + extension), 'local',
        'F:/MinerU/venv/Scripts/python.exe', 'en', '', threading.Event(),
        lambda message: print(message, flush=True), device='cpu')
    with tempfile.TemporaryDirectory(prefix='jujian-multipaper-') as temporary:
        storage = Path(temporary) / 'reading'
        reader = ReadingBridge(storage, papers=[])
        importer = reader.paperImporter
        calls = []
        def reject_model(*args, **kwargs):
            calls.append(True)
            raise AssertionError('Source answer keys must not be replaced by an AI guess')
        importer.requester = reject_model
        importer.prepareAutomatically(raw, 'Three passages fixture', 'en', source.name, 'local')
        assert importer.view['parsed'] and not importer.view['busy'], importer.view
        assert importer.view['questionCount'] == 6 and importer.view['missing'] == 0, importer.view
        assert not calls
        first_id = importer.save(True)
        assert first_id, importer.view
        papers = importer.stored_papers()
        assert len(papers) == 3 and len({p['setId'] for p in papers}) == 1
        for expected, actual in zip(PAPERS, papers):
            assert canonical(actual['body']) == canonical(expected['body']), (extension, actual['title'])
            assert len(expected['questions']) == len(actual['questions'])
            for eq, aq in zip(expected['questions'], actual['questions']):
                assert str(eq['number']) == aq['number']
                assert canonical(eq['stem']) == canonical(aq['stem'])
                assert [canonical(s) for s in eq['options']] == [canonical(s) for s in aq['options']]
                assert aq['answer'] == eq['answer'], (extension, eq['number'], aq['answer'])
        scores = []
        for pi, paper in enumerate(papers):
            assert reader.open(paper['id'])
            for qi, q in enumerate(paper['questions']):
                reader.chooseQuestion(qi)
                assert 'answer' not in reader.view['question'] and 'explanation' not in reader.view['question']
                reader.answer('A' if pi == 0 and qi == 0 else q['answer'])
            if pi < 2:
                assert reader.submit()
                scores.append(reader.view['correct'])
            reader.leave()
        assert scores == [1, 3], scores
        reopened = ReadingBridge(storage, papers=[])
        for pi, paper in enumerate(papers):
            assert reopened.open(paper['id'])
            if pi < 2:
                assert reopened.view['stage'] == 'review' and reopened.view['correct'] == scores[pi]
            else:
                assert reopened.view['stage'] == 'exercise' and reopened.view['selected'] == 'D'
                assert 'answer' not in reopened.view['question']
                assert reopened.submit() and reopened.view['correct'] == 1
            reopened.leave()
        assert importer.save(True) == first_id
        assert len(importer.stored_papers()) == 3
        row = {'format': extension, 'passed': True, 'papers': 3, 'questions_per_paper': [2, 3, 1],
               'central_source_keys': True, 'question_and_passage_binding': True,
               'source_keys_required_no_model_calls': not calls, 'scores': ['1/2', '3/3', '1/1'],
               'resume_and_reopen': True, 'duplicate_preserves_library': True, 'answers_hidden_until_submit': True}
        report.append(row)
        print('PASS', json.dumps(row), flush=True)
(output / 'documents-result.json').write_text(json.dumps({'passed': True, 'results': report}, indent=2), encoding='utf-8')
