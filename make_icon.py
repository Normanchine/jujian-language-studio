"""Draw the desktop app icon from Qt primitives."""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter


root = Path(__file__).resolve().parent
target = root / "assets"
target.mkdir(exist_ok=True)
app = QGuiApplication([])
image = QImage(256, 256, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
painter.setRenderHint(QPainter.Antialiasing)
painter.setBrush(QColor("#C94859"))
painter.setPen(Qt.NoPen)
painter.drawRoundedRect(QRectF(8, 8, 240, 240), 53, 53)
painter.setPen(QColor("#FFFFFF"))
font = QFont("Yu Gothic UI", 133, QFont.Bold)
painter.setFont(font)
painter.drawText(QRectF(8, 0, 240, 240), Qt.AlignCenter, "日")
painter.end()
png = target / "mainichi.png"
image.save(str(png))
Image.open(png).save(target / "mainichi.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(png)
