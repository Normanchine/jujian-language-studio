# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
from pathlib import Path
import PySide6
import imageio_ffmpeg

pyside_root = Path(PySide6.__file__).resolve().parent
model_sources = [
    Path('models/small.pt'),
    Path('dist/每日日语/_internal/models/small.pt'),
    Path('dist/句间/_internal/models/small.pt'),
]
model_source = next((path for path in model_sources if path.is_file()), None)
if model_source is None:
    raise FileNotFoundError('Download Whisper small.pt into models/ before packaging; see README.md')
ffmpeg_binaries = [(str(pyside_root / 'plugins' / 'multimedia' / 'ffmpegmediaplugin.dll'), 'PySide6/plugins/multimedia')]
ffmpeg_binaries += [(str(path), 'PySide6') for path in pyside_root.glob('*.dll') if path.name.startswith(('avcodec-', 'avformat-', 'avutil-', 'swresample-', 'swscale-'))]
ffmpeg_binaries.append((imageio_ffmpeg.get_ffmpeg_exe(), 'imageio_ffmpeg/binaries'))


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[*ffmpeg_binaries, *collect_dynamic_libs('fugashi')],
    datas=[('qml', 'qml'), ('assets/jujian.png', 'assets'), ('assets/doraemon-reading.png', 'assets'), (str(model_source), 'models'), *collect_data_files('whisper'), *collect_data_files('unidic_lite')],
    hiddenimports=['PySide6.QtMultimedia', 'PySide6.QtQuick', 'keyring.backends.Windows',
                   'fugashi', 'unidic_lite'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'matplotlib', 'scipy', 'sklearn', 'tensorflow',
              'torchvision', 'torchaudio', 'onnxruntime', 'cv2',
              'openpyxl', 'bitsandbytes', 'transformers', 'nltk', 'uvicorn',
              'fastapi', 'IPython', 'pytest', 'tkinter', '_tkinter'],
    noarchive=False,
    optimize=0,
)
# NLTK is an optional transitive dependency, unused by this app or Whisper.
# Its auto-collected runtime hook imports NLTK (and NumPy) before app.py runs,
# defeating the GUI's lazy imports. Keep optional modules available on demand.
a.scripts = [entry for entry in a.scripts if entry[0] != 'pyi_rth_nltk']
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='句间',
    icon='assets/jujian.ico',
    # Keep the executable small so Explorer can read its icon without opening
    # a 77 MB embedded Python archive. COLLECT places the archive alongside it.
    append_pkg=False,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='句间',
)
