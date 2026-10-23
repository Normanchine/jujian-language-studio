"""Local word/sentence snapshots, independent of the removable lookup notes."""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot


class ReadingSavedBridge(QObject):
    changed=Signal()

    def __init__(self,path,parent=None):
        super().__init__(parent)
        self.path=Path(path);self._items={};self._document=None;self._status='';self._load_error=False
        try:
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw,dict) or not isinstance(raw.get('items'),list):raise ValueError('invalid favorites')
            for item in raw['items']:
                if self._valid(item):self._items[item['id']]=item
        except FileNotFoundError:pass
        except (OSError,ValueError):
            self._load_error=True;self._status='收藏文件读取失败，原文件已保留'

    @staticmethod
    def _valid(item):
        return (isinstance(item,dict) and item.get('kind') in {'word','sentence'} and item.get('language') in {'en','ja'}
                and all(isinstance(item.get(k),str) for k in ('id','document_key','article_id','article_title','text','sentence','meaning','usage','source_label'))
                and all(type(item.get(k)) is int and item[k]>=0 for k in ('paragraph','start','end','mark_start','mark_end','created_at'))
                and item['start']<item['end'] and item['mark_start']<item['mark_end']
                and item['sentence'].encode('utf-16-le')[item['mark_start']*2:item['mark_end']*2]==item['text'].encode('utf-16-le'))

    def open(self,document):
        self._document=copy.deepcopy(document)
        if not self._load_error:self._status=''
        self.changed.emit()

    @Property('QVariantMap',notify=changed)
    def view(self):
        current={}
        if self._document:
            current={f"{a['kind']}:{a['paragraph']}:{a['start']}:{a['end']}":a['id'] for a in self._items.values()
                     if a['document_key']==self._document['key'] and a['article_id']==self._document['id']}
        return {'items':copy.deepcopy(sorted(self._items.values(),key=lambda a:a['created_at'],reverse=True)),
                'currentIds':current,'status':self._status}

    def _save(self):
        if self._load_error:raise OSError('收藏文件无法读取，请先恢复原文件')
        from core.storage import atomic_json
        atomic_json(self.path, {'version':1,'items':list(self._items.values())})

    def toggle(self,item):
        if not self._document:return False
        value=copy.deepcopy(item)
        value.update(document_key=self._document['key'],article_id=self._document['id'],article_title=self._document['title'],
                     language=self._document['language'],source_label=self._document['source'],created_at=int(time.time()*1000))
        value['id']=hashlib.sha256(json.dumps([value[k] for k in ('document_key','article_id','kind','paragraph','start','end')],ensure_ascii=False).encode()).hexdigest()[:32]
        if not self._valid(value):return False
        if value['id'] in self._items:return self.remove(value['id'])
        self._items[value['id']]=value
        try:self._save()
        except OSError:
            self._items.pop(value['id'],None);self._status='收藏保存失败，请重试';self.changed.emit();return False
        self._status='已收藏词汇' if value['kind']=='word' else '已收藏句子'
        self.changed.emit();return True

    @Slot(str,result=bool)
    def remove(self,key):
        previous=self._items.pop(key,None)
        if not previous:return False
        try:self._save()
        except OSError:
            self._items[key]=previous;self._status='取消收藏失败，请重试';self.changed.emit();return False
        self._status='已取消收藏';self.changed.emit();return True

    def source_matches(self,key,document_key):
        return bool(key in self._items and self._items[key]['document_key']==document_key)
