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
    property bool libraryMode: true
    property bool librarySideOpen: false
    property bool reviewMode: false
    property bool reviewDrawerOpen: false
    property bool sideOpen: false
    property int sideWidth: writer.sideWidth
    property string sideMode: "both"
    property string loadedPath: ""
    property string draftQuery: ""
    property string draftFilter: "all"
    property bool favoritesOnly: false
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
    signal openNotes()

    function saveNow() {
        if (writer.currentPath && !reviewMode && !libraryMode)
            writer.saveDraft(titleField.text, topicField.text, draftText.text)
    }
    function showLibrary() { saveNow(); reviewMode = false; libraryMode = true; librarySideOpen = false }
    function showMaterials() {
        if (libraryMode || !writer.currentPath) librarySideOpen = true
        else { sideMode = "library"; setSide(true) }
    }
    function startDraft(language, mode) {
        saveNow(); writer.newDraft(language)
        if (mode !== "practice") writer.setMode(mode)
        libraryMode = false; librarySideOpen = false; reviewMode = false
        elapsedSeconds = 0
    }
    function openDraft(path) {
        saveNow(); writer.openDraft(path)
        libraryMode = false; librarySideOpen = false; reviewMode = false
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
    function visibleDrafts() {
        var result = []
        var query = draftQuery.trim().toLowerCase()
        for (var i = 0; i < writer.drafts.length; i++) {
            var item = writer.drafts[i]
            if (favoritesOnly && !item.favorite) continue
            if (draftFilter === "reviewed" && !item.reviewed) continue
            if (draftFilter === "draft" && item.reviewed) continue
            if (query && (item.title + " " + (item.preview || "")).toLowerCase().indexOf(query) < 0) continue
            result.push(item)
        }
        return result
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
    Timer { id: autosave; interval: 900; onTriggered: view.saveNow() }
    Timer { interval: 1000; repeat: true
        running: view.visible && !view.libraryMode && !view.reviewMode
                 && writer.current.practice_style === "timed" && writer.current.writing_mode !== "practice"
        onTriggered: view.elapsedSeconds++ }
    Timer { interval: 1000; repeat: true; running: writer.busy && view.reviewWaiting
        onTriggered: view.reviewElapsedSeconds++ }

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
    Popup { id: notePopup; modal: true; focus: true; anchors.centerIn: Overlay.overlay
        width: Math.min(480, view.width - 40); height: 300; padding: 20
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#650F1C16" }
        background: Rectangle { radius: 14; color: view.paper; border.color: "#E1E7E1" }
        ColumnLayout { anchors.fill: parent; spacing: 11
            Text { text: "写下这次的发现"; color: view.ink; font.pixelSize: 18; font.weight: Font.DemiBold }
            TextArea { id: noteText; Layout.fillWidth: true; Layout.fillHeight: true
                wrapMode: TextEdit.Wrap; placeholderText: "我发现……"; font.pixelSize: 13
                background: Rectangle { radius: 9; color: "#FAFBFA"; border.color: "#DCE4DE" } }
            RowLayout { Layout.fillWidth: true
                AppButton { text: "全部笔记"; onClicked: { notePopup.close(); view.openNotes() } }
                Item { Layout.fillWidth: true }
                AppButton { text: "取消"; onClicked: notePopup.close() }
                AppButton { text: "保存笔记"; primary: true; enabled: noteText.text.trim().length > 0
                    onClicked: { writer.addNote(noteText.text, ""); noteText.clear(); notePopup.close() } }
            }
        }
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
        spacing: 14; visible: view.libraryMode || !writer.currentPath
        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 48
            ColumnLayout { Layout.fillWidth: true; spacing: 3
                Text { text: "写作"; color: view.ink; font.pixelSize: 22; font.weight: Font.DemiBold }
            }
            AppButton { text: view.librarySideOpen ? "收起素材" : "我的素材"
                onClicked: view.librarySideOpen = !view.librarySideOpen }
        }
        ScrollView { id: writingScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            Column { width: Math.max(0, writingScroll.width - 14); spacing: 16
                Rectangle { width: parent.width; height: 120; radius: 14
                    color: view.paper; border.color: "#E3E8E2"
                    Column { x: 20; y: 18; width: parent.width - 40; spacing: 11
                        Text { text: "开始新的练习"; color: view.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                        Row { spacing: 9
                            AppButton { text: "日语表达练习"; onClicked: view.startDraft("ja", "practice") }
                            AppButton { text: "英语自由写作"; onClicked: view.startDraft("en", "practice") }
                            AppButton { text: "托福邮件"; onClicked: view.startDraft("en", "toefl_email") }
                            AppButton { text: "托福学术讨论"; onClicked: view.startDraft("en", "toefl_discussion") }
                        }
                    }
                }
                Rectangle { width: parent.width; height: draftList.count === 0 ? 170 : Math.max(230, 80 + draftList.count * 91)
                    radius: 14; color: view.paper; border.color: "#E3E8E2"
                    ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 11
                        RowLayout { Layout.fillWidth: true
                            Text { text: "我的作文"; Layout.fillWidth: true; color: view.ink
                                font.pixelSize: 17; font.weight: Font.DemiBold }
                            AppButton { text: view.favoritesOnly ? "★ 收藏" : "☆ 收藏"; flat: true
                                onClicked: view.favoritesOnly = !view.favoritesOnly }
                        }
                        RowLayout { Layout.fillWidth: true; spacing: 8
                            TextField { id: searchDraft; Layout.fillWidth: true; Layout.preferredHeight: 35
                                placeholderText: "搜索标题或正文"; font.pixelSize: 12; leftPadding: 12
                                onTextChanged: view.draftQuery = text
                                background: Rectangle { radius: 8; color: "#FAFBFA"
                                    border.color: searchDraft.activeFocus ? view.themeAccent : "#DCE4DE" } }
                            AppCombo { Layout.preferredWidth: 104; model: ["全部", "待批改", "已批改"]
                                onActivated: view.draftFilter = ["all", "draft", "reviewed"][currentIndex] }
                        }
                        ListView { id: draftList; Layout.fillWidth: true; Layout.fillHeight: draftList.count > 0
                            visible: draftList.count > 0
                            clip: true; spacing: 7; model: view.visibleDrafts()
                            delegate: Rectangle {
                                required property var modelData
                                width: draftList.width - 8; height: 79; radius: 9
                                color: draftHover.containsMouse ? settings.palette.selection : "#FAFBFA"
                                border.color: "#E6EBE6"
                                Text { x: 14; y: 9; width: parent.width - 135; elide: Text.ElideRight
                                    text: modelData.title; color: view.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                                Text { x: 14; y: 31; width: parent.width - 135; elide: Text.ElideRight
                                    text: modelData.preview || "空白草稿，点击继续写作"; color: "#6E7D72"; font.pixelSize: 11 }
                                Text { x: 14; y: 56; width: parent.width - 135; elide: Text.ElideRight
                                    text: (modelData.language === "ja" ? "日语" : "英语") + " · " + modelData.updatedLabel
                                        + (modelData.reviewed ? " · 已有批改" : " · 待批改")
                                    color: "#89958B"; font.pixelSize: 10 }
                                MouseArea { id: draftHover; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: view.openDraft(modelData.path) }
                                AppButton { anchors.right: removeDraft.left; anchors.rightMargin: 3; y: 21; z: 2
                                    text: modelData.favorite ? "★" : "☆"; flat: true
                                    onClicked: writer.toggleDraftFavorite(modelData.path) }
                                AppButton { id: removeDraft; anchors.right: parent.right; anchors.rightMargin: 8; y: 21; z: 2
                                    text: "删除"; flat: true; onClicked: {
                                        view.pendingDelete = modelData.path
                                        view.pendingDeleteTitle = modelData.title
                                        deleteConfirm.open()
                                    } }
                            }
                        }
                        Text { visible: draftList.count === 0; Layout.fillWidth: true
                            text: writer.drafts.length === 0 ? "暂无作文" : "没有符合条件的作文"
                            color: view.muted; font.pixelSize: 12 }
                    }
                }
            }
        }
    }

    Rectangle { id: librarySidePanel; z: 5
        visible: view.librarySideOpen && (view.libraryMode || !writer.currentPath)
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
        visible: !view.libraryMode && !!writer.currentPath
        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 50; spacing: 8
            AppButton { text: "← 返回作文"; onClicked: view.showLibrary() }
            Text { Layout.fillWidth: true; text: view.reviewMode ? "对照批改" : "写作"
                color: view.ink; font.pixelSize: 20; font.weight: Font.DemiBold }
            AppButton { visible: view.reviewMode; text: "继续修改"; primary: true
                onClicked: { view.reviewMode = false; view.reviewDrawerOpen = false; draftText.forceActiveFocus() } }
            AppButton { visible: view.reviewMode && !body.inlineSide
                text: view.reviewDrawerOpen ? "收起建议" : "查看建议"
                onClicked: view.reviewDrawerOpen = !view.reviewDrawerOpen }
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
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 38; visible: !view.reviewMode
                        Text { text: writer.current.writing_mode === "toefl_email" ? "托福 · 邮件"
                                   : writer.current.writing_mode === "toefl_discussion" ? "托福 · 学术讨论"
                                   : writer.current.language === "ja" ? "日语表达" : "英语自由写作"
                            color: view.themeAccent; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        AppCombo { visible: writer.current.writing_mode !== "practice"; Layout.preferredWidth: 112
                            model: ["引导练习", "限时模拟"]
                            currentIndex: writer.current.practice_style === "timed" ? 1 : 0
                            onActivated: { writer.setPracticeStyle(currentIndex === 1 ? "timed" : "guided"); view.elapsedSeconds = 0 } }
                        Text { visible: writer.current.practice_style === "timed" && writer.current.writing_mode !== "practice"
                            text: {
                                var limit = writer.current.writing_mode === "toefl_email" ? 420 : 600
                                var left = Math.max(0, limit - view.elapsedSeconds)
                                return left > 0 ? Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0") : "时间到"
                            }
                            color: view.themeAccent; font.pixelSize: 13; font.bold: true }
                    }
                     Rectangle { id: topicCard; Layout.fillWidth: true
                         property bool expanded: view.topicExpanded || !!topicField.text.trim()
                                                 || writer.current.writing_mode !== "practice"
                         property bool printed: !!topicField.text.trim() && !view.topicEditing
                         Layout.preferredHeight: !expanded ? 44
                            : printed ? printedTopic.implicitHeight + 64
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
                                Text { visible: !!topicField.text; text: writer.current.topic_source === "ai" ? "AI 模拟题"
                                        : writer.current.topic_source === "ets_user_entry" ? "ETS 材料 · 自行录入" : "自定题目"
                                    color: view.muted; font.pixelSize: 10 }
                                AppButton { visible: writer.current.writing_mode === "practice" && !topicField.text.trim()
                                    objectName: "collapseWritingTopicButton"; text: "收起"; flat: true
                                    onClicked: { view.topicExpanded = false; view.topicEditing = false; draftText.forceActiveFocus() } }
                                AppButton { visible: topicCard.printed; text: "修改题目"; flat: true
                                    onClicked: { view.topicEditing = true; topicField.forceActiveFocus() } }
                                AppButton { visible: view.topicEditing && !!topicField.text.trim()
                                    text: "完成"; flat: true
                                    onClicked: { view.saveNow(); view.topicEditing = false; draftText.forceActiveFocus() } }
                            }
                            Text { id: printedTopic; objectName: "printedWritingTopic"
                                Layout.fillWidth: true; visible: topicCard.printed
                                text: topicField.text; textFormat: Text.PlainText; wrapMode: Text.Wrap
                                font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                                font.pixelSize: 16; lineHeight: 1.4; color: view.ink }
                            ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; visible: !topicCard.printed
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
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 35; visible: !view.reviewMode
                        Text { text: (writer.current.targets || []).length > 0
                                ? "本次目标 · " + (writer.current.targets || []).join("、") : "本次未指定目标表达"
                            Layout.fillWidth: true; elide: Text.ElideRight; color: view.muted; font.pixelSize: 11 }
                        AppButton { text: writer.busy ? "生成中…" : "AI 模拟题"; flat: true; enabled: !writer.busy
                            onClicked: { view.saveNow(); writer.generateTopic() } }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#E9EDE7" }
                    ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; visible: !view.reviewMode
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        TextArea { id: draftText; objectName: "writingDraftField"; width: Math.max(0, parent.width - 16)
                            wrapMode: TextEdit.Wrap; selectByMouse: true
                            placeholderText: "从这里开始写"
                             font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                             font.pixelSize: 19
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
                            onTextChanged: autosave.restart() }
                    }
                    ColumnLayout { Layout.fillWidth: true; Layout.fillHeight: true; visible: view.reviewMode; spacing: 9
                        Text { text: writer.current.title || "作文批改"; Layout.fillWidth: true; elide: Text.ElideRight
                            color: view.ink; font.pixelSize: 21; font.weight: Font.DemiBold }
                        Text { text: "点击下划线查看对应建议"; color: view.muted; font.pixelSize: 11 }
                        Flickable { id: essayFlick; Layout.fillWidth: true; Layout.fillHeight: true
                            contentWidth: width; contentHeight: paragraphColumn.height + 20; clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            Column { id: paragraphColumn; width: essayFlick.width - 16; spacing: 15
                                Repeater { id: paragraphRepeater; model: writer.reviewParagraphs
                                    delegate: Rectangle { required property var modelData
                                        width: paragraphColumn.width; height: paragraphText.implicitHeight + 12
                                        radius: 7; color: "transparent"
                                        Text { id: paragraphText; x: 6; y: 6; width: parent.width - 12
                                            text: view.reviewHtmlFor(modelData); textFormat: Text.RichText; wrapMode: Text.Wrap
                                             font.family: writer.current.language === "en" ? "Georgia" : "Yu Gothic UI"
                                             font.pixelSize: 18; lineHeight: 1.5
                                            color: view.ink; linkColor: view.themeAccent
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
                        AppButton { visible: view.reviewMode; text: "记笔记"; onClicked: notePopup.open() }
                        AppButton { visible: !view.reviewMode; text: "保存草稿"; onClicked: view.saveNow() }
                        AppButton { visible: !view.reviewMode; text: writer.busy ? "正在批改…" : "提交批改"; primary: true
                            enabled: !writer.busy && draftText.text.trim().length > 0
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
                        Flickable { id: issueFlick; Layout.fillWidth: true; Layout.fillHeight: true
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
                                            Text { width: parent.width; text: modelData.quote + " → " + modelData.correction
                                                wrapMode: Text.Wrap; color: view.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                                            Text { width: parent.width; text: modelData.reason; wrapMode: Text.Wrap
                                                color: "#607066"; font.pixelSize: 11 }
                                            Text { visible: !modelData.linked; text: "原文位置不唯一，保留为待核对建议"
                                                color: view.muted; font.pixelSize: 10 }
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: view.selectIssue(index) }
                                    }
                                }
                                Text { visible: writer.reviewIssues.length === 0; width: parent.width; wrapMode: Text.Wrap
                                    text: "本次没有可定位的具体问题，请查看全文建议。"; color: view.muted; font.pixelSize: 12 }
                            }
                        }
                        Flickable { Layout.fillWidth: true; Layout.fillHeight: true; visible: view.reviewTab === "overview"
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
                                Text { visible: !!(writer.current.review && writer.current.review.revisedText)
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: writer.current.review ? writer.current.review.revisedText || "" : ""
                                    color: "#536359"; font.pixelSize: 12; lineHeight: 1.4 }
                            }
                        }
                        AppButton { text: "记下修改心得"; Layout.fillWidth: true; onClicked: notePopup.open() }
                    }
                }
            }
        }
    }
}
