import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: practice
    objectName: "readingPracticeView"
    property var session: reading.view
    property bool review: session.stage === "review"
    property bool compact: width < 850
    property bool hasNext: false
    property int narrowTab: 1
    property int textSize: 18
    property bool wrongOnly: false
    property int highlightedParagraph: -1
    property string highlightedQuote: ""
    property string paperBody: session.body || ""
    property var paragraphs: paperBody.split(/\n\s*\n/)
    property string questionKey: (session.id || "")+":"+session.index+":"+session.stage
    property var question: ({options:[]})
    property real passagePosition: passage.contentY
    property bool restoringPassage: true
    property string attemptKey: session.id || ""
    property color ink: "#293B32"
    property color muted: "#7B8981"
    signal backRequested()
    signal intensiveRequested()
    signal nextRequested()
    onQuestionKeyChanged: { question = session.question || {options:[]}; questionScroll.contentY = 0; }
    onReviewChanged: { wrongOnly = false; highlightedParagraph = -1; highlightedQuote = ""; }
    onAttemptKeyChanged: { restoringPassage = true; if (visible) Qt.callLater(restorePosition); }
    onVisibleChanged: if (visible) { narrowTab = 1; wrongOnly = false; Qt.callLater(restorePosition); }
    function restorePosition() {
        restoringPassage = true; var saved = session.passagePosition || 0;
        passage.forceLayout();
        Qt.callLater(function() { passage.forceLayout(); passage.contentY = Math.max(0,Math.min(saved,Math.max(0,passage.contentHeight-passage.height))); practice.restoringPassage = false; });
    }
    function savePosition() { if (visible && !restoringPassage) reading.savePassagePosition(Math.max(0,passage.contentY)); }
    function clock(seconds) { return Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0"); }
    function html(text) { return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
    function paragraphHtml(text,index) {
        var safe = html(text);
        safe = highlightedParagraph === index && highlightedQuote ? safe.replace(html(highlightedQuote),'<span style="background-color:#F0E3B4">'+html(highlightedQuote)+'</span>') : safe;
        return '<p style="line-height:145%; margin:0">'+safe+'</p>';
    }
    function locate(evidence) {
        highlightedParagraph = evidence.paragraph-1; highlightedQuote = evidence.quote;
        narrowTab = 0; Qt.callLater(function() { passage.positionViewAtIndex(highlightedParagraph,ListView.Beginning); });
    }
    function moveQuestion(delta) {
        var next = session.index+delta;
        while (next >= 0 && next < session.total && review && wrongOnly && session.navigation[next].correct) next += delta;
        if (next >= 0 && next < session.total) reading.chooseQuestion(next);
    }
    Shortcut { sequence: "A"; enabled: practice.visible && !practice.review && !practice.session.paused && !submitDialog.visible; onActivated: reading.answer("A") }
    Shortcut { sequence: "B"; enabled: practice.visible && !practice.review && !practice.session.paused && !submitDialog.visible; onActivated: reading.answer("B") }
    Shortcut { sequence: "C"; enabled: practice.visible && !practice.review && !practice.session.paused && !submitDialog.visible; onActivated: reading.answer("C") }
    Shortcut { sequence: "D"; enabled: practice.visible && !practice.review && !practice.session.paused && !submitDialog.visible; onActivated: reading.answer("D") }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            AppButton { objectName: "readingPracticeBack"; text: "‹ 返回"; flat: true; onClicked: { practice.savePosition(); practice.backRequested() } }
            Text { text: practice.review ? "阅读复盘" : "阅读练习"; color: practice.ink; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Text { text: practice.review ? session.correct+" / "+session.total+" 正确" : session.answered+" / "+session.total+" 已答"; color: settings.palette.accent; font.pixelSize: 12 }
            Text { text: practice.clock(reading.elapsed); color: practice.muted; font.pixelSize: 14 }
            AppButton { objectName: "readingPracticePause"; visible: !practice.review; text: session.paused ? "继续" : "暂停"; onClicked: { practice.savePosition(); reading.togglePause() } }
            AppButton { objectName: "readingPracticeSubmit"; visible: !practice.review; text: "交卷"; primary: true; onClicked: submitDialog.open() }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: session.source || ""; color: practice.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
            AppCombo { objectName: "readingAttemptHistory"; visible: practice.review; Layout.preferredWidth: 200
                model: practice.session.history || []; textRole: "label"; valueRole: "id"
                currentIndex: (practice.session.history || []).findIndex(function(a) { return a.id === practice.session.id })
                onActivated: reading.reviewAttempt(currentValue) }
        }
        RowLayout { visible: practice.compact; Layout.fillWidth: true
            AppButton { objectName: "readingPracticePassageTab"; text: "原文"; primary: practice.narrowTab===0; onClicked: practice.narrowTab=0 }
            AppButton { objectName: "readingPracticeQuestionTab"; text: practice.review ? "题目与解析" : "题目"; primary: practice.narrowTab===1; onClicked: practice.narrowTab=1 }
            Item { Layout.fillWidth: true }
        }
        SplitView {
            id: split; Layout.fillWidth: true; Layout.fillHeight: true; orientation: Qt.Horizontal
            handle: Rectangle { implicitWidth: 10; color: "transparent"; Rectangle { anchors.centerIn: parent; width: 2; height: 30; radius: 1; color: "#D4DFD7" } }
            Rectangle {
                visible: !practice.compact || practice.narrowTab===0
                SplitView.preferredWidth: split.width*0.53; SplitView.minimumWidth: practice.compact ? 0 : 340; SplitView.fillWidth: practice.compact
                radius: 12; color: settings.palette.surface; border.color: "#DFE7E1"
                ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "原文"; color: practice.muted; font.pixelSize: 11; Layout.fillWidth: true }
                        AppButton { text: "A−"; flat: true; implicitWidth: 32; implicitHeight: 26; onClicked: practice.textSize=Math.max(14,practice.textSize-1) }
                        AppButton { text: "A＋"; flat: true; implicitWidth: 32; implicitHeight: 26; onClicked: practice.textSize=Math.min(24,practice.textSize+1) }
                    }
                    Text { text: session.title || ""; color: practice.ink; font.pixelSize: 22; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    ListView {
                        id: passage; objectName: "readingPracticePassage"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        model: practice.paragraphs; spacing: 20; boundsBehavior: Flickable.StopAtBounds
                        onMovementEnded: practice.savePosition()
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; onPressedChanged: if (!pressed) practice.savePosition() }
                        delegate: Item { required property string modelData; required property int index
                            width: passage.width-12; height: paragraph.implicitHeight
                            Text { text: parent.index+1; color: "#A1AFA6"; font.pixelSize: 10; y: 5 }
                            TextEdit { id: paragraph; objectName: "readingExerciseParagraph_"+parent.index
                                x: 24; width: parent.width-24; height: implicitHeight; readOnly: true; selectByMouse: true
                                text: practice.paragraphHtml(parent.modelData,parent.index); textFormat: TextEdit.RichText; wrapMode: TextEdit.Wrap
                                color: practice.ink; font.family: session.language === "ja" ? "Yu Gothic UI" : "Georgia"; font.pixelSize: practice.textSize }
                        }
                    }
                }
            }
            Rectangle {
                visible: !practice.compact || practice.narrowTab===1
                SplitView.fillWidth: true; SplitView.minimumWidth: practice.compact ? 0 : 310
                radius: 12; color: settings.palette.surface; border.color: "#DFE7E1"
                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "第 "+((session.index || 0)+1)+" / "+(session.total || 0)+" 题"; color: practice.ink; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        AppButton { objectName: "readingPracticeFlag"; visible: !practice.review; text: session.flagged ? "★ 待检查" : "☆ 标记"; flat: true; enabled: !session.paused; onClicked: reading.flag() }
                        AppButton { visible: practice.review; text: practice.wrongOnly ? "显示全部" : "只看错题"; flat: true; onClicked: {
                            practice.wrongOnly=!practice.wrongOnly;
                            if (practice.wrongOnly) { var at=session.navigation.findIndex(function(a){return !a.correct}); if(at>=0) reading.chooseQuestion(at); }
                        } }
                    }
                    Flow { Layout.fillWidth: true; spacing: 6
                        Repeater { model: practice.session.navigation || []
                            Button { id: nav; required property var modelData; required property int index
                                objectName: "readingQuestion_"+index; width: 30; height: 29; hoverEnabled: true
                                visible: !practice.review || !practice.wrongOnly || !modelData.correct
                                enabled: practice.review || !practice.session.paused
                                background: Rectangle { radius: 6; color: nav.index===practice.session.index ? settings.palette.accent : practice.review ? (nav.modelData.correct ? "#E4EFE7" : "#F5E5E2") : nav.modelData.answered ? settings.palette.selection : settings.palette.page
                                    border.color: nav.modelData.flagged ? "#BD955D" : "transparent" }
                                contentItem: Text { text: nav.modelData.number; color: nav.index===practice.session.index ? "white" : practice.ink; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 12 }
                                onClicked: reading.chooseQuestion(index)
                            }
                        }
                    }
                    Text { visible: practice.review && practice.wrongOnly && session.correct===session.total; text: "本次全部答对"; color: settings.palette.accent; font.pixelSize: 12 }
                    Flickable {
                        id: questionScroll; objectName: "readingPracticeQuestionScroll"; Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; contentWidth: width; contentHeight: questionColumn.height; boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        ColumnLayout { id: questionColumn; width: questionScroll.width-10; spacing: 10
                            Text { text: practice.question.stem || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                                font.family: session.language === "ja" ? "Yu Gothic UI" : "Georgia"; font.pixelSize: 19; lineHeight: 1.25; color: practice.ink }
                            Repeater { model: practice.question.options || []
                                ListeningOption { required property string modelData; required property int index
                                    objectName: "readingOption_"+letter; Layout.fillWidth: true; text: modelData; letter: "ABCD"[index]
                                    chosen: practice.review ? practice.question.answer===letter : practice.session.selected===letter
                                    enabled: !practice.review && !practice.session.paused; onClicked: reading.answer(letter) }
                            }
                            Rectangle { visible: practice.review; Layout.fillWidth: true; implicitHeight: explanationColumn.implicitHeight+28
                                radius: 9; color: settings.palette.page
                                ColumnLayout { id: explanationColumn; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 14; y: 14; spacing: 10
                                    Text { text: "你的选择 "+(session.selected || "未答")+"    正确答案 "+(practice.question.answer || ""); color: session.selected===practice.question.answer ? settings.palette.accent : "#AE6556"; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                    Text { text: practice.question.explanation || ""; color: practice.ink; font.pixelSize: 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    Repeater { model: practice.question.evidence || []
                                        AppButton { required property var modelData; objectName: "readingEvidence"; text: "定位原文 · 第 "+modelData.paragraph+" 段"; flat: true; onClicked: practice.locate(modelData) }
                                    }
                                }
                            }
                        }
                    }
                    Text { visible: !practice.review && !!session.paused; text: "计时已暂停"; color: practice.muted; font.pixelSize: 12 }
                    RowLayout { Layout.fillWidth: true
                        AppButton { objectName: "readingPracticePrevious"; text: "上一题"; enabled: session.index>0 && (practice.review || !session.paused); onClicked: practice.moveQuestion(-1) }
                        Item { Layout.fillWidth: true }
                        AppButton { objectName: "readingPracticeNext"; text: "下一题"; enabled: session.index<session.total-1 && (practice.review || !session.paused); onClicked: practice.moveQuestion(1) }
                    }
                }
            }
        }
        RowLayout { visible: practice.review; Layout.fillWidth: true
            AppButton { objectName: "readingPracticeRedo"; text: "重新练习"; flat: true; onClicked: reading.redo() }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "readingPracticeIntensive"; text: "精读本文"; onClicked: practice.intensiveRequested() }
            AppButton { objectName: "readingPracticeNextArticle"; text: practice.hasNext ? "下一篇练习  ›" : "回到阅读首页"; primary: true; onClicked: practice.nextRequested() }
        }
    }
    Popup { id: submitDialog; objectName: "readingSubmitDialog"; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; width: Math.min(420,parent.width-48); padding: 24
        background: Rectangle { radius: 13; color: settings.palette.surface }
        contentItem: ColumnLayout { spacing: 18
            Text { text: "提交本次练习"; font.pixelSize: 19; color: practice.ink }
            Text { text: session.answered<session.total ? "还有 "+(session.total-session.answered)+" 题未答，交卷后按未答记录。" : "已完成全部题目，交卷后查看复盘。"; color: practice.muted; font.pixelSize: 13; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout { Layout.fillWidth: true; Item { Layout.fillWidth: true }
                AppButton { text: "继续检查"; onClicked: submitDialog.close() }
                AppButton { objectName: "readingConfirmSubmit"; text: "确认交卷"; primary: true; onClicked: { practice.savePosition(); if (reading.submit()) submitDialog.close(); } }
            }
        }
    }
}
