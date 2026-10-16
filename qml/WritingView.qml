import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    objectName: "writingView"
    property bool reviewMode: false
    property bool notebookOpen: false
    property bool libraryMode: false
    property bool favoritesOnly: false
    property string pendingDelete: ""
    property string pendingDeleteTitle: ""
    property string noteSourceQuote: ""
    property string loadedPath: ""
    property var selectedTargets: []
    property string materialFilter: "全部"
    property color ink: "#26342C"
    property color paper: "#FFFEFB"
    property color themeAccent: "#C94859"
    property bool showSide: false
    property int reviewElapsed: 0
    signal openNotes()
    Timer { interval: 1000; repeat: true; running: writer.busy
        onRunningChanged: if (running) view.reviewElapsed = 0
        onTriggered: view.reviewElapsed++ }

    function saveNow() {
        if (writer.currentPath && !reviewMode)
            writer.saveDraft(titleField.text, topicField.text, draftText.text)
    }
    function showLibrary() { saveNow(); libraryMode = true }
    function visibleDrafts() {
        var result = []
        for (var i = 0; i < writer.drafts.length; i++) {
            var item = writer.drafts[i]
            if (!favoritesOnly || item.favorite) result.push(item)
        }
        return result
    }
    Popup {
        id: deleteConfirm
        objectName: "essayDeleteConfirm"
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 398; height: 200; padding: 24
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#660F1C16" }
        background: Rectangle {
            radius: 14; color: "#FFFFFF"; border.color: "#E2E7E2"
        }
        contentItem: Column {
            spacing: 14
            Row { spacing: 11
                Rectangle { width: 34; height: 34; radius: 10; color: "#FCE9ED"
                    Text { anchors.centerIn: parent; text: "删"; color: "#B33E51"
                        font.family: "Microsoft YaHei UI"; font.pixelSize: 14; font.bold: true } }
                Text { text: "删除作文"; color: view.ink; font.pixelSize: 18
                    font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            }
            Text { width: parent.width; text: "即将删除「" + view.pendingDeleteTitle + "」"
                color: "#35443A"; font.pixelSize: 13; elide: Text.ElideRight }
            Text { width: parent.width; text: "删除后无法在应用中恢复。"
                color: "#77857A"; font.pixelSize: 12 }
            Row { spacing: 9; anchors.right: parent.right
                AppButton { text: "取消"; width: 82; onClicked: deleteConfirm.close() }
                AppButton { text: "删除作文"; width: 104; primary: true; destructive: true
                    onClicked: {
                        writer.deleteDraft(view.pendingDelete)
                        deleteConfirm.close()
                    } }
            }
        }
    }
    function filteredMaterials() {
        var result = []
        var language = writer.current.language || "ja"
        for (var i = 0; i < writer.favorites.length; i++) {
            var favorite = writer.favorites[i]
            if (favorite.language === language && (materialFilter === "全部" || materialFilter === "收藏"
                    || favorite.kind === materialFilter)) result.push(favorite)
        }
        if (materialFilter === "收藏") return result
        for (var j = 0; j < writer.materials.length; j++) {
            var item = writer.materials[j]
            if (materialFilter !== "全部" && item.kind !== materialFilter) continue
            if (!result.some(function(value) { return value.expression === item.expression })) result.push(item)
        }
        return result
    }
    Connections {
        target: writer
        function onChanged() {
            if (writer.currentPath && view.loadedPath !== writer.currentPath) {
                view.loadedPath = writer.currentPath
                titleField.text = writer.current.title || ""
                topicField.text = writer.current.topic || ""
                draftText.text = writer.current.text || ""
                view.selectedTargets = writer.current.targets || []
                view.reviewMode = false
            }
        }
        function onReviewReady() { view.reviewMode = true }
        function onTopicReady() { topicField.text = writer.current.topic || "" }
    }
    Timer { id: autosave; interval: 900; repeat: false; onTriggered: view.saveNow() }

    Column {
        anchors.fill: parent; spacing: 14
        RowLayout {
            width: parent.width; height: 58
            ColumnLayout { Layout.fillWidth: true; spacing: 2
                Text { text: reviewMode ? "作文批改" : "写作";
                    color: view.ink; font.pixelSize: 21; font.weight: Font.DemiBold }
            }
            Row { spacing: 8; Layout.preferredWidth: childrenRect.width
                Layout.preferredHeight: childrenRect.height; Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                AppButton { visible: !!writer.currentPath && !!writer.current.review
                    text: reviewMode ? "返回草稿" : "查看批改"
                    onClicked: { if (!reviewMode) view.saveNow(); reviewMode = !reviewMode } }
                AppButton { visible: view.width < 950 && !!writer.currentPath && !view.libraryMode
                    text: view.showSide ? "收起侧栏" : (view.reviewMode ? "写作建议" : "写作素材")
                    onClicked: view.showSide = !view.showSide }
                AppButton { visible: !!writer.currentPath && !view.libraryMode; text: "全部作文"
                    onClicked: view.showLibrary() }
                AppButton { text: "新建日语"; onClicked: { view.saveNow(); writer.newDraft("ja"); view.libraryMode = false } }
                AppButton { text: "新建英语"; onClicked: { view.saveNow(); writer.newDraft("en"); view.libraryMode = false } }
            }
        }
        Rectangle {
            visible: view.libraryMode || !writer.currentPath; width: parent.width; height: parent.height - 72
            radius: 10; color: "#FFFFFF"; border.color: "#DFE4E0"
            Column {
                anchors.fill: parent; anchors.margins: 20; spacing: 12
                RowLayout { width: parent.width
                    Text { text: "全部作文"; color: view.ink; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    AppButton { text: view.favoritesOnly ? "★ 只看收藏" : "☆ 只看收藏"
                        onClicked: view.favoritesOnly = !view.favoritesOnly }
                }
                ListView { id: essayList; width: parent.width; height: parent.height - 40
                    clip: true; spacing: 8
                    model: view.visibleDrafts()
                    delegate: Rectangle {
                        required property var modelData
                        width: essayList.width - 12; height: 75; radius: 9
                        color: draftHover.containsMouse ? "#F6F8F6" : "#FAFBFA"
                        border.color: "#E6EBE7"
                        Text { x: 14; y: 10; width: parent.width - 130; elide: Text.ElideRight
                            text: modelData.title; color: view.ink; font.pixelSize: 14; font.bold: true }
                        Text { x: 14; y: 36; width: parent.width - 130; elide: Text.ElideRight
                            text: (modelData.language === "en" ? "英语" : "日语") + " · " + modelData.updatedLabel + " · " + (modelData.preview || "空白草稿")
                            color: "#78857C"; font.pixelSize: 11 }
                        MouseArea { id: draftHover; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { writer.openDraft(modelData.path); view.libraryMode = false } }
                        AppButton { anchors.right: deleteButton.left; anchors.rightMargin: 6; y: 18; z: 2
                            text: modelData.favorite ? "★" : "☆"; flat: true
                            onClicked: writer.toggleDraftFavorite(modelData.path) }
                        AppButton { id: deleteButton; anchors.right: parent.right; anchors.rightMargin: 10; y: 18; z: 2
                            text: "删除"; flat: true
                            onClicked: {
                                view.pendingDelete = modelData.path
                                view.pendingDeleteTitle = modelData.title
                                deleteConfirm.open()
                            } }
                    }
                }
                Text { visible: essayList.count === 0; text: "这里还没有作文。"
                    color: "#839087"; font.pixelSize: 13 }
            }
        }
        Item {
            visible: !!writer.currentPath && !view.libraryMode; width: parent.width; height: parent.height - 72
            RowLayout {
                anchors.fill: parent; spacing: 14
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: 16
                    color: view.paper; border.color: "#E8E5DC"
                    Column {
                        anchors.fill: parent; anchors.margins: 24; spacing: 13
                        RowLayout {
                            width: parent.width; height: 44; visible: !view.reviewMode
                            TextField { id: titleField; Layout.fillWidth: true; placeholderText: "作文标题"
                                font.pixelSize: 23; font.bold: true; color: view.ink
                                background: Rectangle { color: "transparent" }
                                onTextChanged: autosave.restart() }
                            Rectangle { width: 54; height: 26; radius: 13; color: "#F0F3EE"
                                Text { anchors.centerIn: parent; text: writer.current.language === "en" ? "英语" : "日语"
                                    color: "#66796B"; font.pixelSize: 11; font.weight: Font.DemiBold } }
                        }
                         RowLayout { width: parent.width; height: 38; visible: !view.reviewMode; spacing: 8
                             AppCombo { id: writingMode; Layout.preferredWidth: 137; height: 33
                                 visible: writer.current.language === "en"
                                 model: ["自由写作", "托福邮件练习", "托福学术讨论"]
                                 currentIndex: ({practice:0, toefl_email:1, toefl_discussion:2})[writer.current.writing_mode || "practice"] || 0
                                 onActivated: writer.setMode(["practice", "toefl_email", "toefl_discussion"][currentIndex]) }
                             TextField { id: topicField; Layout.fillWidth: true; height: 36
                                 placeholderText: "写作题目（可留空）"
                                 font.pixelSize: 12; leftPadding: 12; color: view.ink
                                 background: Rectangle { radius: 9; color: "#F8F8F4"; border.color: "#E7EAE3" }
                                 onTextChanged: autosave.restart() }
                             AppButton { text: "AI 出题"; enabled: !writer.busy
                                 onClicked: { view.saveNow(); writer.generateTopic() } }
                         }
                        Text { visible: view.reviewMode; text: writer.current.title || "作文批改"
                            color: view.ink; font.pixelSize: 23; font.weight: Font.DemiBold }
                        Rectangle { width: parent.width; height: 1; color: "#ECEDE6" }
                        Item {
                            width: parent.width
                            height: parent.height - (view.reviewMode ? 133 : 171)
                            ScrollView {
                                anchors.fill: parent; visible: !view.reviewMode
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                                TextArea { id: draftText; width: Math.max(0, parent.width - 18); wrapMode: TextEdit.Wrap
                                    placeholderText: "在这里输入作文正文。"
                                    font.family: writer.current.language === "en" ? "Segoe UI" : "Yu Gothic UI"
                                    font.pixelSize: 17; color: view.ink; selectByMouse: true
                                    leftPadding: 10; rightPadding: 10; topPadding: 16; bottomPadding: 20
                                    background: Rectangle { color: view.paper }
                                    onTextChanged: autosave.restart() }
                            }
                            ScrollView {
                                anchors.fill: parent; visible: view.reviewMode && writer.current.language === "en"
                                TextArea { text: writer.current.review ? writer.current.review.text : ""
                                    readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                                    font.family: "Segoe UI"; font.pixelSize: 17; color: view.ink
                                    leftPadding: 10; rightPadding: 16; topPadding: 16
                                    background: Rectangle { color: view.paper } }
                            }
                            ScrollView { anchors.fill: parent
                                visible: view.reviewMode && writer.current.language === "ja"
                                TextArea { text: writer.current.review ? writer.current.review.text : ""
                                    readOnly: true; wrapMode: TextEdit.Wrap; selectByMouse: true
                                    font.family: "Yu Gothic UI"; font.pixelSize: 16
                                    background: Rectangle { color: "#FCFDFC" } }
                            }
                        }
                        Rectangle { width: parent.width; height: 1; color: "#ECEDE6" }
                        RowLayout { width: parent.width; height: 38
                            Text { Layout.fillWidth: true
                                text: writer.busy ? writer.status + "  " + view.reviewElapsed + " 秒"
                                      : writer.status || (view.reviewMode ? "批改稿为只读快照；原稿仍在草稿中。" : "自动保存  ·  " + (writer.current.language === "ja" ? draftText.text.trim().length + " 字" : (draftText.text.trim() ? draftText.text.trim().split(/\s+/).length : 0) + " 词"))
                                color: "#748178"; font.pixelSize: 12; elide: Text.ElideRight }
                            AppButton { visible: !view.reviewMode; text: "保存"; onClicked: view.saveNow() }
                            AppButton { visible: !view.reviewMode; text: writer.busy ? "正在分析全文…" : "开始批改"; primary: true
                                enabled: !writer.busy && draftText.text.trim().length > 0
                                onClicked: { view.reviewElapsed = 0; view.saveNow(); writer.review() } }
                        }
                    }
                }
                Rectangle {
                    visible: view.reviewMode || view.width >= 950 || view.showSide
                    Layout.preferredWidth: Math.min(390, Math.max(300, view.width * 0.39))
                    Layout.fillHeight: true; radius: 16; color: "#F9FAF7"; border.color: "#E6EAE3"
                    Column {
                        anchors.fill: parent; anchors.margins: 17; spacing: 12
                        Text { text: view.reviewMode ? "AI 批改指导" : "灵感与素材"; color: view.ink
                            font.pixelSize: 17; font.weight: Font.DemiBold }
                        Text { visible: !view.reviewMode; text: "挑选想练的表达，写进自己的句子里"
                            color: "#87938A"; font.pixelSize: 11; wrapMode: Text.Wrap; width: parent.width }
                        Row { visible: !view.reviewMode; spacing: 6
                            AppCombo { id: levelChoice; width: 128; height: 31
                                model: writer.current.language === "en" ? ["托福风格", "通用英语"] : ["N2 及以下", "N3 及以下", "N4 及以下"] }
                            AppButton { text: "换一组"; enabled: !writer.busy
                                onClicked: { view.saveNow(); writer.generateMaterials(levelChoice.currentText) } }
                        }
                         AppCombo { visible: !view.reviewMode; width: parent.width; height: 31
                             model: ["全部", "收藏", "语法", "词汇"]
                             onActivated: view.materialFilter = ["全部", "收藏", "grammar", "vocabulary"][currentIndex] }
                         RowLayout { visible: !view.reviewMode; width: parent.width; spacing: 5
                             AppCombo { id: customKind; Layout.preferredWidth: 78; height: 34
                                 model: ["词汇", "语法"] }
                             TextField { id: manualTarget; Layout.fillWidth: true; height: 34
                                 placeholderText: "多个词用逗号分隔"; font.pixelSize: 12
                                 background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: manualTarget.activeFocus ? view.themeAccent : "#DCE4DE" } }
                             AppButton { text: customKind.currentIndex === 0 ? "生成卡片" : "加入卡片"
                                 enabled: manualTarget.text.trim().length > 0 && !writer.busy
                                 onClicked: {
                                     writer.addCustomMaterials(manualTarget.text, customKind.currentIndex === 0 ? "vocabulary" : "grammar")
                                     manualTarget.clear()
                                 } }
                         }
                        Text { visible: !view.reviewMode && view.selectedTargets.length > 0
                            width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11; color: "#B43E51"
                            text: "本次目标：" + view.selectedTargets.join("、") }
                        ScrollView {
                            id: materialsScroll
                             width: parent.width; height: Math.max(80, parent.height - (view.reviewMode ? 70 : 231))
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            Column {
                                width: Math.max(0, materialsScroll.width - 14); spacing: 8
                                Text { visible: !view.reviewMode && writer.materials.length === 0
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: "选择难度并生成一组语法、词汇；从中挑选想用的表达。"
                                    color: "#87938A"; font.pixelSize: 12 }
                                Repeater {
                                     model: view.reviewMode ? [] : view.filteredMaterials()
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: parent.width; height: itemColumn.height + 18; radius: 7
                                        color: view.selectedTargets.indexOf(modelData.expression) >= 0 ? settings.palette.selection : "#F8FAF8"
                                        border.color: view.selectedTargets.indexOf(modelData.expression) >= 0 ? view.themeAccent : "#E7EBE7"
                                        Column { id: itemColumn; x: 9; y: 9; width: parent.width - 18; spacing: 4
                                            Text { width: parent.width; text: modelData.expression
                                                wrapMode: Text.Wrap; color: view.ink; font.pixelSize: 13; font.bold: true }
                                            Text { width: parent.width; text: modelData.meaning
                                                wrapMode: Text.Wrap; color: "#66746A"; font.pixelSize: 11 }
                                            Text { width: parent.width; text: modelData.example
                                                wrapMode: Text.Wrap; color: "#839087"; font.pixelSize: 11 }
                                        }
                                         Text { anchors.right: parent.right; anchors.rightMargin: 8; y: 5
                                             text: writer.favorites.some(function(value) { return value.expression === modelData.expression
                                                 && value.language === writer.current.language }) ? "★" : "☆"
                                             color: "#C68B35"; font.pixelSize: 18 }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var selected = view.selectedTargets.slice()
                                                var at = selected.indexOf(modelData.expression)
                                                if (at >= 0) selected.splice(at, 1)
                                                else selected.push(modelData.expression)
                                                view.selectedTargets = selected
                                                writer.setTargets(JSON.stringify(selected))
                                            } }
                                         MouseArea { x: parent.width - 34; y: 0; width: 34; height: 35; z: 2
                                             cursorShape: Qt.PointingHandCursor
                                             onClicked: writer.toggleFavorite(modelData.expression) }
                                    }
                                }
                                Text { visible: view.reviewMode; text: "整体点评"
                                    color: view.ink; font.pixelSize: 14; font.bold: true }
                                Text { visible: view.reviewMode; width: parent.width; wrapMode: Text.Wrap
                                    text: writer.current.review ? writer.current.review.overall : ""
                                    color: "#4A594E"; font.pixelSize: 12; lineHeight: 1.3 }
                                Text { visible: view.reviewMode && !!(writer.current.review && writer.current.review.context)
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: "全文语境：" + (writer.current.review ? writer.current.review.context : "")
                                    color: "#53685B"; font.pixelSize: 12; lineHeight: 1.3 }
                                Text { visible: view.reviewMode && writer.current.review
                                                && (writer.current.review.strengths || []).length > 0
                                    text: "写得好的地方"; color: view.ink; font.pixelSize: 14; font.bold: true }
                                Repeater { model: view.reviewMode && writer.current.review
                                                   ? writer.current.review.strengths || [] : []
                                    delegate: Text { required property var modelData; width: parent.width
                                        wrapMode: Text.Wrap; text: "• " + modelData
                                        color: "#53685B"; font.pixelSize: 12 } }
                                Text { visible: view.reviewMode && writer.current.review
                                                && (writer.current.review.priorities || []).length > 0
                                    text: "先改这些"; color: view.ink; font.pixelSize: 14; font.bold: true }
                                Repeater { model: view.reviewMode && writer.current.review
                                                   ? writer.current.review.priorities || [] : []
                                    delegate: Text { required property var modelData; width: parent.width
                                        wrapMode: Text.Wrap; text: "• " + modelData
                                        color: "#775047"; font.pixelSize: 12 } }
                                Text { visible: view.reviewMode && writer.current.review
                                                && writer.current.review.language === "en"
                                    text: "具体错误与修改建议"; color: view.ink; font.pixelSize: 14; font.bold: true }
                                Repeater {
                                    model: view.reviewMode && writer.current.review
                                           && writer.current.review.language === "en"
                                           ? (writer.current.review.issues || writer.current.review.marks || []) : []
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: parent.width; height: issueColumn.implicitHeight + 20
                                        radius: 8; color: "#FFF7F8"; border.color: "#F0DCE1"
                                        Column { id: issueColumn; x: 10; y: 10; width: parent.width - 20; spacing: 5
                                            Text { width: parent.width; wrapMode: Text.Wrap
                                                text: (modelData.category || "具体问题")
                                                      + (modelData.repeats > 1 ? " · 原文中有 " + modelData.repeats + " 处" : "")
                                                color: "#B44255"; font.pixelSize: 11; font.bold: true }
                                            Text { width: parent.width; wrapMode: Text.Wrap
                                                text: modelData.quote + " → " + (modelData.correction || "删除")
                                                color: "#3E4B41"; font.pixelSize: 12; font.bold: true }
                                            Text { width: parent.width; wrapMode: Text.Wrap
                                                text: modelData.reason; color: "#685A5D"; font.pixelSize: 12 }
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                view.notebookOpen = true
                                                view.noteSourceQuote = modelData.quote
                                                noteText.text = "原文：" + modelData.quote + "\n建议：" + modelData.correction
                                                                + "\n我的笔记："
                                            } }
                                    }
                                }
                                Text { visible: view.reviewMode && !!(writer.current.review && writer.current.review.revisedText)
                                    text: "参考改写"; color: view.ink; font.pixelSize: 14; font.bold: true }
                                Text { visible: view.reviewMode && !!(writer.current.review && writer.current.review.revisedText)
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: writer.current.review ? writer.current.review.revisedText : ""
                                    color: "#344A3B"; font.family: "Segoe UI"; font.pixelSize: 13; lineHeight: 1.3 }
                                Text { visible: view.reviewMode && !!(writer.current.review && writer.current.review.targetFeedback)
                                    width: parent.width; wrapMode: Text.Wrap
                                    text: "目标表达：" + (writer.current.review ? writer.current.review.targetFeedback : "")
                                    color: "#66746A"; font.pixelSize: 12 }
                                Repeater {
                                    model: view.reviewMode && writer.current.review && writer.current.review.language === "ja"
                                           ? writer.current.review.advice || [] : []
                                    delegate: Rectangle { required property var modelData
                                        width: parent.width; height: adviceText.implicitHeight + 18
                                        radius: 7; color: "#FFF7F8"; border.color: "#F0DCE1"
                                        Text { id: adviceText; x: 9; y: 9; width: parent.width - 18
                                            wrapMode: Text.Wrap; font.pixelSize: 12; color: "#5E4047"
                                            text: modelData.quote + " → " + modelData.suggestion + "\n" + modelData.reason }
                                    }
                                }
                                Repeater { model: view.reviewMode && writer.current.review ? writer.current.review.unanchored || [] : []
                                    delegate: Text { required property var modelData; width: parent.width
                                        wrapMode: Text.Wrap; text: modelData; color: "#6B585C"; font.pixelSize: 12 } }
                            }
                        }
                    }
                }
            }
            Rectangle {
                visible: view.reviewMode
                width: view.notebookOpen ? Math.min(310, parent.width * 0.36) : 100
                height: view.notebookOpen ? 265 : 36
                x: parent.width - width - 18; y: parent.height - height - 16
                radius: 9; color: "#FFFFFF"; border.color: "#DCE4DE"; z: 5
                Behavior on width { NumberAnimation { duration: 140 } }
                Behavior on height { NumberAnimation { duration: 140 } }
                Column { anchors.fill: parent; anchors.margins: view.notebookOpen ? 12 : 0; spacing: 8
                    Rectangle { width: parent.width; height: 36; radius: 8; color: "#F8FAF8"
                        Text { anchors.centerIn: parent; text: view.notebookOpen ? "笔记本  ·  收起" : "记笔记"
                            color: "#33433A"; font.pixelSize: 12; font.bold: true }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: view.notebookOpen = !view.notebookOpen }
                    }
                    TextArea { id: noteText; visible: view.notebookOpen
                        width: parent.width; height: 156; wrapMode: TextEdit.Wrap
                        placeholderText: "记下这次发现的错误…"
                        background: Rectangle { color: "#FAFBFA"; border.color: "#DCE4DE"; radius: 6 } }
                    Row { visible: view.notebookOpen; spacing: 7
                        AppButton { text: "保存笔记"; enabled: noteText.text.trim().length > 0
                             onClicked: { writer.addNote(noteText.text, view.noteSourceQuote); noteText.clear(); view.noteSourceQuote = "" } }
                        AppButton { text: "全部笔记"; onClicked: view.openNotes() }
                    }
                }
            }
        }
    }
}
