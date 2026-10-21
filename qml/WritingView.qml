import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    objectName: "writingView"
    property color themeAccent: settings.palette.accent
    property color ink: "#26342C"
    property color muted: "#78877D"
    property color paper: settings.palette.surface
    property bool notesMode: false
    property bool libraryMode: true
    property bool librarySideOpen: false
    property bool reviewMode: false
    property bool reviewDrawerOpen: false
    property bool sideOpen: false
    property int sideWidth: writer.sideWidth
    property string sideMode: "both"
    property string loadedPath: ""
    property string pendingDelete: ""
    property string pendingDeleteTitle: ""
    property int activeIssue: -1
    property var previewMaterial: ({})
    property string reviewTab: "issues"
    property int elapsedSeconds: 0
    property int reviewElapsedSeconds: 0
    property bool reviewWaiting: false
    property bool topicExpanded: false
    property bool topicEditing: false
    property bool taskBound: !!writer.current.task_id
    property string taskState: writer.current.task_state || ""
    onVisibleChanged: if (!visible) { selectionNote.close(); saveNow(); writer.pauseTask() }
    Component.onDestruction: writer.pauseTask()
    property var selectionOwner: null
    property string selectionQuote: ""
    onLibraryModeChanged: selectionNote.close()
    onReviewModeChanged: selectionNote.close()
    onNotesModeChanged: selectionNote.close()
    function clearSelectionNote(source) {
        if (source === selectionOwner) selectionNote.close()
    }
    function showSelectionNote(source) {
        if (!view.visible || libraryMode || notesMode || notePopup.opened || !source.selectedText.trim()) return
        selectionOwner = source
        selectionQuote = source.selectedText
        var rect = source.positionToRectangle(source.selectionEnd)
        var point = source.mapToItem(view, rect.x, rect.y + rect.height)
        selectionNote.x = Math.max(8, Math.min(view.width - selectionNote.width - 8, point.x))
        selectionNote.y = Math.max(8, Math.min(view.height - selectionNote.height - 8, point.y + 7))
        selectionNote.open()
    }
    Popup {
        id: selectionNote
        objectName: "writingSelectionAction"
        parent: view
        focus: false; modal: false; padding: 5
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { radius: 10; color: settings.palette.surface; border.color: settings.palette.accent }
        AppButton {
            objectName: "writingSelectionSave"
            text: "＋ 记笔记"; flat: true; focusPolicy: Qt.NoFocus
            onClicked: {
                var quote = view.selectionQuote
                selectionNote.close()
                view.saveNow()
                notePopup.newNote(writer.currentPath, writer.current.language, quote)
            }
        }
    }

    function saveNow() {
        if (writer.currentPath && !reviewMode && !libraryMode && !notesMode)
            writer.saveDraft(titleField.text, topicField.text, draftText.text)
    }
    function showLibrary() { saveNow(); notesMode = false; writer.pauseTask(); reviewMode = false; libraryMode = true; librarySideOpen = false }
    function showMaterials() {
        if (libraryMode || !writer.currentPath) librarySideOpen = true
        else { sideMode = "library"; setSide(true) }
    }
    function startDraft(language, mode) {
        saveNow(); writer.newDraft(language)
        if (mode !== "practice") writer.setMode(mode)
        notesMode = false; libraryMode = false; librarySideOpen = false; reviewMode = false
        elapsedSeconds = 0
    }
    function openDraft(path) {
        saveNow(); writer.openDraft(path)
        notesMode = false; libraryMode = false; librarySideOpen = false; reviewMode = false
        elapsedSeconds = 0
    }
    function setSide(opened) { sideOpen = opened; writer.setSideOpen(opened) }
    function clampSideWidth(requested, areaWidth) {
        return Math.max(270, Math.min(650, Math.min(requested, areaWidth - 480)))
    }
    function toggleTarget(expression) {
        var values = (writer.current.targets || []).slice()
        var at = values.indexOf(expression)
        if (at >= 0) values.splice(at, 1)
        else values.push(expression)
        writer.setTargets(JSON.stringify(values))
    }
    function selectIssue(index) {
        activeIssue = index; reviewTab = "issues"; reviewDrawerOpen = true
        if (issueRepeater.itemAt(index))
            issueFlick.contentY = Math.max(0, Math.min(issueFlick.contentHeight - issueFlick.height,
                                                       issueRepeater.itemAt(index).y - 8))
        if (writer.reviewIssues[index] && writer.reviewIssues[index].paragraphIndex !== undefined) {
            var paragraph = paragraphRepeater.itemAt(writer.reviewIssues[index].paragraphIndex)
            if (paragraph)
                essayFlick.contentY = Math.max(0, Math.min(essayFlick.contentHeight - essayFlick.height, paragraph.y - 16))
        }
    }
    function reviewHtmlFor(paragraph) {
        var content = paragraph.html || ""
        if (activeIssue < 0) return content
        var marker = 'href="issue:' + activeIssue + '"'
        var at = content.indexOf(marker)
        if (at < 0) return content
        var open = content.lastIndexOf("<a ", at)
        var close = content.indexOf("</a>", at)
        if (open < 0 || close < 0) return content
        return content.slice(0, open) + '<span style="background-color:#DDEBDD;">'
               + content.slice(open, close + 4) + '</span>' + content.slice(close + 4)
    }
    Connections { target: writer
        function onChanged() {
            if (view.reviewWaiting && !writer.busy) view.reviewWaiting = false
            if (writer.currentPath && view.loadedPath !== writer.currentPath) {
                view.loadedPath = writer.currentPath
                titleField.text = writer.current.title === "未命名作文" ? "" : writer.current.title || ""
                topicField.text = writer.current.topic || ""
                draftText.text = writer.current.text || ""
                Qt.callLater(function() { writer.setDraftLineSpacing(draftText) })
                view.topicExpanded = false
                view.topicEditing = false
                view.sideOpen = !!writer.current.side_open
                view.reviewMode = false
                view.activeIssue = -1
            }
        }
        function onTopicReady() { topicField.text = writer.current.topic || ""; view.topicEditing = false }
        function onReviewReady() { view.reviewWaiting = false; view.reviewMode = true; view.reviewDrawerOpen = false
            view.activeIssue = -1; view.reviewTab = "issues" }
    }
    Connections {
        target: draftScroll.contentItem
        ignoreUnknownSignals: true
        function onContentYChanged() { selectionNote.close() }
    }
    Timer { id: autosave; interval: 900; onTriggered: view.saveNow() }
    Timer { interval: 1000; repeat: true
        running: view.visible && !view.libraryMode && !view.reviewMode
                 && !view.taskBound && writer.current.practice_style === "timed" && writer.current.writing_mode !== "practice"
        onTriggered: view.elapsedSeconds++ }
    Timer { interval: 1000; repeat: true; running: writer.busy && view.reviewWaiting
        onTriggered: view.reviewElapsedSeconds++ }

    WritingTaskPicker {
        id: taskPicker
        parent: Overlay.overlay
        onSelected: function(taskId, fresh) {
            view.saveNow()
            writer.openWritingTask(taskId, fresh)
            view.loadedPath = ""
            writer.changed()
            view.libraryMode = false; view.librarySideOpen = false; view.reviewMode = false
        }
    }

    Popup {
        id: submissionPopup
        objectName: "writingSubmissionPopup"
        parent: Overlay.overlay
        anchors.centerIn: Overlay.overlay
        modal: true; focus: true; padding: 22
        width: Math.min(680, view.width - 32); height: Math.min(520, view.height - 32)
        background: Rectangle { radius: 14; color: view.paper; border.color: "#DCE4DE" }
        Overlay.modal: Rectangle { color: "#650F1C16" }
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            RowLayout {
                Layout.fillWidth: true
                Text { text: "本次作答原稿"; font.pixelSize: 18; color: view.ink; Layout.fillWidth: true }
                AppButton { text: "关闭"; flat: true; onClicked: submissionPopup.close() }
            }
            Text { text: "结束作答时保存，后续修改不会覆盖。"; color: view.muted; font.pixelSize: 12 }
            ScrollView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea { width: parent.width; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                    text: (writer.current.submission || {}).text || "（空白作答）"
                    font.family: "Georgia"; font.pixelSize: 18; color: view.ink; background: Item {} }
            }
        }
    }

    Popup { id: deleteConfirm; objectName: "essayDeleteConfirm"
        modal: true; focus: true; anchors.centerIn: Overlay.overlay
        width: Math.min(400, view.width - 40); height: 194; padding: 22
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#650F1C16" }
        background: Rectangle { radius: 14; color: view.paper; border.color: "#E1E7E1" }
        ColumnLayout { anchors.fill: parent; spacing: 12
            Text { text: "删除作文"; color: view.ink; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap
                text: "即将删除「" + view.pendingDeleteTitle + "」。删除后无法在应用中恢复。"
                color: view.muted; font.pixelSize: 12 }
            Item { Layout.fillHeight: true }
            RowLayout { Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton { text: "取消"; onClicked: deleteConfirm.close() }
                AppButton { text: "删除作文"; primary: true; destructive: true
                    onClicked: { writer.deleteDraft(view.pendingDelete); deleteConfirm.close() } }
            }
        }
    }
    function captureWritingNote() {
        saveNow()
        var quote = draftText.selectedText || ""
        if (reviewMode && activeIssue >= 0 && writer.reviewIssues[activeIssue])
            quote = writer.reviewIssues[activeIssue].correction || writer.reviewIssues[activeIssue].quote || ""
        notePopup.newNote(writer.currentPath, writer.current.language, quote)
    }
    WritingNoteDialog {
        id: notePopup
        parent: Overlay.overlay
        onOpenEssay: function(path) { view.openDraft(path) }
    }
    Popup { id: materialPreviewPopup; modal: true; focus: true; anchors.centerIn: Overlay.overlay
        width: Math.min(490, view.width - 36); height: 326; padding: 20
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#650F1C16" }
        background: Rectangle { radius: 14; color: view.paper; border.color: "#E1E7E1" }
        ColumnLayout { anchors.fill: parent; spacing: 9
            Text { text: view.previewMaterial.expression || "素材"; Layout.fillWidth: true; wrapMode: Text.Wrap
                color: view.ink; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { text: view.previewMaterial.meaning || "尚未补充释义"; Layout.fillWidth: true; wrapMode: Text.Wrap
                color: "#536359"; font.pixelSize: 13 }
            Text { text: view.previewMaterial.usage || ""; visible: !!view.previewMaterial.usage
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#66756A"; font.pixelSize: 12 }
            Text { text: view.previewMaterial.example || ""; visible: !!view.previewMaterial.example
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#66756A"; font.pixelSize: 12 }
            Text { text: view.previewMaterial.context ? "学习原句：" + view.previewMaterial.context : ""
                visible: !!view.previewMaterial.context; Layout.fillWidth: true; wrapMode: Text.Wrap
                color: view.muted; font.pixelSize: 11 }
            Item { Layout.fillHeight: true }
            RowLayout { Layout.fillWidth: true
                AppButton { text: "到素材库编辑"; visible: !!view.previewMaterial.id
                    onClicked: { materialPreviewPopup.close(); view.showMaterials() } }
                Item { Layout.fillWidth: true }
                AppButton { text: "关闭"; onClicked: materialPreviewPopup.close() }
            }
        }
    }

    ColumnLayout { anchors.fill: parent
        anchors.rightMargin: view.librarySideOpen && view.width >= 900 ? librarySidePanel.width + 14 : 0
        spacing: 14; visible: !view.notesMode && (view.libraryMode || !writer.currentPath)
        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 48
            ColumnLayout { Layout.fillWidth: true; spacing: 3
                Text { text: "写作"; color: view.ink; font.pixelSize: 22; font.weight: Font.DemiBold }
            }
            AppButton { text: view.librarySideOpen ? "收起素材" : "我的素材"
                onClicked: view.librarySideOpen = !view.librarySideOpen }
        }
        WritingHome {
            Layout.fillWidth: true; Layout.fillHeight: true
            onStartDraft: function(language, mode) { view.startDraft(language, mode) }
            onPickTask: taskPicker.open()
            onOpenDraft: function(path) { view.openDraft(path) }
            onDeleteDraft: function(path, title) { view.pendingDelete = path; view.pendingDeleteTitle = title; deleteConfirm.open() }
            onAllNotes: { view.librarySideOpen = false; view.notesMode = true }
            onNewNote: notePopup.newNote("", "en", "")
            onEditNote: function(note) { notePopup.editNote(note) }
        }
    }

    WritingNotes {
        anchors.fill: parent; visible: view.notesMode
        onBack: view.notesMode = false
        onNewNote: notePopup.newNote("", "en", "")
        onEditNote: function(note) { notePopup.editNote(note) }
        onOpenDraft: function(path) { view.openDraft(path) }
    }

    Rectangle { id: librarySidePanel; z: 5
        visible: !view.notesMode && view.librarySideOpen && (view.libraryMode || !writer.currentPath)
        x: view.width - width
        width: Math.min(view.sideWidth, view.width >= 900 ? view.width - 500 : view.width - 28)
        height: view.height
        radius: 14; color: "#F9FBF8"; border.color: "#E2E9E1"
        Rectangle { x: 0; width: 3; height: parent.height; radius: 2
            color: listResize.containsMouse || listResize.pressed ? view.themeAccent : "transparent" }
        MouseArea { id: listResize; x: 0; width: 14; height: parent.height; z: 6
            hoverEnabled: true; cursorShape: Qt.SizeHorCursor; preventStealing: true
            onPositionChanged: function(mouse) {
                if (pressed && view.width >= 900) {
                    var point = mapToItem(view, mouse.x, mouse.y)
                    view.sideWidth = Math.max(270, Math.min(650, Math.min(view.width - point.x, view.width - 500)))
                }
            }
            onReleased: writer.setSideWidth(view.sideWidth)
        }
        ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 10
            RowLayout { Layout.fillWidth: true
                Text { text: "素材库"; Layout.fillWidth: true; color: view.ink
                    font.pixelSize: 16; font.weight: Font.DemiBold }
                AppButton { text: "收起"; flat: true; onClicked: view.librarySideOpen = false }
            }
            WritingMaterials { objectName: "listWritingMaterials"; Layout.fillWidth: true; Layout.fillHeight: true; compact: true
                sourceFilter: "favorites"
                dialogWidth: view.width; dialogHeight: view.height; themeAccent: view.themeAccent }
        }
    }

    ColumnLayout { anchors.fill: parent; spacing: 12
        visible: !view.notesMode && !view.libraryMode && !!writer.currentPath
        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 50; spacing: 8
            AppButton { text: "← 返回作文"; onClicked: view.showLibrary() }
            Text { Layout.fillWidth: true; text: view.reviewMode ? "对照批改" : "写作"
                color: view.ink; font.pixelSize: 20; font.weight: Font.DemiBold }
            AppButton { visible: view.reviewMode; text: "继续修改"; primary: true
                onClicked: { view.reviewMode = false; view.reviewDrawerOpen = false; draftText.forceActiveFocus() } }
            AppButton { visible: view.reviewMode && !body.inlineSide
                text: view.reviewDrawerOpen ? "收起建议" : "查看建议"
                onClicked: view.reviewDrawerOpen = !view.reviewDrawerOpen }
            AppButton { objectName: "writingCaptureNote"; text: "摘录 / 笔记"; flat: true
                onClicked: view.captureWritingNote() }
            AppButton { visible: !view.reviewMode && !!writer.current.review; text: "查看上次批改"
                onClicked: { view.saveNow(); view.reviewMode = true } }
            AppButton { visible: !view.reviewMode; text: view.sideOpen ? "收起素材" : "打开素材"
                onClicked: { if (!view.sideOpen) view.sideMode = "both"; view.setSide(!view.sideOpen) } }
        }
        Item { id: body; Layout.fillWidth: true; Layout.fillHeight: true
            property bool inlineSide: width >= 850
            Rectangle { id: sheet; objectName: "writingSheet"
                x: (view.reviewMode || view.sideOpen) && body.inlineSide
                   ? (body.width - sidePanel.width - width) / 2 : (body.width - width) / 2
                 width: (view.reviewMode || view.sideOpen) && body.inlineSide
                        ? Math.min(730, body.width - sidePanel.width - 14) : Math.min(body.width, 730)
                height: body.height; radius: 15; color: view.paper; border.color: "#E5E9E2"
                ColumnLayout { anchors.fill: parent; anchors.margins: sheet.width < 600 ? 17 : 26; spacing: 12
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 43; visible: !view.reviewMode
                        TextField { id: titleField; objectName: "writingTitleField"; Layout.fillWidth: true; Layout.preferredHeight: 42
                            placeholderText: "给这篇作文起个标题"; font.pixelSize: 22; font.weight: Font.DemiBold
                            color: view.ink; background: Item {}
                            onTextChanged: autosave.restart() }
                        Text { text: writer.current.language === "ja" ? "日语" : "英语";
                            color: view.muted; font.pixelSize: 11 }
                    }
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 38; visible: !view.reviewMode && !view.taskBound
                        Text { text: writer.current.writing_mode === "toefl_email" ? "托福 · 邮件"
                                   : writer.current.writing_mode === "toefl_discussion" ? "托福 · 学术讨论"
                                   : writer.current.language === "ja" ? "日语表达" : "英语自由写作"
                            color: view.themeAccent; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        AppCombo { visible: !view.taskBound && writer.current.writing_mode !== "practice"; Layout.preferredWidth: 112
                            model: ["引导练习", "限时模拟"]
                            currentIndex: writer.current.practice_style === "timed" ? 1 : 0
                            onActivated: { writer.setPracticeStyle(currentIndex === 1 ? "timed" : "guided"); view.elapsedSeconds = 0 } }
                        Text { visible: !view.taskBound && writer.current.practice_style === "timed" && writer.current.writing_mode !== "practice"
                            text: {
                                var limit = writer.current.writing_mode === "toefl_email" ? 420 : 600
                                var left = Math.max(0, limit - view.elapsedSeconds)
                                return left > 0 ? Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0") : "时间到"
                            }
                            color: view.themeAccent; font.pixelSize: 13; font.bold: true }
                    }
                    ColumnLayout {
                        visible: view.taskBound && !view.reviewMode
                        Layout.fillWidth: true; spacing: 7
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11; color: view.muted
                            text: (writer.current.writing_mode === "toefl_email" ? "托福专项 · 邮件" : "托福专项 · 学术讨论")
                                + (writer.current.topic_source === "demo" ? " · 演示题（非真题，时限仅作演示）" : " · " + writer.current.task_source) }
                        Flow {
                            Layout.fillWidth: true; spacing: 8
                            Text { objectName: "writingTaskTimer"; height: 34; verticalAlignment: Text.AlignVCenter
                                text: view.taskState === "untimed" ? "不限时练习"
                                    : view.taskState === "finished" || view.taskState === "editing" ? "作答已结束 · 原稿已保存"
                                    : Math.floor(writer.taskRemaining / 60) + ":" + String(writer.taskRemaining % 60).padStart(2, "0")
                                        + (view.taskState === "paused" ? " · 已暂停" : view.taskState === "ready" ? " · 待开始" : "")
                                color: view.themeAccent; font.pixelSize: 14; font.weight: Font.DemiBold }
                            AppButton { objectName: "writingTaskStart"; visible: view.taskState === "ready" || view.taskState === "paused"
                                text: view.taskState === "ready" ? "开始计时" : "继续计时"; primary: true
                                onClicked: { view.saveNow(); writer.startTask(); draftText.forceActiveFocus() } }
                            AppButton { objectName: "writingTaskPause"; visible: view.taskState === "running"; text: "暂停"
                                onClicked: { view.saveNow(); writer.pauseTask() } }
                            AppButton { objectName: "writingTaskUntimed"; visible: ["ready", "paused", "untimed"].indexOf(view.taskState) >= 0
                                text: view.taskState === "untimed" ? "切回计时" : "不限时练习"; flat: true
                                onClicked: { view.saveNow(); writer.untimedTask() } }
                            AppButton { objectName: "writingTaskFinish"; visible: ["running", "paused", "untimed"].indexOf(view.taskState) >= 0
                                text: "结束作答"; onClicked: { view.saveNow(); writer.finishTask() } }
                            AppButton { objectName: "writingTaskEdit"; visible: view.taskState === "finished"; text: "继续修改"
                                onClicked: { writer.editTask(); draftText.forceActiveFocus() } }
                            AppButton { objectName: "writingTaskOriginal"; visible: !!writer.current.submission; text: "查看原稿"; flat: true
                                onClicked: submissionPopup.open() }
                        }
                    }
                     Rectangle { id: topicCard; Layout.fillWidth: true
                         property bool expanded: view.topicExpanded || !!topicField.text.trim()
                                                 || writer.current.writing_mode !== "practice"
                         property bool printed: !!topicField.text.trim() && !view.topicEditing
                         Layout.preferredHeight: !expanded ? 44
                            : printed ? (view.taskBound ? Math.min(printedTopic.implicitHeight + 64, Math.max(130, view.height * 0.27)) : printedTopic.implicitHeight + 64)
                            : Math.min(view.height > 650 ? 170 : 118,
                                       Math.max(106, topicField.contentHeight + 40))
                        color: printed ? view.paper : "#F8FAF7"; radius: printed ? 0 : 9
                        visible: !view.reviewMode
                         RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 10
                             visible: !topicCard.expanded
                             Text { text: "可自拟题目或写作任务"; Layout.fillWidth: true
                                 color: view.muted; font.pixelSize: 12 }
                             AppButton { text: "添加题目"; flat: true
                                 onClicked: { view.topicExpanded = true; view.topicEditing = true; topicField.forceActiveFocus() } }
                         }
                         ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 5
                             visible: topicCard.expanded
                            RowLayout { Layout.fillWidth: true
                                Text { text: writer.current.writing_mode === "practice" ? "主题或写作任务" : "本次题目"
                                    color: view.ink; font.pixelSize: 11; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                Text { visible: !!topicField.text; text: view.taskBound ? "上下滚动查看完整题目" : writer.current.topic_source === "ai" ? "AI 模拟题"
                                        : writer.current.topic_source === "ets_user_entry" ? "ETS 材料 · 自行录入" : "自定题目"
                                    color: view.muted; font.pixelSize: 10 }
                                AppButton { visible: !view.taskBound && writer.current.writing_mode === "practice" && !topicField.text.trim()
                                    objectName: "collapseWritingTopicButton"; text: "收起"; flat: true
                                    onClicked: { view.topicExpanded = false; view.topicEditing = false; draftText.forceActiveFocus() } }
                                AppButton { visible: topicCard.printed && !view.taskBound; text: "修改题目"; flat: true
                                    onClicked: { view.topicEditing = true; topicField.forceActiveFocus() } }
                                AppButton { visible: view.topicEditing && !!topicField.text.trim()
                                    text: "完成"; flat: true
                                    onClicked: { view.saveNow(); view.topicEditing = false; draftText.forceActiveFocus() } }
                            }
                            ScrollView { id: promptScroll; Layout.fillWidth: true; Layout.fillHeight: true; visible: topicCard.printed; clip: true
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                                ScrollBar.vertical.policy: view.taskBound ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
                            Text { id: printedTopic; objectName: "printedWritingTopic"
                                width: Math.max(0, promptScroll.availableWidth - 14); visible: topicCard.printed
                                text: topicField.text; textFormat: Text.PlainText; wrapMode: Text.Wrap
                                font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                                font.pixelSize: 16; lineHeight: 1.4; color: view.ink }
                            }
                            ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; visible: !topicCard.printed && !view.taskBound
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                                TextArea { id: topicField; objectName: "writingTopicField"
                                    implicitWidth: 0
                                    placeholderText: "可自己输入题目，也可以用 AI 生成模拟题"; wrapMode: TextEdit.Wrap
                                    font.pixelSize: 12; color: view.ink; background: Item {}
                                    onActiveFocusChanged: { if (activeFocus) view.topicEditing = true }
                                    onTextChanged: autosave.restart() }
                            }
                        }
                    }
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 35; visible: !view.reviewMode && !view.taskBound
                        Text { text: (writer.current.targets || []).length > 0
                                ? "本次目标 · " + (writer.current.targets || []).join("、") : "本次未指定目标表达"
                            Layout.fillWidth: true; elide: Text.ElideRight; color: view.muted; font.pixelSize: 11 }
                        AppButton { visible: !view.taskBound; text: writer.busy ? "生成中…" : "AI 模拟题"; flat: true; enabled: !writer.busy
                            onClicked: { view.saveNow(); writer.generateTopic() } }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#E9EDE7" }
                    ScrollView { id: draftScroll; Layout.fillWidth: true; Layout.fillHeight: true; visible: !view.reviewMode
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        TextArea { id: draftText; objectName: "writingDraftField"; implicitWidth: 0; width: Math.max(0, draftScroll.availableWidth)
                            wrapMode: TextEdit.Wrap; selectByMouse: true; persistentSelection: true
                            readOnly: view.taskBound && ["ready", "paused", "finished"].indexOf(view.taskState) >= 0
                            placeholderText: view.taskBound && view.taskState === "ready" ? "点击开始计时，或选择不限时练习" : "从这里开始写"
                             font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                             font.pixelSize: 19
                            WritingSelectionHook {
                                onNoteRequested: function(source) { view.showSelectionNote(source) }
                                onSelectionCleared: function(source) { view.clearSelectionNote(source) }
                            }
                            cursorDelegate: Item { width: 0; height: 0 }
                            Rectangle {
                                id: smoothCaret; objectName: "animatedWritingCaret"
                                x: draftText.cursorRectangle.x - 1; y: draftText.cursorRectangle.y
                                width: 2; height: draftText.cursorRectangle.height; radius: 1
                                color: view.themeAccent; z: 2
                                visible: draftText.activeFocus && draftText.cursorVisible
                                Behavior on x { NumberAnimation { duration: 85; easing.type: Easing.OutCubic } }
                                Behavior on y { NumberAnimation { duration: 105; easing.type: Easing.OutCubic } }
                                SequentialAnimation on opacity {
                                    running: smoothCaret.visible; loops: Animation.Infinite
                                    NumberAnimation { from: 1; to: 1; duration: 650 }
                                    NumberAnimation { from: 0; to: 0; duration: 400 }
                                }
                            }
                            color: view.ink; leftPadding: 10; rightPadding: 14; topPadding: 16; bottomPadding: 24
                            background: Item {}
                            onTextChanged: { if (view.taskBound) writer.updateTaskText(text); autosave.restart() } }
                    }
                    ColumnLayout { Layout.fillWidth: true; Layout.fillHeight: true; visible: view.reviewMode; spacing: 9
                        Text { text: writer.current.title || "作文批改"; Layout.fillWidth: true; elide: Text.ElideRight
                            color: view.ink; font.pixelSize: 21; font.weight: Font.DemiBold }
                        Text { text: "点击下划线查看对应建议"; color: view.muted; font.pixelSize: 11 }
                        Flickable { id: essayFlick; onContentYChanged: selectionNote.close(); Layout.fillWidth: true; Layout.fillHeight: true
                            contentWidth: width; contentHeight: paragraphColumn.height + 20; clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            Column { id: paragraphColumn; width: essayFlick.width - 16; spacing: 15
                                Repeater { id: paragraphRepeater; model: writer.reviewParagraphs
                                    delegate: Rectangle { required property var modelData
                                        width: paragraphColumn.width; height: paragraphText.implicitHeight + 12
                                        radius: 7; color: "transparent"
                                        WritingSelectableText { id: paragraphText; objectName: "writingReviewParagraph"; x: 6; y: 6; width: parent.width - 12
                                            text: view.reviewHtmlFor(modelData); textFormat: TextEdit.RichText; wrapMode: TextEdit.Wrap
                                             font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                                             font.pixelSize: 18
                                            color: view.ink
                                            onNoteRequested: function(source) { view.showSelectionNote(source) }
                                            onSelectionCleared: function(source) { view.clearSelectionNote(source) }
                                            onLinkActivated: function(link) {
                                                var index = parseInt(link.split(":")[1])
                                                if (!isNaN(index)) view.selectIssue(index)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#E9EDE7" }
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 38
                        Text { Layout.fillWidth: true; elide: Text.ElideRight; color: view.muted; font.pixelSize: 11
                            text: writer.busy ? (view.reviewWaiting ? writer.status + " · " + view.reviewElapsedSeconds + " 秒" : writer.status)
                                : view.reviewMode ? "批改是提交时的快照；草稿仍可继续修改。"
                                : "自动保存  ·  " + (writer.current.language === "ja" ? draftText.text.trim().length + " 字"
                                  : (draftText.text.trim() ? draftText.text.trim().split(/\s+/).length : 0) + " 词") }
                        AppButton { visible: view.reviewMode; text: "记笔记"; onClicked: view.captureWritingNote() }
                        AppButton { visible: !view.reviewMode; text: "保存草稿"; onClicked: view.saveNow() }
                        AppButton { objectName: "writingReviewSubmit"; visible: !view.reviewMode; text: writer.busy ? "正在批改…" : "提交批改"; primary: true
                            enabled: !writer.busy && draftText.text.trim().length > 0
                                && (!view.taskBound || ["finished", "editing", "untimed"].indexOf(view.taskState) >= 0)
                            onClicked: { view.saveNow(); view.reviewElapsedSeconds = 0; view.reviewWaiting = true; writer.review() } }
                    }
                }
            }
            Rectangle { visible: (view.reviewMode ? view.reviewDrawerOpen : view.sideOpen) && !body.inlineSide
                anchors.fill: parent; z: 1; color: "#370F1C16"
                MouseArea { anchors.fill: parent; onClicked: {
                    if (view.reviewMode) view.reviewDrawerOpen = false
                    else view.setSide(false)
                } } }
            Rectangle { id: sidePanel; objectName: "writingSidePanel"; z: 2
                visible: view.reviewMode ? (body.inlineSide || view.reviewDrawerOpen) : view.sideOpen
                x: body.width - width
                width: body.inlineSide ? view.clampSideWidth(view.sideWidth, body.width)
                       : Math.min(view.sideWidth, body.width - 34)
                height: body.height
                radius: 14; color: "#F9FBF8"; border.color: "#E2E9E1"
                Rectangle { x: 0; width: 3; height: parent.height; radius: 2
                    color: sideResize.containsMouse || sideResize.pressed ? view.themeAccent : "transparent" }
                MouseArea { id: sideResize; x: 0; width: 14; height: parent.height; z: 6
                    visible: body.inlineSide; hoverEnabled: true; cursorShape: Qt.SizeHorCursor
                    preventStealing: true
                    onPositionChanged: function(mouse) {
                        if (pressed) {
                            var point = mapToItem(body, mouse.x, mouse.y)
                            view.sideWidth = view.clampSideWidth(body.width - point.x, body.width)
                        }
                    }
                    onReleased: writer.setSideWidth(view.sideWidth)
                }
                ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 10
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 37; Layout.maximumHeight: 37
                        Text { text: view.reviewMode ? "批改建议" : "写作素材"; Layout.fillWidth: true
                            color: view.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        AppButton { text: writer.busy ? "生成中…" : "生成"
                            visible: !view.reviewMode && view.sideMode !== "library"
                                     && writer.current.practice_style !== "timed"
                            enabled: !writer.busy
                            onClicked: { view.saveNow(); writer.generateMaterials("常用、准确") } }
                        AppButton { objectName: "addSidebarMaterialButton"
                            text: "+ 添加"; visible: !view.reviewMode && view.sideMode !== "ai"
                            onClicked: editorWritingMaterials.openAdd() }
                        AppButton { visible: !body.inlineSide; text: "收起"; flat: true
                            onClicked: { if (view.reviewMode) view.reviewDrawerOpen = false; else view.setSide(false) } }
                    }
                    ColumnLayout { Layout.fillWidth: true; Layout.fillHeight: true
                        visible: !view.reviewMode; spacing: 8
                        RowLayout { Layout.fillWidth: true; Layout.maximumHeight: 36
                            AppButton { text: "全部"; primary: view.sideMode === "both"; Layout.fillWidth: true
                                onClicked: view.sideMode = "both" }
                            AppButton { text: "AI"; primary: view.sideMode === "ai"; Layout.fillWidth: true
                                onClicked: view.sideMode = "ai" }
                            AppButton { text: "我的"; primary: view.sideMode === "library"; Layout.fillWidth: true
                                onClicked: view.sideMode = "library" }
                            AppButton { text: "收藏"; primary: view.sideMode === "favorites"; Layout.fillWidth: true
                                onClicked: view.sideMode = "favorites" }
                        }
                        WritingMaterials { id: editorWritingMaterials; objectName: "editorWritingMaterials"
                            Layout.fillWidth: true; Layout.fillHeight: true
                            compact: true; returnToDraft: true; sourceFilter: view.sideMode
                            dialogWidth: view.width; dialogHeight: view.height; themeAccent: view.themeAccent
                            onGenerateAi: { view.saveNow(); writer.generateMaterials("常用、准确") }
                            onPreviewAi: function(material) {
                                view.previewMaterial = material; materialPreviewPopup.open()
                            }
                            onTargetAi: function(expression) { view.toggleTarget(expression) }
                            onCollectAi: function(material) {
                                var kind = material.kind === "grammar" ? "grammar" : "vocabulary"
                                var existed = false
                                for (var n = 0; n < writer.library.length; n++) {
                                    var entry = writer.library[n]
                                    if (entry.essay_id === writer.currentEssayId
                                            && entry.language === writer.current.language && entry.kind === kind
                                            && entry.expression.toLowerCase() === material.expression.toLowerCase()) {
                                        existed = true; break
                                    }
                                }
                                var id = writer.saveMaterial(writer.current.language, kind,
                                                             material.expression, "", "")
                                if (id && !existed) {
                                    writer.updateMaterial(id, material.meaning || "", material.usage || "",
                                                          material.example || "", "")
                                    writer.updateMaterialRelated(id, material.related || "")
                                }
                            }
                        }
                    }
                    ColumnLayout { Layout.fillWidth: true; Layout.fillHeight: true; visible: view.reviewMode; spacing: 8
                        RowLayout { Layout.fillWidth: true
                            AppButton { text: "具体问题"; primary: view.reviewTab === "issues"; Layout.fillWidth: true
                                onClicked: view.reviewTab = "issues" }
                            AppButton { text: "全文建议"; primary: view.reviewTab === "overview"; Layout.fillWidth: true
                                onClicked: view.reviewTab = "overview" }
                        }
                        Flickable { id: issueFlick; onContentYChanged: selectionNote.close(); Layout.fillWidth: true; Layout.fillHeight: true
                            visible: view.reviewTab === "issues"; contentWidth: width
                            contentHeight: issueColumn.height + 10; clip: true; boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            Column { id: issueColumn; width: issueFlick.width - 10; spacing: 8
                                Text { width: parent.width; text: writer.reviewIssues.length + " 条具体建议"
                                    color: view.muted; font.pixelSize: 11 }
                                Repeater { id: issueRepeater; model: writer.reviewIssues
                                    delegate: Rectangle { required property var modelData; required property int index
                                        width: issueColumn.width; height: issueContent.implicitHeight + 18; radius: 9
                                        color: view.activeIssue === index ? settings.palette.selection : view.paper
                                        border.color: view.activeIssue === index ? view.themeAccent : "#E4EAE3"
                                        Column { id: issueContent; x: 10; y: 9; width: parent.width - 20; spacing: 5
                                            Text { width: parent.width; text: (index + 1) + " · "
                                                    + (modelData.kind === "style" ? "可选表达" : modelData.category)
                                                color: view.themeAccent; font.pixelSize: 11; font.weight: Font.DemiBold }
                                            Text { width: parent.width; text: modelData.quote; textFormat: Text.PlainText
                                                wrapMode: Text.Wrap; color: view.muted; font.pixelSize: 12 }
                                            WritingSelectableText { objectName: "writingCorrectedSentence"; width: parent.width; text: modelData.correction
                                                color: view.ink; font.pixelSize: 13; font.weight: Font.DemiBold
                                                onNoteRequested: function(source) { view.showSelectionNote(source) }
                                                onSelectionCleared: function(source) { view.clearSelectionNote(source) } }
                                            Text { width: parent.width; text: modelData.reason; wrapMode: Text.Wrap
                                                color: "#607066"; font.pixelSize: 11 }
                                            Text { visible: !modelData.linked; text: "原文位置不唯一，保留为待核对建议"
                                                color: view.muted; font.pixelSize: 10 }
                                        }
                                        TapHandler { onTapped: view.selectIssue(index) }
                                    }
                                }
                                Text { visible: writer.reviewIssues.length === 0; width: parent.width; wrapMode: Text.Wrap
                                    text: "本次没有可定位的具体问题，请查看全文建议。"; color: view.muted; font.pixelSize: 12 }
                            }
                        }
                        Flickable { id: overviewFlick; objectName: "writingOverviewScroll"; onContentYChanged: selectionNote.close(); Layout.fillWidth: true; Layout.fillHeight: true; visible: view.reviewTab === "overview"
                            contentWidth: width; contentHeight: overviewColumn.height + 10; clip: true
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            Column { id: overviewColumn; width: parent.width - 10; spacing: 12
                                Text { text: "整体评价"; color: view.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                Text { width: parent.width; wrapMode: Text.Wrap; text: writer.current.review ? writer.current.review.overall || "" : ""
                                    color: "#536359"; font.pixelSize: 12; lineHeight: 1.4 }
                                Text { visible: !!writer.current.review && (writer.current.review.priorities || []).length > 0
                                    text: "优先修改"; color: view.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                Repeater { model: writer.current.review ? writer.current.review.priorities || [] : []
                                    delegate: Text { required property var modelData; width: overviewColumn.width; wrapMode: Text.Wrap
                                        text: "• " + modelData; color: "#536359"; font.pixelSize: 12 } }
                                Text { visible: !!(writer.current.review && writer.current.review.targetFeedback)
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: "目标表达：" + (writer.current.review ? writer.current.review.targetFeedback || "" : "")
                                    color: "#536359"; font.pixelSize: 12 }
                                Text { visible: !!(writer.current.review && writer.current.review.revisedText)
                                    text: "参考改写"; color: view.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                WritingSelectableText { objectName: "writingAiRevisedText"; visible: !!(writer.current.review && writer.current.review.revisedText)
                                    width: parent.width
                                    text: writer.current.review ? writer.current.review.revisedText || "" : ""
                                    color: "#536359"; font.pixelSize: 14
                                    onNoteRequested: function(source) { view.showSelectionNote(source) }
                                    onSelectionCleared: function(source) { view.clearSelectionNote(source) } }
                            }
                        }
                        AppButton { text: "记下修改心得"; Layout.fillWidth: true; onClicked: view.captureWritingNote() }
                    }
                }
            }
        }
    }
}
