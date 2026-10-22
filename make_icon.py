"""Render the 句间 icon for the app and Windows executable."""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


root = Path(__file__).resolve().parent
target = root / "assets"
app = QGuiApplication([])
renderer = QSvgRenderer(QByteArray((target / "jujian.svg").read_bytes()))
if not renderer.isValid():
    raise RuntimeError("Invalid 句间 SVG icon")

image = QImage(512, 512, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
painter.setRenderHint(QPainter.Antialiasing)
renderer.render(painter)
painter.end()

png = target / "jujian.png"
ico = target / "jujian.ico"
if not image.save(str(png)):
    raise RuntimeError(f"Could not save {png}")
with Image.open(png) as source:
    source.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(png)
print(ico)
