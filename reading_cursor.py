"""Theme-colored native cursors used only while hovering the intensive reader."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap


def reading_cursor(accent,query=False,ratio=1.0):
    """One quiet pointer, plus an explicit Japanese selection-query variant."""
    ratio=max(1.0,ratio)
    image=QPixmap(round(36*ratio),round(36*ratio))
    image.setDevicePixelRatio(ratio);image.fill(Qt.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing)
    color=QColor(accent)
    if not color.isValid():color=QColor('#4E8068')
    arrow=QPainterPath();arrow.moveTo(3,3);arrow.lineTo(4.5,24)
    arrow.lineTo(10,19);arrow.lineTo(14.2,28);arrow.lineTo(18,26.2)
    arrow.lineTo(13.8,17.2);arrow.lineTo(21,16);arrow.closeSubpath()
    painter.setPen(QPen(QColor('#FFFFFF'),3.5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    painter.setBrush(color if query else QColor('#FAFCFA'));painter.drawPath(arrow)
    painter.setPen(QPen(color.darker(115),1.35,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));painter.drawPath(arrow)
    if query:
        # A small selection frame remains legible when Alt is pressed without movement.
        painter.setPen(QPen(QColor('#FFFFFF'),4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        frame=QPainterPath();frame.moveTo(23,10);frame.lineTo(23,6);frame.lineTo(28,6)
        frame.moveTo(28,20);frame.lineTo(32,20);frame.lineTo(32,15)
        painter.drawPath(frame)
        painter.setPen(QPen(color,1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));painter.drawPath(frame)
        painter.drawLine(QPointF(27,10),QPointF(27,16))
    painter.end()
    return QCursor(image,3,3)


class ReadingCursor:
    def __init__(self):
        self.accent='#4E8068';self.query_enabled=True;self._owned=False
        self._key=None;self._cache={}
        app=QGuiApplication.instance()
        if isinstance(app,QGuiApplication):app.aboutToQuit.connect(self.release)

    def show(self,query,ratio):
        key=(self.accent,bool(query and self.query_enabled),round(ratio,3))
        if self._owned and self._key==key:return
        if key not in self._cache:
            if len(self._cache)>24:self._cache.clear()
            self._cache[key]=reading_cursor(*key)
        cursor=self._cache[key]
        if self._owned:QGuiApplication.changeOverrideCursor(cursor)
        elif QGuiApplication.overrideCursor() is None:
            QGuiApplication.setOverrideCursor(cursor);self._owned=True
        else:return
        self._key=key

    def release(self):
        if self._owned:
            QGuiApplication.restoreOverrideCursor();self._owned=False;self._key=None
