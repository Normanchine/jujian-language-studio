"""Stable subtitle rows: model results update a row without resetting the view."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class SentenceListModel(QAbstractListModel):
    SegmentRole = int(Qt.UserRole) + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments = []

    def roleNames(self):
        return {self.SegmentRole: b"modelData"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._segments)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == self.SegmentRole and 0 <= index.row() < len(self._segments):
            return self._segments[index.row()]
        return None

    def replace(self, segments):
        self.beginResetModel()
        self._segments = segments
        self.endResetModel()

    def update_sentence(self, row, segments):
        if segments is not self._segments or len(segments) != self.rowCount():
            self.replace(segments)
        elif 0 <= row < len(self._segments):
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.SegmentRole])
