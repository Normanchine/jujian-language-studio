"""Run the real QML with persistent, isolated preview storage and opt-in demo tasks."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
os.environ["JUJIAN_WRITING_DEMO"] = "1"


def create_preview(storage=None, animations=False, reading_bank=True, writing_bank=False):
    root = Path(__file__).resolve().parent
    storage = (Path(storage) if storage else root / 'test-download/writing-task-preview/data').resolve()
    # Select paths before business imports; retain legacy overrides below for
    # integration harnesses which imported those modules before this function.
    os.environ['JUJIAN_DATA_DIR'] = str(storage)
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine
    import model_settings
    import study
    import writing
    from download_service import DownloadBridge
    from reading import ReadingBridge

    from core.session import open_data_session
    app = QApplication.instance() or QApplication(sys.argv)
    session_lock = open_data_session(storage)
    app._preview_data_lock = session_lock
    storage.mkdir(parents=True, exist_ok=True)
    model_settings.CONFIG = storage / "settings.json"
    study.DATA = storage
    study.PROJECTS = storage / "projects"
    study.LAST = storage / "last-project.txt"
    study.REMOVED_PROJECTS = storage / "removed-projects"
    writing.ESSAYS = storage / "essays"
    writing.NOTES = storage / "notes"
    writing.FAVORITES = storage / "writing-favorites.json"
    writing.MATERIAL_LIBRARY = storage / "writing-materials.json"
    writing.WRITING_LAYOUT = storage / "writing-layout.json"
    writing.DATA = storage
    app = QApplication.instance() or QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(root / "assets" / "jujian.png")))
    engine = QQmlApplicationEngine()
    bridges = {"study": study.StudyBridge(), "writer": writing.WritingBridge(catalogue_path=root / 'data/toefl-writing.json' if writing_bank else None),
               "settings": model_settings.SettingsBridge(), "downloads": DownloadBridge(),
               "reading": ReadingBridge(storage / "reading", bank_path=root / "data/reading/materials/toefl-reviewed.json" if reading_bank else None)}
    for name, bridge in bridges.items():
        engine.rootContext().setContextProperty(name, bridge)
    engine.rootContext().setContextProperty("uiAnimationsEnabled", animations)
    engine.load(QUrl.fromLocalFile(str(root / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("Writing preview QML failed to load")
    window = engine.rootObjects()[0]
    window.setProperty("page", "writing")
    window.setProperty("title", "句间 · 写作开发版（已核材料）" if writing_bank else "句间 · 写作专项源码预览（独立演示数据）")
    app.aboutToQuit.connect(bridges["writer"].pauseTask)
    app.aboutToQuit.connect(bridges["study"].close)
    app.aboutToQuit.connect(bridges["reading"].leave)
    app.aboutToQuit.connect(bridges['reading'].paperImporter.close)
    bridges['settings'].dataSafety.essaysRestored.connect(bridges['writer'].refresh)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(1500, bridges['settings'].dataSafety.automaticBackup)
    return app, engine, bridges, window


def seed_home_demo(writer):
    """One-time clearly labelled examples, only in the optional home showcase."""
    if writer.drafts:
        return
    samples = [
        ("ja", "週末の図書館", "静かな場所で本を読むと、気持ちが落ち着きます。\n今日は図書館で日本語の小説を読みました。"),
        ("en", "A place to concentrate", "A quiet study space gives students a chance to focus without distractions.\nFor example, a small reading room can make a busy campus feel more welcoming."),
        ("en", "An email about a museum visit", "Dear Ms. Taylor,\nOur club is planning a visit to your museum. Could you tell us which dates are available?"),
        ("ja", "小さな習慣", "毎朝少しずつ書くことで、自分の考えを整理できるようになりました。"),
        ("en", "Learning through volunteering", "Volunteering helps students develop a sense of responsibility and understand their community."),
        ("ja", "雨の日の帰り道", "雨が降っていたので、駅の近くの喫茶店で少し休みました。"),
        ("en", "Working with others", "Working with others allows us to learn from different perspectives and explain our ideas more clearly."),
    ]
    paths = []
    for language, title, text in samples:
        writer.newDraft(language)
        writer.saveDraft("示例 · " + title, "自编页面展示素材，非用户作文或真题。", text)
        paths.append(writer.currentPath)
    for path in paths[:2]:
        writer.toggleDraftFavorite(path)
    for text, quote, path, language in [
        ("用 without distractions 表达不受干扰，比一味使用 very quiet 更具体。", "a chance to focus without distractions", paths[1], "en"),
        ("「〜ことで」说明方法和结果，可以迁移到学习习惯的描述中。", "毎朝少しずつ書くことで、自分の考えを整理できるようになりました。", paths[3], "ja"),
        ("邮件里先交代目的，再提出具体问题，读起来更清楚。", "Could you tell us which dates are available?", paths[2], "en"),
    ]:
        writer.saveWritingNote("", text, quote, path, language)


if __name__ == "__main__":
    showcase = "--home-showcase" in sys.argv
    storage = Path(__file__).resolve().parent / "test-download/writing-home-preview/data" if showcase else None
    app, engine, bridges, window = create_preview(storage, writing_bank=not showcase)
    if showcase:
        seed_home_demo(bridges["writer"])
        window.setProperty("title", "句间 · 写作主页预览（独立示例数据）")
    raise SystemExit(app.exec())
