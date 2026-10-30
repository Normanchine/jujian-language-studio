"""Personal reading-exam import with immutable worker inputs and source provenance."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from ai_client import ask_json
from core.storage import atomic_json
from document_conversion import convert_document, ConversionCancelled
from reading_import import detect_language
from reading_quiz import MAX_TEXT, LETTERS, parse_reading_papers, ai_answer_prompt, apply_ai_answers
from reading_structure import content_id, extraction_prompt, validate_extraction, source_chunks, canonical, formatting_source


class ReadingPaperImportBridge(QObject):
    changed = Signal()
    papersChanged = Signal()
    sourceReady = Signal(str, str, str)
    _result = Signal(int, str, object, str)
    _progress = Signal(int, str)

    def __init__(self, path, parent=None, requester=None, converter=None):
        super().__init__(parent)
        self.path = Path(path)
        self.requester = requester or ask_json
        self.converter = converter or convert_document
        self._preferences_path = self.path.with_name('paper-import-preferences.json')
        self._draft_path = self.path.with_name('paper-import-draft.json')
        self._preferences = {'python': 'F:/MinerU/venv/Scripts/python.exe', 'folder': '', 'conversion': 'local', 'backend': 'local', 'device': 'auto'}
        self._rows, self._draft, self._origin = [], None, {}
        self._generation = 0
        self._thread = None
        self._auto_backend = None
        self._cancel = threading.Event()
        self._load_error = ''
        self._view = dict(parsed=False, busy=False, stage='', error='', message='', warnings=[],
                          papers=[], questions=[], questionCount=0, missing=0, selectedCount=0, raw='', title='', filename='')
        try:
            if self._preferences_path.exists():
                prefs = json.loads(self._preferences_path.read_text(encoding='utf-8'))
                if isinstance(prefs, dict):
                    self._preferences.update({k: v for k, v in prefs.items() if k in self._preferences and isinstance(v, str)})
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(raw, dict) or raw.get('schema') != 1 or not isinstance(raw.get('papers'), list):
                    raise ValueError('个人阅读题库格式无效')
                from reading import validate_paper
                self._rows = [validate_paper(row) for row in raw['papers']]
                if len({p['id'] for p in self._rows}) != len(self._rows):
                    raise ValueError('个人阅读题编号重复')
            if self._draft_path.exists():
                pending = json.loads(self._draft_path.read_text(encoding='utf-8'))
                if (isinstance(pending, dict) and pending.get('schema') == 1 and isinstance(pending.get('raw'), str)
                        and len(pending['raw']) <= MAX_TEXT):
                    self._view.update(raw=pending['raw'], title=str(pending.get('title', '')), filename=str(pending.get('filename', '')),
                                      message='已恢复上次导入文本，可重新识别；未确认题目不会自动入库。')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self._load_error = '导入数据读取失败，原文件已保留：' + str(exc)
            self._view['error'] = self._load_error
        self._result.connect(self._finish)
        self._progress.connect(self._show_progress)

    @Property('QVariantMap', notify=changed)
    def view(self):
        return copy.deepcopy(self._view)

    @Property('QVariantMap', notify=changed)
    def preferences(self):
        return dict(self._preferences)

    @Property(str, notify=changed)
    def lastSourceFolder(self):
        folder = Path(self._preferences['folder'])
        return QUrl.fromLocalFile(str(folder)).toString() if self._preferences['folder'] and folder.is_dir() else ''

    def stored_papers(self):
        return copy.deepcopy(self._rows)

    def _error(self, message):
        self._view.update(error=message, busy=False, stage='')
        self.changed.emit()

    def _refresh(self):
        papers, questions = [], []
        if self._draft:
            for pi, paper in enumerate(self._draft['papers']):
                papers.append({'index': pi, 'title': paper['title'], 'body': paper['body']})
                for qi, q in enumerate(paper['questions']):
                    questions.append(dict(paperIndex=pi, questionIndex=qi, paperTitle=paper['title'],
                        number=str(q['number']), stem=q['stem'], options=q['options'], answer=q.get('answer', ''),
                        answerSource={'key': '原书答案', 'imported': '原书答案', 'manual': '手动答案', 'ai': 'AI 参考答案'}.get(q.get('answer_source'), '缺少答案'),
                        included=q.get('included', True)))
        selected = [q for q in questions if q['included']]
        self._view.update(papers=papers, questions=questions, questionCount=len(questions), selectedCount=len(selected),
                          missing=sum(not q['answer'] for q in selected), parsed=bool(papers))
        self.changed.emit()

    @Slot()
    def invalidate(self):
        self._cancel.set()
        self._generation += 1
        self._auto_backend = None
        self._draft = None
        self._view.update(parsed=False, busy=False, stage='', error=self._load_error, message='', warnings=[],
                          papers=[], questions=[], questionCount=0, missing=0, selectedCount=0)
        self.changed.emit()

    @Slot()
    def cancel(self):
        self._cancel.set()
        self._generation += 1
        self._auto_backend = None
        self._view.update(busy=False, stage='', message='已取消等待，已有文本和识别结果保留。已发出的模型请求可能继续运行。')
        self.changed.emit()

    def _start(self, kind, work):
        self._cancel.set()
        self._cancel = cancel = threading.Event()
        self._generation += 1
        generation = self._generation
        self._view.update(busy=True, error='', stage=kind)
        self.changed.emit()
        def progress(message):
            try:
                self._progress.emit(generation, message)
            except RuntimeError:
                cancel.set()
        def run():
            try:
                value = work(cancel, progress)
                if not cancel.is_set():
                    try:
                        self._result.emit(generation, kind, value, '')
                    except RuntimeError:
                        cancel.set()
            except ConversionCancelled:
                pass
            except Exception as exc:
                try:
                    self._result.emit(generation, kind, None, str(exc))
                except RuntimeError:
                    cancel.set()
        self._thread = threading.Thread(target=run, name='reading-import-' + kind, daemon=True)
        self._thread.start()

    @Slot()
    def close(self):
        converting = self._view['stage'] == 'convert'
        self.cancel()
        if converting and self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @Slot(int, str)
    def _show_progress(self, generation, message):
        if generation == self._generation:
            self._view['message'] = message
            self.changed.emit()

    @Slot(str, str, str, str, str, str)
    def loadFile(self, url, mode, python, pages, language, device='auto'):
        self.invalidate()
        path = Path(QUrl(url).toLocalFile())
        if not path.is_file():
            self._error('没有找到所选文件')
            return
        if language not in ('en', 'ja'):
            self._error('请先选择文档语言')
            return
        if device not in {'auto', 'cpu', 'cuda'}:
            self._error('未知转换设备')
            return
        self._preferences.update(python=python, conversion=mode, folder=str(path.parent), backend=self._preferences['backend'], device=device)
        try:
            atomic_json(self._preferences_path, self._preferences)
        except OSError as exc:
            self._error('导入设置保存失败：' + str(exc))
            return
        output = self.path.parent / 'import-work' / uuid4().hex
        converter = self.converter
        def work(cancel, progress):
            text = converter(path, output, mode, python, language, pages, cancel, progress, device=device)
            if len(text) > MAX_TEXT:
                raise ValueError('转换文本超过 50 万字符，请按单元或页码拆分')
            return {'raw': text, 'title': path.stem, 'filename': path.name,
                    'origin': {'filename': path.name, 'conversion': 'text' if path.suffix.lower() in ('.txt', '.md', '.markdown') else mode,
                               'pages': pages, 'converted_sha256': hashlib.sha256(text.encode()).hexdigest()}}
        self._start('convert', work)

    def _prepare(self, raw, title, language, filename):
        if self._load_error:
            raise ValueError(self._load_error)
        if not isinstance(raw, str) or not raw.strip() or '\x00' in raw or len(raw) > MAX_TEXT:
            raise ValueError('请输入有效的文本（最多 50 万字符）')
        language = detect_language(raw) if language == 'auto' else language
        if language not in ('en', 'ja'):
            raise ValueError('请选择英语或日语')
        atomic_json(self._draft_path, {'schema': 1, 'raw': raw, 'title': title, 'filename': filename})
        self._view.update(raw=raw, title=title, filename=filename)
        return {'raw': raw, 'title': title.strip()[:300], 'language': language, 'filename': filename, 'origin': copy.deepcopy(self._origin)}

    @Slot(str, str, str, str, result=bool)
    def parse(self, raw, title, language, filename):
        self.invalidate()
        try:
            draft = self._prepare(raw, title, language, filename)
            result = parse_reading_papers(raw, draft['language'], title)
            self._draft = {**draft, 'papers': result['papers']}
            self._view.update(warnings=result['warnings'], error='', message='已识别文章和题目。答案单独保存，交卷后显示。')
            self._refresh()
            return True
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return False

    @Slot(result=str)
    def clipboardSource(self):
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.clipboard().text()

    @Slot(str, str, str, str, str)
    def prepareAutomatically(self, raw, title, language, filename, backend):
        """Prepare keys in the background, without requiring an answer reveal."""
        if backend not in {'local', 'cloud'}:
            self._error('请选择本地或云端模型')
            return
        if self.parse(raw, title, language, filename):
            if self._view['missing']:
                self.fillAnswers(backend)
            else:
                self._view['message'] = '题目和原书答案已准备，答案将在交卷后显示。'
                self.changed.emit()
        else:
            self.organize(raw, title, language, filename, backend)
            if self._view['busy']:
                self._auto_backend = backend

    @Slot(str, str, str, str, str)
    def organize(self, raw, title, language, filename, backend):
        self.invalidate()
        try:
            draft = self._prepare(raw, title, language, filename)
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return
        requester = self.requester
        self._preferences['backend'] = backend
        try:
            atomic_json(self._preferences_path, self._preferences)
        except OSError as exc:
            self._error('模型选择保存失败：' + str(exc))
            return
        def work(cancel, progress):
            papers, warnings = [], []
            consecutive_errors = 0
            chunks = source_chunks(raw)
            for index, chunk in enumerate(chunks):
                if cancel.is_set():
                    raise ConversionCancelled()
                if len(chunk) > 6500:
                    warnings.append(f'第 {index+1} 部分超过模型单次整理范围，请按文章拆分或先使用规则识别。该部分未发送。')
                    continue
                progress(f'模型正在整理第 {index+1}/{len(chunks)} 部分…')
                try:
                    prompt_source = formatting_source(chunk)
                    payload = requester(extraction_prompt(prompt_source, draft['language']), 'analysis', 3600, backend=backend)
                    result = validate_extraction(payload, chunk, draft['language'], title or '阅读材料')
                    consecutive_errors = 0
                    papers.extend(result['papers'])
                    warnings.extend(result['warnings'])
                    if not result['papers']:
                        warnings.append(f'第 {index+1} 部分没有通过来源校验的完整阅读题。')
                except Exception as exc:
                    # A formatter failure must not drop an otherwise complete
                    # source paper. Keep deterministic extraction when possible.
                    try:
                        fallback = parse_reading_papers(chunk, draft['language'])
                    except ValueError:
                        fallback = None
                    if fallback:
                        papers.extend(fallback['papers'])
                        warnings.extend(fallback['warnings'])
                        warnings.append(f'第 {index+1} 部分模型未完成，已保留规则识别结果：{exc}')
                        consecutive_errors += 1
                        if consecutive_errors >= 2:
                            warnings.append('模型连续失败，后续部分只保留可用的规则识别结果，不再发出模型请求。')
                            for remaining in chunks[index+1:]:
                                try:
                                    preserved = parse_reading_papers(remaining, draft['language'])
                                    papers.extend(preserved['papers'])
                                    warnings.extend(preserved['warnings'])
                                except ValueError:
                                    warnings.append('一个后续部分无法按规则识别，已保留原文供稍后处理。')
                            break
                        continue
                    warnings.append(f'第 {index+1} 部分未完成：{exc}')
                    consecutive_errors += 1
                    if consecutive_errors >= 2:
                        warnings.append('模型连续两次失败，已停止后续请求；已整理的部分仍可预览。')
                        break
            if not papers:
                raise ValueError('未得到可导入的阅读题。' + '；'.join(warnings[:4]))
            seen, unique = set(), []
            for paper in papers:
                key = content_id(paper['body'], paper['questions'])
                if key not in seen:
                    seen.add(key)
                    unique.append(paper)
            # Question batches carry the same full passage; merge them back into
            # one practice paper without dropping numbers or overwriting keys.
            merged = {}
            for paper in unique:
                body_key = content_id(paper['body'], [])
                if body_key not in merged:
                    merged[body_key] = paper
                    continue
                existing = merged[body_key]['questions']
                by_number = {str(q['number']): q for q in existing}
                for question in paper['questions']:
                    old = by_number.get(str(question['number']))
                    if old is None:
                        existing.append(question)
                        by_number[str(question['number'])] = question
                    elif (old['stem'], old['options']) != (question['stem'], question['options']):
                        old['included'] = False
                        warnings.append(f'重复题号 {question["number"]} 的内容不同，已排除，请拆分后重新导入。')
                    elif old.get('answer') and question.get('answer') and old['answer'] != question['answer']:
                        old.update(answer='', answer_source='')
                        warnings.append(f'第 {question["number"]} 题出现冲突答案，留待核对。')
                    elif not old.get('answer') and question.get('answer'):
                        old.update(answer=question['answer'], answer_source=question.get('answer_source', 'key'))
            # A document-wide answer table can be outside an individual model
            # chunk. Restore only keys bound to the exact source passage and
            # question; never ask the model to guess an available source key.
            try:
                originals = parse_reading_papers(raw, draft['language'])['papers']
            except ValueError:
                originals = []
            def identity(paper, question):
                return (canonical(paper['body']), str(question['number']), canonical(question['stem']),
                        tuple(canonical(option) for option in question['options']))
            keys = {identity(p, q): q for p in originals for q in p['questions'] if q.get('answer')}
            for paper in merged.values():
                for question in paper['questions']:
                    original = keys.get(identity(paper, question))
                    if original:
                        question.update(answer=original['answer'], answer_source='key')
                        if original.get('explanation'):
                            question['explanation'] = original['explanation']
            return {'draft': {**draft, 'papers': list(merged.values())}, 'warnings': warnings}
        self._start('organize', work)

    @Slot(str)
    def fillAnswers(self, backend):
        if not self._draft or self._view['busy']:
            return
        if backend not in {'local', 'cloud'}:
            self._error('请选择本地或云端模型')
            return
        self._preferences['backend'] = backend
        try:
            atomic_json(self._preferences_path, self._preferences)
        except OSError as exc:
            self._error('模型选择保存失败：' + str(exc))
            return
        snapshot = copy.deepcopy(self._draft['papers'])
        requester = self.requester
        def work(cancel, progress):
            for index, paper in enumerate(snapshot):
                pending = [q for q in paper['questions'] if q.get('included', True) and not q.get('answer')]
                for start in range(0, len(pending), 6):
                    if cancel.is_set():
                        raise ConversionCancelled()
                    progress(f'AI 正在准备第 {index+1} 篇的缺失答案，交卷后显示…')
                    batch = pending[start:start+6]
                    payload = requester(ai_answer_prompt(paper['body'], batch, paper['language']), 'analysis', 2000, backend=backend)
                    apply_ai_answers(payload, batch, paper['body'])
            return snapshot
        self._start('answers', work)

    @Slot(int, str, object, str)
    def _finish(self, generation, kind, value, error):
        if generation != self._generation:
            return
        self._view.update(busy=False, stage='')
        if error:
            self._error(error)
            return
        if kind == 'convert':
            self._origin = value['origin']
            self._view.update(raw=value['raw'], title=value['title'], filename=value['filename'], error='', message='文档已转为文本，请识别题目或交给模型整理。')
            self.sourceReady.emit(value['raw'], value['title'], value['filename'])
        elif kind == 'organize':
            self._draft = value['draft']
            self._view.update(warnings=value['warnings'], error='', message='文章和题目已整理，先确认排版即可。答案将在交卷后显示。')
            self._refresh()
            backend = self._auto_backend
            self._auto_backend = None
            if backend and self._view['missing']:
                self.fillAnswers(backend)
        elif kind == 'answers' and self._draft:
            for current, finished in zip(self._draft['papers'], value):
                by_number = {str(q['number']): q for q in finished['questions']}
                for q in current['questions']:
                    result = by_number.get(str(q['number']), {})
                    if not q.get('answer') and result.get('answer_source') == 'ai':
                        for field in ('answer', 'answer_source', 'explanation', 'evidence'):
                            if field in result:
                                q[field] = copy.deepcopy(result[field])
            self._view.update(message='题目已准备；AI 参考答案将在交卷后显示。仍缺答案的题可排除。', error='')
            self._refresh()
        self.changed.emit()

    @Slot(int, int, str)
    def setAnswer(self, paper_index, question_index, letter):
        try:
            if paper_index < 0 or question_index < 0:
                return
            q = self._draft['papers'][paper_index]['questions'][question_index]
            if letter not in LETTERS[:len(q['options'])] or len(letter) != 1:
                return
            q.update(answer=letter, answer_source='manual')
            q.pop('evidence', None)
            q['explanation'] = ''
            self._refresh()
        except (IndexError, KeyError, TypeError):
            return

    @Slot(int, int, bool)
    def includeQuestion(self, paper_index, question_index, included):
        try:
            if paper_index < 0 or question_index < 0:
                return
            self._draft['papers'][paper_index]['questions'][question_index]['included'] = included
            self._refresh()
        except (IndexError, TypeError, KeyError):
            return

    @Slot()
    def skipUnanswered(self):
        if self._draft:
            for p in self._draft['papers']:
                for q in p['questions']:
                    if not q.get('answer'):
                        q['included'] = False
            self._refresh()

    @Slot(str, result=bool)
    def remove(self, paper_id):
        if self._load_error:
            self._error(self._load_error)
            return False
        paper = next((p for p in self._rows if p['id'] == paper_id), None)
        if not paper:
            return False
        try:
            # Archive the source paper; immutable attempts retain their own
            # snapshots. Reimporting the same content can recover its history.
            atomic_json(self.path.parent / 'retired-papers' / (paper_id + '.json'), paper)
            rows = [p for p in self._rows if p['id'] != paper_id]
            atomic_json(self.path, {'schema': 1, 'papers': rows})
        except OSError as exc:
            self._error('移除失败，原题库已保留：' + str(exc))
            return False
        self._rows = rows
        self.papersChanged.emit()
        self._view.update(error='', message='已从材料库移除，原文件、题目快照和作答记录保留。')
        self.changed.emit()
        return True

    @Slot(bool, result=str)
    def save(self, confirmed):
        if self._view['busy']:
            return ''
        if not confirmed or not self._draft or self._view['busy'] or self._load_error:
            self._error(self._load_error or '请先完成整理并确认题目排版')
            return ''
        try:
            from reading import validate_paper
            draft = self._draft
            raw_hash = hashlib.sha256(draft['raw'].encode()).hexdigest()
            new, duplicates = [], []
            known = {p['id'] for p in self._rows}
            for index, paper in enumerate(draft['papers']):
                selected = [q for q in paper['questions'] if q.get('included', True)]
                if not selected:
                    continue
                if any(not q.get('answer') for q in selected):
                    raise ValueError('所选题目仍缺答案，请手动补充或排除后再导入')
                identity = content_id(paper['body'], selected)
                paper_id = 'personal-paper-' + identity[:24]
                if paper_id in known:
                    duplicates.append(paper_id)
                    continue
                questions = []
                for q in selected:
                    item = {k: copy.deepcopy(q[k]) for k in ('stem', 'options', 'answer', 'explanation', 'answer_source', 'evidence') if k in q}
                    item.update(id=paper_id + '-q' + hashlib.sha256(str(q['number']).encode()).hexdigest()[:12],
                                number=str(q['number']), type='single', explanation=item.get('explanation') or '原书未提供解析；答案来源：' + ('AI 参考，需结合原文核对' if q.get('answer_source') == 'ai' else '手动核对' if q.get('answer_source') == 'manual' else '导入文本'))
                    questions.append(item)
                row = dict(schema_version=1, id=paper_id, title=paper['title'], language=paper['language'],
                           group='我的阅读题', setId='personal-exam-' + raw_hash[:16], setTitle=draft['title'] or draft['filename'] or '个人试卷',
                           number=index+1, order=int(time.time()*1000)+index, body=paper['body'], questions=questions,
                           source=dict(kind='personal_practice', label='个人导入 · 阅读练习', review_status='user_confirmed',
                                       filename=draft['filename'], raw_sha256=raw_hash, origin=draft['origin']))
                new.append(validate_paper(row))
                known.add(paper_id)
            if not new and not duplicates:
                raise ValueError('至少选择一道有答案的题目')
            if new:
                atomic_json(self.path.parent / 'import-sources' / (raw_hash + '.json'),
                            {'schema': 1, 'raw': draft['raw'], 'filename': draft['filename'], 'origin': draft['origin']})
                atomic_json(self.path, {'schema': 1, 'papers': [*self._rows, *new]})
                self._rows.extend(new)
                self.papersChanged.emit()
            self._view.update(error='', message=f'已导入 {len(new)} 篇；重复 {len(duplicates)} 篇保留原进度。')
            self.changed.emit()
            return (new[0]['id'] if new else duplicates[0])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._error('导入未完成，预览内容已保留：' + str(exc))
            return ''
