"""Source/frozen checks for the approved writing and native-frame update; no network."""
def check_writing_updates(engine, window, writer, captures):
    import json
    from pathlib import Path
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlExpression, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    import shiboken6
    import writing
    from review_guidance import organize_feedback, build_review_prompt
    quick=shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0],QQuickWindow)
    window.setProperty('page','writing');window.resize(1320,900);QTest.qWait(80)
    view=window.findChild(QObject,'writingView')
    def js(code):
        expression=QQmlExpression(QQmlEngine.contextForObject(view),view,code)
        expression.evaluate()
        assert not expression.hasError(),expression.error().toString()
    def item(name):
        result=window.findChild(QObject,name)
        assert result,name
        return result
    def click(name):
        target=item(name)
        assert target.isVisible() and target.isEnabled(),name
        point=target.mapToScene(QPointF(target.width()/2,target.height()/2)).toPoint()
        QTest.mouseClick(quick,Qt.LeftButton,Qt.NoModifier,point);QTest.qWait(70)
    def wait_job():
        for _ in range(150):
            QTest.qWait(10)
            if not writer.busy:break
        assert not writer.busy
        QTest.qWait(30)
    source='Last year, i moved away.\n\nVideo calls help me stay in touch with my family.'
    topic='Discuss the impact of digital communication.\n\n'+'Explain your view with relevant examples.\n'*24
    writer.newDraft('en');writer.saveDraft('Release writing verification',topic,source)
    path=writer.currentPath
    writer._draft.update(task_id='release-self-check',task_state='untimed',task_prompt=topic,task_elapsed=0)
    writer._persist_task()
    js('loadedPath="";openDraft('+json.dumps(path)+')');QTest.qWait(100)
    click('writingCopyTopic');assert QGuiApplication.clipboard().text()==topic.strip()
    card=item('writingTopicCard');sheet=item('writingSheet')
    before=card.height();sheet_width=sheet.width()
    click('writingMaterialsToggle');QTest.qWait(300)
    assert card.height()<before and sheet.width()==sheet_width
    assert item('writingSidePanel').parentItem()==item('writingContextPanel')
    assert item('writingPromptScroll').property('contentHeight')>item('writingPromptScroll').height()
    click('writingMaterialsToggle');QTest.qWait(300)
    assert abs(card.height()-before)<1
    # Check the actual packed generator, schema, and failed-generation preservation.
    cards=[dict(expression=e,kind='vocabulary',meaning='保持联系',scenario='讨论远距离沟通',usage=e+' with + 人',example='Video calls help families '+e+'.',caution='',related='')
           for e in ('maintain close ties','stay connected','keep in touch','share daily experiences')]
    old_ask=writing.ask_json
    prompts=[]
    def fixture(prompt,task,token_limit):
        prompts.append(prompt);return {'items':cards}
    writing.ask_json=fixture
    try:
        writer.generateMaterials('常用、准确');wait_job()
        assert len(writer.materials)==4 and json.dumps(source,ensure_ascii=False) in prompts[0]
        assert writer.materials[0]['scenario']=='讨论远距离沟通'
        writer.generateMaterials('常用、准确');wait_job()
        assert len(writer.materials)==4 and '失败' in writer.status
    finally:writing.ask_json=old_ask
    # Submit uses the real thread and state machine, with a deterministic local model reply.
    old_review=writing.review_english
    def review(draft):
        return organize_feedback(draft['text'],{'overall':'演示核验：修正第一人称大小写。','issues':[
            {'quote':'i','correction':'I','reason':'第一人称代词大写。','kind':'error','category':'拼写'}],
            'revised_text':draft['text'].replace(' i ',' I ')})
    writing.review_english=review
    try:click('writingReviewSubmit');wait_job()
    finally:writing.review_english=old_review
    assert writer.current['task_state']=='finished' and writer.current['submission']['text']==source
    assert writer.reviewIssues[0]['linked'] and writer.reviewIssues[0]['correction']=='I'
    click('writingOpenComparison');click('writingComparisonEditModel')
    replacement='My own reference essay for comparison.'
    item('writingCustomModelInput').setProperty('text',replacement)
    click('writingCustomModelSave')
    assert replacement in item('writingComparisonModelText').property('text')
    click('writingComparisonSwitchModel')
    assert 'Video calls' in item('writingComparisonModelText').property('text')
    stored=json.loads(Path(path).read_text(encoding='utf-8'))
    assert stored['custom_model']==replacement and stored['text']==source and stored['submission']['text']==source
    assert '不强求' in build_review_prompt(dict(writing_mode='toefl_discussion'))
    assert quick.grabWindow().save(str(captures/'writing-v0211-comparison.png'))
    # Same-HWND native-style reset must recover on its own.
    actions=engine.rootContext().contextProperty('windowActions')
    frame=actions.frame;handle=frame.hwnd
    frame.set_style(handle,-16,frame.get_style(handle,-16)&~0x00C40000)
    frame.user.SetWindowPos(handle,None,0,0,0,0,0x0037)
    QTest.qWait(300)
    assert frame.hwnd==handle and frame.get_style(handle,-16)&0x00CF0000==0x00CF0000
    assert not actions._effects_timer.isActive(), 'frame recovery must settle without an event loop'
    (captures/'writing-updates.json').write_text(json.dumps({
        'passed':True,'asymmetric_layout':True,'topic_resize_and_copy':True,'scoped_material_generation':True,
        'failed_generation_preserves_cards':True,'untimed_submission_snapshot':True,'case_correction_anchor':True,
        'editable_reference_preserves_ai':True,'same_handle_native_frame_recovery':True,
        'network_requests':0},indent=2),encoding='utf-8')
