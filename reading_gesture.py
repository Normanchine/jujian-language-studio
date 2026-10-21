"""Observe reading modifiers without intercepting native mouse selection."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Property, Qt, Signal, Slot
from PySide6.QtGui import QCursor, QKeySequence
from PySide6.QtQuick import QQuickItem
from shiboken6 import isValid, getCppPointer, wrapInstance

MODIFIER_KEYS = {int(Qt.Key_Alt):Qt.AltModifier.value,int(Qt.Key_Control):Qt.ControlModifier.value,
                 int(Qt.Key_Shift):Qt.ShiftModifier.value,int(Qt.Key_Meta):Qt.MetaModifier.value}
MODIFIER_NAMES = {'Alt':int(Qt.Key_Alt),'Ctrl':int(Qt.Key_Control),'Shift':int(Qt.Key_Shift),'Meta':int(Qt.Key_Meta)}


def normalize_trigger(value):
    value=str(value).strip()
    if value in MODIFIER_NAMES:return value
    sequence=QKeySequence(value,QKeySequence.PortableText)
    canonical=sequence.toString(QKeySequence.PortableText)
    if sequence.count()!=1 or not canonical or canonical.endswith('+'):
        raise ValueError('请使用一个修饰键，或一组快捷键')
    key=int(sequence[0].key())
    if key in {0,int(Qt.Key_unknown),int(Qt.Key_Escape)} or canonical in {'Ctrl+C','Ctrl+A','Ctrl+V','Ctrl+X','Alt+F4','Alt+Tab'}:
        raise ValueError('这组按键用于系统操作或文字编辑，请换一个')
    return canonical


class ReadingGesture(QObject):
    changed=Signal()
    cancelled=Signal()
    pointerPressed=Signal(float,float)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._scope=None;self._window=None;self._held=False;self._pressed=set();self._trigger='Alt'
        self._key=int(Qt.Key_Alt);self._modifiers=Qt.AltModifier.value
        self._pointer_cancelled=False
        from reading_cursor import ReadingCursor
        self._reading_cursor=ReadingCursor();self._cursor_position=None;self._query_dragging=False

    @Property(bool,notify=changed)
    def held(self):return self._held

    @Slot(QObject)
    def setScope(self,scope):
        # QML may initially expose an Item as a generic QObject in a source run.
        if scope and not isinstance(scope,QQuickItem) and scope.inherits('QQuickItem'):
            scope=wrapInstance(getCppPointer(scope)[0],QQuickItem)
        self._scope=scope
        self.reset()
        self._attach_window()

    def _attach_window(self):
        self._reading_cursor.release();self._cursor_position=None
        previous=self._window
        if previous and isValid(previous):previous.removeEventFilter(self)
        scope=self._scope
        window=scope.window() if scope and isValid(scope) else None
        self._window=window
        if window:window.installEventFilter(self)

    @Slot(str,bool)
    def setCursorStyle(self,accent,query_enabled):
        self._reading_cursor.accent=accent;self._reading_cursor.query_enabled=query_enabled
        self._refresh_cursor()

    @Slot(bool)
    def setQueryDragging(self,value):
        self._query_dragging=value;self._refresh_cursor()

    def _refresh_cursor(self):
        scope=self._scope;window=self._window;point=self._cursor_position
        if (scope and isValid(scope) and scope.isVisible() and window and isValid(window)
                and window.isActive() and point is not None and scope.contains(scope.mapFromScene(point))):
            self._reading_cursor.show(self._held or self._query_dragging,window.devicePixelRatio())
        else:self._reading_cursor.release()

    @Slot(str)
    def setTrigger(self,value):
        try:value=normalize_trigger(value)
        except ValueError:value='Alt'
        if value==self._trigger:return
        self._trigger=value
        if value in MODIFIER_NAMES:
            self._key=MODIFIER_NAMES[value];self._modifiers=MODIFIER_KEYS[self._key]
        else:
            key=QKeySequence(value)[0]
            self._key=int(key.key());self._modifiers=key.keyboardModifiers().value
        self.reset()

    @Slot()
    def reset(self):
        self._query_dragging=False
        self._pointer_cancelled=True
        self._pressed.clear()
        if self._held:self._held=False;self.changed.emit()
        self.cancelled.emit()
        self._refresh_cursor()

    @Slot(QObject,int)
    def syncTextCursor(self,editor,shape):
        scope=self._scope
        if (scope and isValid(scope) and scope.isVisible() and editor and isValid(editor)
                and editor.isVisible() and editor.window()==scope.window()):
            editor.window().setCursor(QCursor(Qt.CursorShape(shape)))

    def _update(self,modifiers):
        for key in self._pressed:
            modifiers |= MODIFIER_KEYS.get(key,0)
        if self._key in MODIFIER_KEYS:
            held=bool(modifiers & self._modifiers)
        else:held=self._key in self._pressed and (modifiers & self._modifiers)==self._modifiers
        if held!=self._held:
            self._held=held;self._refresh_cursor();self.changed.emit()

    def eventFilter(self,watched,event):
        scope=self._scope
        if scope is None or not isValid(scope) or not scope.isVisible():
            self._reading_cursor.release();self._cursor_position=None
            if self._held:self.reset()
            return False
        window=scope.window()
        if watched!=window:return False
        kind=event.type()
        if kind in {QEvent.WindowDeactivate,QEvent.Hide,QEvent.Close,QEvent.Leave}:
            self._cursor_position=None;self._reading_cursor.release()
            if kind==QEvent.Leave:return False
            self.reset();return False
        if kind==QEvent.Enter:
            self._cursor_position=window.mapFromGlobal(QCursor.pos()).toPointF();self._refresh_cursor()
        if kind in {QEvent.KeyPress,QEvent.KeyRelease}:
            if event.isAutoRepeat():return False
            key=event.key();modifiers=event.modifiers().value
            if key==int(Qt.Key_Escape):self.reset();return False
            if kind==QEvent.KeyPress:self._pressed.add(key)
            else:self._pressed.discard(key)
            if key in MODIFIER_KEYS:
                if kind==QEvent.KeyPress:modifiers |= MODIFIER_KEYS[key]
                else:modifiers &= ~MODIFIER_KEYS[key]
            self._update(modifiers)
            # Consume standalone Alt in the reader, preserving combinations such as Alt+Tab.
            return key==int(Qt.Key_Alt) and self._key==int(Qt.Key_Alt)
        if kind in {QEvent.MouseButtonPress,QEvent.MouseButtonRelease,QEvent.MouseMove}:
            self._cursor_position=event.position();self._refresh_cursor()
            if kind==QEvent.MouseButtonPress:
                self._pointer_cancelled=False
                if event.button()==Qt.LeftButton:self.pointerPressed.emit(event.position().x(),event.position().y())
            if not self._pointer_cancelled:self._update(event.modifiers().value)
        return False
