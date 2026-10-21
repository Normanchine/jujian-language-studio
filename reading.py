"""Local reading practice: validated papers, resumable attempts and immutable results."""
from __future__ import annotations

import copy
import json
import time
import math
import re
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from study import ASSETS, DATA
from reading_analysis import ReadingAnalysisBridge
from reading_materials import load_bundle
from reading_import import ReadingImportBridge


def catalogue_source(row, source):
    row.update(sourceLabel=source['label'], sourceKind=source['kind'])
    if source['kind'] != 'toefl_personal_materials':return row
    records=source.get('records',[])
    canonical=next((r for r in records if r.get('record_id')==source.get('canonical_record_id')),None)
    primary=canonical or next((r for r in records if r.get('source_group')), {})
    group=primary.get('source_group') or '来源待整理'
    month=re.match(r'(\d+)\s*月',group)
    month_number=int(month.group(1)) if month else 0
    label=group.split('/',1)[-1]
    date=re.search(r'\d+\.(\d+)',label)
    row.update(group=f'托福资料 · {month_number}月' if month else '托福资料 · 其他',
               setId='toefl-source-'+sha256(group.encode()).hexdigest()[:12],setTitle=label,
               sourceGroup=group,sourceGroups=sorted({r['source_group'] for r in records if r.get('source_group')}),
               order=month_number*100000+(int(date.group(1)) if date else 0)*1000+row['order']%1000)
    return row


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def validate_paper(raw: dict) -> dict:
    if not isinstance(raw,dict):
        raise ValueError('阅读材料格式无效')
    paper = copy.deepcopy(raw)
    if paper.get('schema_version') != 1 or not paper.get('id') or not paper.get('title'):
        raise ValueError('阅读材料格式无效')
    source = paper.get('source', {})
    if not isinstance(source,dict) or (source.get('kind') != 'self_authored_demo' and source.get('review_status') != 'approved'):
        raise ValueError('阅读材料尚未复核')
    if not source.get('label') or not isinstance(paper.get('body'),str) or not paper['body'].strip():
        raise ValueError('阅读来源或原文缺失')
    paragraphs = paper['body'].split('\n\n')
    questions = paper.get('questions', [])
    if not isinstance(questions,list) or not questions:
        raise ValueError('没有可作答的题目')
    seen = set()
    for q in questions:
        if not isinstance(q,dict) or not q.get('id') or q['id'] in seen or q.get('type') != 'single':
            raise ValueError('题号重复或题型尚未支持')
        seen.add(q['id'])
        if not q.get('stem') or not isinstance(q.get('options'),list) or len(q['options']) != 4 or not all(isinstance(x,str) and x.strip() for x in q['options']):
            raise ValueError('题干或选项不完整')
        if q.get('answer') not in ('A','B','C','D') or not q.get('explanation'):
            raise ValueError('答案或解析缺失')
        for e in q.get('evidence', []):
            p = e.get('paragraph', 0)
            if not 1 <= p <= len(paragraphs) or not e.get('quote') or e['quote'] not in paragraphs[p-1]:
                raise ValueError('原文依据无法定位')
    return paper


