"""Frozen-release integration checks for reading marks and attached model essays."""
def check_updates(engine, window, writer, reading, captures):
    import json
    from pathlib import Path
    import shiboken6
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQml import QQmlExpression, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    quick=shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0],QQuickWindow)
    view=window.findChild(QObject,'writingView')
    home=window.findChild(QObject,'readingHome')
    def js(code,obj):
        expression=QQmlExpression(QQmlEngine.contextForObject(obj),obj,code)
        value=expression.evaluate()
        assert not expression.hasError(),expression.error().toString()
        value=value[0] if isinstance(value,tuple) else value
        return value.toVariant() if hasattr(value,'toVariant') else value
    def find(name):
        pending=[quick.contentItem()]
        while pending:
            item=pending.pop()
            if item.objectName()==name and item.isVisible():return item
            pending.extend(item.childItems())
        raise AssertionError(name)
    def click(name):
        item=find(name)
        point=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
        assert 0<=point.x()<quick.width() and 0<=point.y()<quick.height(),(name,point)
        QTest.mouseClick(quick,Qt.LeftButton,Qt.NoModifier,point)
        QTest.qWait(80)
    window.setWidth(1320);window.setHeight(900);window.setProperty('page','writing')
    writer.newDraft('en')
    source='Last weekend, I go to the library.\n\nThe quiet room help me focus.'
    model='Last weekend, I went to the library.\n\nThe quiet room helped me focus.'
    writer.saveDraft('Release verification essay','A quiet place',source)
    path=writer.currentPath
    writer._job_file=Path(path)
    writer._ready('review',dict(language='en',text=source,revisedText=model,overall='Verification fixture.',issues=[],created='2026-10-27T12:00:00'))
    js('loadedPath="";openDraft('+json.dumps(path)+');openComparison()',view)
    QTest.qWait(130)
    assert js('comparisonMode && hasModelEssay',view)
    assert not find('writingComparison').property('stacked')
    assert quick.grabWindow().save(str(captures/'writing-comparison-wide.png'))
    window.setWidth(900);window.setHeight(700);QTest.qWait(130)
    assert find('writingComparison').property('stacked')
    assert quick.grabWindow().save(str(captures/'writing-comparison-narrow.png'))
    click('writingComparisonBack');click('writingOpenComparison')
    stored=json.loads(Path(path).read_text(encoding='utf-8'))
    assert stored['text']==source and stored['review']['revisedText']==model
    click('writingComparisonBack');js('showLibrary()',view)

    body='駅の近くに図書館があります。静かな部屋で本を読みます。'*5
    article=dict(id='release-reading-check',language='ja',group='Release check',setId='release-check',setTitle='Verification',
                 title='図書館',body='\n\n'.join([body]*8),number=1,order=0,hasQuestions=False)
    window.setProperty('readingPreviewItems',[article]);window.setProperty('page','reading')
    js("changeLanguage('ja');openDestination('library');choose('all')",home);QTest.qWait(130)
    click('readingArticleComplete_release-reading-check')
    assert js('readingRecords["release-reading-check"].readComplete',home)
    click('readingRead_done');assert len(js('results',home))==1
    click('readingIntensive_release-reading-check');QTest.qWait(130)
    reader=find('readingArticlePage');passage=find('readingPassage')
    js('positionViewAtIndex(2,1);forceLayout()',passage);QTest.qWait(80)
    js('contentY=itemAtIndex(2).y-60',passage);QTest.qWait(80)
    before=js('itemAtIndex(2).y-contentY',passage)
    reading.intensive.requester=lambda *args: {'translation':'用于发行检查的演示译文。'*3}
    click('readingParagraphTranslation_2')
    for _ in range(100):
        QTest.qWait(10)
        if reading.intensive.view['translations'][2]['text']:break
    assert reading.intensive.view['translations'][2]['text']
    assert abs(js('itemAtIndex(2).y-contentY',passage)-before)<2
    js('positionViewAtIndex(4,1);forceLayout()',passage);QTest.qWait(80)
    js('contentY=itemAtIndex(4).y+40',passage);js('savePosition()',reader)
    anchor=js('record.readingAnchor',reader)
    assert anchor['paragraph']==4
    click('readingBack')
    js("openArticle(selectedArticle,'intensive')",home);QTest.qWait(130)
    assert abs(js('contentY-itemAtIndex(4).y',find('readingPassage'))-40)<3
    assert quick.grabWindow().save(str(captures/'reading-manual-completion.png'))
    click('readingBack')
    assert reading.homeState['records']['release-reading-check']['readComplete'] is True
    (captures/'study-updates.json').write_text(json.dumps(dict(passed=True,writing_comparison=True,
        writing_stored_snapshot=True,reading_manual_complete=True,translation_scroll=True,paragraph_restore=True),indent=2),encoding='utf-8')
