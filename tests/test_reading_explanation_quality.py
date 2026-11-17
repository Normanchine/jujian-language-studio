"""Prevent metadata leaks in new output, cached output and saved explanations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QCoreApplication
from reading_analysis import ReadingAnalysisBridge,grammar_candidates,validate_annotations,engine_identity
from reading_explanation_quality import teaching_fields,saved_explanation_view

APP=QCoreApplication.instance() or QCoreApplication([])
TEXT='説明を聞いてから、本を見つけることができました。'
IDENTITY={'backend':'fixture','model':'self-authored-grammar-check'}


def good_response():
    return {'annotations':[dict(candidate_id=c['candidate_id'],meaning='表示能够完成这个动作。',
        connection=c['connection'],point='本句表示听完说明后，能够找到书。') for c in grammar_candidates(TEXT)]}


def wait(bridge):
    deadline=time.monotonic()+5
    while bridge.view['busy'] and time.monotonic()<deadline:
        APP.processEvents();time.sleep(.005)
    APP.processEvents()
    if bridge.view['busy']:raise AssertionError('analysis worker timed out')


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.identity=patch('reading_analysis.engine_identity',return_value=IDENTITY)
        self.identity.start()

    def tearDown(self):
        self.identity.stop();self.temp.cleanup()

    def bridge(self, requester=None):
        value=ReadingAnalysisBridge(self.root,requester=requester)
        value.openDocument('grammar-test','ja',TEXT,'自编例句','Local fixture')
        return value

    def test_internal_text_is_rejected_in_every_displayed_field(self):
        for key in ('meaning','point','connection'):
            for leak in ('虽然候选g31_36涵盖整体，但g31_34值得解释。','band为unknown','candidate_id = g0','请返回JSON解释'):
                item=dict(meaning='正常解释',point='说明实际用法',connection='辞书形＋结构')
                item[key]=leak
                with self.subTest(key=key,leak=leak),self.assertRaises(ValueError):teaching_fields(item)
        with self.assertRaises(ValueError):teaching_fields(dict(meaning='解释',point={'candidate_id':'g0'}))
        self.assertEqual(teaching_fields(dict(meaning='这里的 band 是乐队。'))['meaning'],'这里的 band 是乐队。')

    def test_full_possible_structure_including_past_and_negative_is_preserved(self):
        for ending in ('ました','ませんでした','なかった','ます','る'):
            text='本を見つけることができ'+ending+'。'
            choices=grammar_candidates(text)
            self.assertTrue(any(c['text']=='ことができ'+ending and c['band']=='basic' for c in choices),choices)
            self.assertFalse(any(c['text']=='ことが' for c in choices),choices)

    def test_valid_other_annotations_survive_rejected_explanation(self):
        raw=good_response()
        self.assertGreaterEqual(len(raw['annotations']),2)
        raw['annotations'][0]['point']='g31_34 比 g31_36 更合适，band为unknown'
        valid,rejected=validate_annotations(raw,dict(paragraph=0,start=0,text=TEXT),[TEXT])
        self.assertEqual(rejected,1)
        self.assertEqual(len(valid),len(raw['annotations'])-1)

    def test_dirty_cache_is_not_displayed_and_is_replaced_only_by_clean_reply(self):
        bridge=self.bridge()
        part=dict(paragraph=0,start=0,text=TEXT)
        path=bridge._analysis_path(IDENTITY,part);path.parent.mkdir(parents=True)
        raw=good_response();raw['annotations'][0]['point']='band为unknown，参考g31_34'
        path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
        before=path.read_bytes()
        calls=[]
        reader=self.bridge(lambda *args:(calls.append(args),good_response())[1])
        self.assertFalse(reader.view['analyzed'])
        self.assertNotIn('g31_34',json.dumps(reader.view['annotations'],ensure_ascii=False))
        self.assertEqual(path.read_bytes(),before)
        reader.analyze(False);wait(reader)
        self.assertEqual(len(calls),1)
        self.assertTrue(reader.view['analyzed'],reader.view['status'])
        self.assertNotIn('g31_34',path.read_text(encoding='utf-8'))

    def test_one_bad_reply_retries_and_manual_correction_survives(self):
        calls=[]
        def request(*args):
            calls.append(args)
            raw=good_response()
            if len(calls)==1:raw['annotations'][0]['point']='候选g31_34的band为unknown'
            return raw
        reader=self.bridge(request)
        valid,_=validate_annotations(good_response(),dict(paragraph=0,start=0,text=TEXT),[TEXT])
        reader._grammar=valid
        self.assertTrue(reader.correctAnnotation(valid[0]['id'],'我保存的手动解释'))
        reader.analyze(True);wait(reader)
        self.assertEqual(len(calls),2)
        self.assertTrue(reader.view['analyzed'],reader.view['status'])
        corrected=next(a for a in reader.view['annotations'] if a['id']==valid[0]['id'])
        self.assertEqual(corrected['meaning'],'我保存的手动解释')
        self.assertEqual(corrected['source'],'已更正')

    def test_repeated_bad_replies_keep_previous_valid_cache_and_explanation(self):
        reader=self.bridge()
        part=dict(paragraph=0,start=0,text=TEXT)
        path=reader._analysis_path(IDENTITY,part);path.parent.mkdir(parents=True)
        path.write_text(json.dumps(good_response()),encoding='utf-8')
        before=path.read_bytes()
        calls=[]
        def bad(*args):
            calls.append(args)
            raw=good_response()
            for a in raw['annotations']:a['point']='g31_34属于候选列表'
            return raw
        reader=self.bridge(bad)
        old=copy.deepcopy(reader.view['annotations'])
        reader.analyze(True);wait(reader)
        self.assertEqual(len(calls),2)
        self.assertFalse(reader.view['analyzed'])
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(reader.view['annotations'],old)

    def test_partial_reply_caches_only_valid_content_and_can_be_reused(self):
        calls=[]
        def partial(*args):
            calls.append(args)
            raw=good_response();raw['annotations'][0]['point']='内部编号g31_34不应显示'
            return raw
        reader=self.bridge(partial)
        reader.analyze(True);wait(reader)
        self.assertEqual(len(calls),2)
        self.assertTrue(reader.view['analyzed'])
        path=reader._analysis_path(IDENTITY,dict(paragraph=0,start=0,text=TEXT))
        self.assertNotIn('g31_34',path.read_text(encoding='utf-8'))
        reader.analyze(False);wait(reader)
        self.assertEqual(len(calls),2)

    def test_old_favorite_metadata_is_hidden_without_rewriting_or_hiding_manual_text(self):
        raw=dict(meaning='形式名词',point='候选g31_34，band为unknown',source='AI')
        before=copy.deepcopy(raw)
        shown=saved_explanation_view(raw)
        self.assertTrue(shown['needsReanalysis'])
        self.assertNotIn('g31_34',shown['point'])
        self.assertEqual(raw,before)
        raw['source']='已更正'
        self.assertEqual(saved_explanation_view(raw)['point'],raw['point'])


if __name__=='__main__':unittest.main()
