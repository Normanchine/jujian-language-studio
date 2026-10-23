"""Data location is independent from assets; previews opt in before imports."""
import os
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('JUJIAN_DATA_DIR', str(ROOT / 'data'))).expanduser().resolve()
ASSETS = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else ROOT