class ReadingBridge(QObject):
    changed = Signal()
    catalogueChanged = Signal()
    clockChanged = Signal()
    homeStateChanged = Signal()
    summariesChanged = Signal()
    error = Signal(str)

    def __init__(self, storage: Path | None = None, papers: list[dict] | None = None, bank_path: Path | None = None):
        super().__init__()
        self._dir = Path(storage) if storage else Path(DATA) / 'reading'
        self._intensive = ReadingAnalysisBridge(self._dir / 'intensive', self)
        self._importer = ReadingImportBridge(self._dir / 'personal-articles.json', self)
        self._importer.imported.connect(lambda _id: self.catalogueChanged.emit())
        self._home_path = self._dir.parent / 'reading-home.json'
        try:
            self._home_state = json.loads(self._home_path.read_text(encoding='utf-8'))
            if not isinstance(self._home_state,dict): self._home_state = {}
        except (OSError,ValueError):
            self._home_state = {}
        raw = papers if papers is not None else json.loads((ASSETS / 'assets/reading-demo.json').read_text(encoding='utf-8'))['papers']
        bundle = load_bundle(Path(bank_path) if bank_path else self._dir / 'materials' / 'toefl-reviewed.json') if papers is None else {'papers': [], 'intensive_articles': []}
        raw = [*raw, *bundle['papers']]
        self._intensive_articles = bundle['intensive_articles']
        if len({p['id'] for p in raw}) != len(raw):
            raise ValueError('阅读材料编号重复')
        self._papers = {p['id']: validate_paper(p) for p in raw}
        self._records = {}
        self._broken = []
        for path in (self._dir / 'attempts').glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(record,dict):
                    raise ValueError('作答记录格式无效')
                if record.get('schema_version') != 1 or path.stem != record['id'] or record['status'] not in ('active','submitted'):
                    raise ValueError('作答记录格式无效')
                validate_paper(record['paper'])
                questions = record['paper']['questions']
                keys = {q['id'] for q in questions}
                if not isinstance(record.get('index'),int) or not 0 <= record['index'] < len(questions):
                    raise ValueError('作答题号无效')
                if not isinstance(record.get('answers'),dict) or any(k not in keys or v not in ('A','B','C','D') for k,v in record['answers'].items()):
                    raise ValueError('作答选项无效')
                if not isinstance(record.get('elapsed'),(int,float)) or not math.isfinite(record['elapsed']) or record['elapsed'] < 0:
                    raise ValueError('计时记录无效')
                if not isinstance(record.get('activity_at'),(int,float)) or not isinstance(record.get('flags'),list) or any(k not in keys for k in record['flags']):
                    raise ValueError('作答状态无效')
                if record['status']=='submitted' and (not record.get('submitted_at') or record.get('correct') != sum(record['answers'].get(q['id'])==q['answer'] for q in questions)):
                    raise ValueError('交卷结果不一致')
                self._records[record['id']] = record
            except (ValueError, KeyError, TypeError, OSError):
                self._broken.append(path.name)
        self._active = None
        self._last_activity = max((r['activity_at'] for r in self._records.values()),default=0)
        self._stage = 'idle'
        self._running_since = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _elapsed(self):
        return self._active.get('elapsed',0) + (time.monotonic()-self._running_since if self._running_since is not None else 0) if self._active else 0

    def _stamp(self):
        self._last_activity = max(int(time.time()*1000), self._last_activity+1)
        return self._last_activity

    def _checkpoint(self):
        if self._active and self._active['status'] == 'active':
            if self._running_since is not None:
                self._active['elapsed'] = self._elapsed()
                self._running_since = time.monotonic()
            try:
                write_json(self._dir / 'attempts' / (self._active['id']+'.json'), self._active)
            except OSError as exc:
                self.error.emit('阅读记录保存失败：'+str(exc)); return False
        return True

    def _tick(self):
        if self._running_since is not None:
            try:
                if int(self._elapsed()) % 5 == 0:
                    self._checkpoint()
                self.clockChanged.emit()
            except OSError as exc:
                self.error.emit('阅读记录保存失败：'+str(exc))

    @Property('QVariantList', notify=catalogueChanged)
    def importedCatalogue(self):
        return self._importer.catalogue()

    @Property('QVariantList', notify=catalogueChanged)
    def catalogue(self):
        rows = [catalogue_source(dict(id=p['id'], title=p['title'], body=p['body'], language=p['language'], group=p['group'], setId=p['setId'], setTitle=p['setTitle'],
                     number=p['number'], order=p['order'], hasQuestions=True, practice='new', visited=0, intensive='new', mock=False,
                     questionCount=len(p['questions'])),p['source']) for p in self._papers.values()] + [
                         catalogue_source({k: copy.deepcopy(v) for k,v in a.items() if k != 'source'},a['source'])
                         for a in self._intensive_articles]
        numbers={}
        for row in sorted(rows,key=lambda a:(a.get('sourceGroup',''),a['order'])):
            if row.get('sourceKind')=='toefl_personal_materials':
                numbers[row['setId']]=numbers.get(row['setId'],0)+1
                row['number']=numbers[row['setId']]
        return rows + self._importer.catalogue()

    @Property(QObject, constant=True)
    def importer(self):
        return self._importer

    @Property(QObject, constant=True)
    def intensive(self):
        return self._intensive

    @Property('QVariantMap', notify=homeStateChanged)
    def homeState(self):
        return self._home_state

    @Slot('QVariantMap')
    def saveHomeState(self, state):
        try:
            write_json(self._home_path,state)
            self._home_state = copy.deepcopy(state); self.homeStateChanged.emit()
        except OSError as exc:
            self.error.emit('阅读页面状态保存失败：'+str(exc))

    @Property(int, notify=clockChanged)
    def elapsed(self):
        return int(self._elapsed())

    @Property('QVariantMap', notify=summariesChanged)
    def summaries(self):
        output = {}
        for paper_id, paper in self._papers.items():
            rows = [a for a in self._records.values() if a['paper']['id'] == paper_id]
            done = sorted([a for a in rows if a['status'] == 'submitted'], key=lambda a:a['submitted_at'], reverse=True)
            pending = sorted([a for a in rows if a['status'] == 'active'], key=lambda a:a['activity_at'], reverse=True)
            last = max(rows,key=lambda a:a['activity_at']) if rows else None
            active = pending[0] if pending else None
            completed = done[0] if done else None
            output[paper_id] = dict(practice='done' if completed else 'progress' if active else 'new', pending=bool(active),
                completed=bool(completed), questionCount=len((active or completed or {'paper':paper})['paper']['questions']), answered=len(active['answers']) if active else len(completed['answers']) if completed else 0,
                score=f"{completed['correct']}/{len(completed['paper']['questions'])}" if completed else '',
                wrong=len(completed['paper']['questions'])-completed['correct'] if completed else 0,
                lastPracticeAt=last['activity_at'] if last else 0, practiceCompletedAt=completed['submitted_at'] if completed else 0)
        return output

    @Property('QVariantMap', notify=changed)
    def view(self):
        a = self._active
        if not a:
            return dict(stage='idle',index=0,total=0,answered=0,paused=False,correct=0,question={'options':[]},navigation=[],history=[],selected='',body='',source='')
        paper = a['paper']
        q = paper['questions'][a['index']]
        review = self._stage == 'review'
        question = {k:copy.deepcopy(q[k]) for k in ('id','stem','type','options')}
        if review:
            question.update(answer=q['answer'], explanation=q['explanation'], evidence=q.get('evidence',[]))
        return dict(stage=self._stage, id=a['id'], paperId=paper['id'], title=paper['title'], language=paper['language'], source=paper['source']['label'],
            body=paper['body'], paragraphs=paper['body'].split('\n\n'), index=a['index'], total=len(paper['questions']),
            question=question, selected=a['answers'].get(q['id'],''), answered=len(a['answers']), elapsed=int(self._elapsed()),
            paused=self._stage == 'exercise' and self._running_since is None, correct=a.get('correct',0), submittedAt=a.get('submitted_at',0),
            passagePosition=a.get('passage_position',0), flagged=q['id'] in a.get('flags',[]),
            navigation=[dict(number=i+1, answered=item['id'] in a['answers'], flagged=item['id'] in a.get('flags',[]),
                             correct=a['answers'].get(item['id']) == item['answer'] if review else None) for i,item in enumerate(paper['questions'])],
            history=[dict(id=r['id'], label=time.strftime('%m-%d %H:%M',time.localtime(r['submitted_at']/1000))+f" · {r['correct']}/{len(r['paper']['questions'])}")
                     for r in sorted(self._records.values(),key=lambda r:r.get('submitted_at',0),reverse=True) if r['paper']['id']==paper['id'] and r['status']=='submitted'])

    def _load(self, record, stage):
        self.leave()
        self._active = record
        self._stage = stage
        self._running_since = time.monotonic() if stage == 'exercise' else None
        if stage == 'exercise':
            self._active['activity_at'] = self._stamp(); self._checkpoint(); self.summariesChanged.emit()
        self.changed.emit(); self.clockChanged.emit()

    @Slot(str, result=bool)
    def open(self, paper_id):
        if paper_id not in self._papers:
            self.error.emit('这篇材料仅供精读，暂没有已核对的练习题。' if any(a['id']==paper_id for a in self._intensive_articles)
                            else '这条仅用于目录布局演示，没有可作答的题目。')
            return False
        rows = [a for a in self._records.values() if a['paper']['id']==paper_id]
        pending = sorted([a for a in rows if a['status']=='active'],key=lambda a:a['activity_at'],reverse=True)
        done = sorted([a for a in rows if a['status']=='submitted'],key=lambda a:a['submitted_at'],reverse=True)
        if pending:
            self._load(pending[0], 'exercise')
        elif done:
            self._load(done[0], 'review')
        else:
            return self._new(paper_id)
        return True

    def _new(self, paper_id):
        now = self._stamp()
        record = dict(schema_version=1, id=uuid4().hex, paper=copy.deepcopy(self._papers[paper_id]), status='active',
            answers={}, flags=[], index=0, elapsed=0.0, created_at=now, activity_at=now, passage_position=0)
        self._records[record['id']] = record
        self._load(record,'exercise')
        if not self._checkpoint():
            self._running_since=None; self._stage='idle'; self.changed.emit(); return False
        self.summariesChanged.emit()
        return True

    @Slot(str)
    def answer(self, letter):
        if self._stage != 'exercise' or self._running_since is None or letter not in ('A','B','C','D'):
            return
        self._active['answers'][self._active['paper']['questions'][self._active['index']]['id']] = letter
        self._active['activity_at'] = self._stamp()
        self._checkpoint(); self.changed.emit(); self.summariesChanged.emit()

    @Slot(int)
    def chooseQuestion(self, index):
        if not self._active or not 0 <= index < len(self._active['paper']['questions']):
            return
        if self._stage == 'exercise' and self._running_since is None:
            return
        if self._stage == 'review':
            self._active = copy.deepcopy(self._active)
        self._active['index'] = index
        self._checkpoint(); self.changed.emit()

    @Slot()
    def flag(self):
        if self._stage != 'exercise' or self._running_since is None:
            return
        flags = self._active['flags']; key = self._active['paper']['questions'][self._active['index']]['id']
        flags.remove(key) if key in flags else flags.append(key)
        self._checkpoint(); self.changed.emit()

    @Slot(float)
    def savePassagePosition(self, position):
        if self._stage == 'exercise' and self._active:
            self._active['passage_position'] = max(0,position)
            self._checkpoint()

    @Slot()
    def togglePause(self):
        if self._stage != 'exercise':
            return
        self._checkpoint()
        self._running_since = time.monotonic() if self._running_since is None else None
        self.changed.emit()

    @Slot(result=bool)
    def submit(self):
        if self._stage != 'exercise':
            return False
        if not self._checkpoint():
            return False
        result = copy.deepcopy(self._active)
        result.update(status='submitted', submitted_at=self._stamp())
        result['activity_at'] = result['submitted_at']
        result['correct'] = sum(result['answers'].get(q['id'])==q['answer'] for q in result['paper']['questions'])
        try:
            write_json(self._dir / 'attempts' / (result['id']+'.json'), result)
        except OSError as exc:
            self.error.emit('交卷保存失败，请重试：'+str(exc)); return False
        self._running_since = None
        self._records[result['id']] = result; self._active = copy.deepcopy(result); self._stage='review'
        self.changed.emit(); self.clockChanged.emit(); self.summariesChanged.emit(); return True

    @Slot()
    def redo(self):
        if self._active and self._stage=='review':
            self.open(self._active['paper']['id']) if any(r['status']=='active' and r['paper']['id']==self._active['paper']['id'] for r in self._records.values()) else self._new(self._active['paper']['id'])

    @Slot(str)
    def reviewAttempt(self, attempt_id):
        record = self._records.get(attempt_id)
        if record and record['status']=='submitted':
            self._load(copy.deepcopy(record),'review')

    @Slot()
    def leave(self):
        self._checkpoint(); self._running_since=None; self._stage='idle'; self._active=None; self.changed.emit(); self.clockChanged.emit()
