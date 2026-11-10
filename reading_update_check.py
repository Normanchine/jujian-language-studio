"""Isolated source/frozen checks for reading navigation and article-card actions."""
import json
import threading
import time

from PySide6.QtCore import QObject, QPointF, Qt, QTimer
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
import shiboken6
import model_settings


def check_reading_updates(engine, window, reading, settings, captures):
    quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    window.setProperty('page', 'reading')
    home = window.findChild(QObject, 'readingHome')

    def js(code, obj=home):
        expression = QQmlExpression(QQmlEngine.contextForObject(obj), obj, code)
        value = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        value = value[0] if isinstance(value, tuple) else value
        return value.toVariant() if hasattr(value, 'toVariant') else value

    def find(name):
        pending = [quick.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name and item.isVisible():
                return item
            pending.extend(item.childItems())
        raise AssertionError(name)

    def click(name):
        item = find(name)
        QTest.mouseClick(quick, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint())
        QTest.qWait(35)

    def until(predicate):
        for _ in range(100):
            if predicate():
                return
            QTest.qWait(20)
        raise AssertionError('Reading update check timed out')

    key_gate, analysis_gate = threading.Event(), threading.Event()
    key_started, analysis_started = threading.Event(), threading.Event()
    original_key, original_request = model_settings.cloud_key, reading.intensive.requester
    report = {'network_requests': 0}
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))

    def slow_key(*args):
        key_started.set()
        assert key_gate.wait(6), 'Credential fixture timed out'
        return 'fixture-only'

    def slow_analysis(*args):
        analysis_started.set()
        assert analysis_gate.wait(6), 'Analysis fixture timed out'
        return {'annotations': []}

    try:
        until(lambda: not settings.keyStatusLoading)
        model_settings.cloud_key = slow_key
        reading.intensive.requester = slow_analysis
        sample = dict(id='release-reading-ui', language='ja', number=1, order=0,
            title='雨の日の帰り道', body='駅を出ると、雨が降り始めました。\n\n温かいお茶を飲みながら、本を読みました。',
            group='自编发布检查', setId='release-reading-ui', setTitle='演示文章',
            sourceKind='personal_import', hasQuestions=False, mock=False)
        js("articleOpen=false;materials="+json.dumps([sample], ensure_ascii=False)+";changeLanguage('ja');openDestination('library');choose('release-reading-ui');chooseReadScope('all');openArticle(languageItems[0],'intensive')")
        QTest.qWait(120)
        click('readingAnalyze')
        until(analysis_started.is_set)
        timer.start()
        started = time.perf_counter()
        click('settingsNavigation')
        report['settings_during_analysis_seconds'] = round(time.perf_counter()-started, 3)
        until(key_started.is_set)
        QTest.qWait(140)
        assert report['settings_during_analysis_seconds'] < .5 and len(ticks) >= 3, report
        assert settings.keyStatusLoading and not analysis_gate.is_set()
        revision = settings._key_status_revision
        settings._set_key_status(False)
        settings._finish_key_status(revision, True)
        key_gate.set()
        QTest.qWait(80)
        assert not settings.hasKey, 'Stale vault result replaced newer state'
        analysis_gate.set()
        click('readingNavigation')
        js("articleOpen=false;choose('release-reading-ui')")
        click('readingArticleComplete_release-reading-ui')
        assert find('readingTitle_release-reading-ui').opacity() < .6
        assert not js('articleOpen')
        for width, height in ((1280, 880), (900, 640)):
            window.resize(width, height)
            QTest.qWait(100)
            card = find('readingCard_release-reading-ui')
            for prefix in ('readingMore_', 'readingIntensive_', 'readingArticleComplete_'):
                item = find(prefix+'release-reading-ui')
                bottom = item.mapToItem(card, QPointF(item.width(), item.height()))
                assert bottom.x() <= card.width()+1 and bottom.y() <= card.height()+1
                QTest.mouseMove(quick, item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
                QTest.qWait(25)
                assert card.property('hovered')
            quick.grabWindow().save(str(captures/f'reading-cards-{width}.png'))
        click('readingMore_release-reading-ui')
        QTest.qWait(120)
        more = find('readingMore_release-reading-ui')
        assert js('articleMenu.visible', more)
        assert js('articleMenu.popupType === Popup.Item', more), 'Article menu must use the themed QML popup'
        quick.grabWindow().save(str(captures/'reading-article-menu.png'))
        click('readingManage_release-reading-ui')
        assert window.findChild(QObject, 'readingManageArticlePopup').property('visible')
        QTest.keyClick(quick, Qt.Key_Escape)
        report.update(card_actions=True, completion_style=True, themed_menu=True, stale_key_ignored=True, passed=True)
        (captures/'reading-updates.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        timer.stop()
        key_gate.set(); analysis_gate.set()
        reading.intensive.cancel()
        QTest.qWait(70)
        model_settings.cloud_key = original_key
        reading.intensive.requester = original_request
