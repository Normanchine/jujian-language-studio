import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "writingNotesPage"
    signal back()
    signal newNote()
    signal editNote(var note)
    signal openDraft(string path)
    property string query: ""
    property string language: "all"
    property string essayPath: "all"
    property string selectedPath: ""
    property bool reviewing: false
    property bool revealed: false
    property var sources: [{title: "全部来源", path: "all"}, {title: "自由笔记 / 来源已删除", path: ""}].concat(writer.drafts)
    property var matches: writer.notes.filter(function(n) {
        return (page.language === "all" || n.language === page.language)
            && (page.essayPath === "all" || (n.essayPath || "") === page.essayPath)
            && ((n.sourceQuote || "") + " " + n.text + " " + (n.essayTitle || "")).toLowerCase().indexOf(page.query.trim().toLowerCase()) >= 0
    })
    property int selectedIndex: {
        for (var i = 0; i < matches.length; ++i) if (matches[i].path === selectedPath) return i
        return -1
    }
    property var currentNote: selectedIndex >= 0 ? matches[selectedIndex] : ({})
    onMatchesChanged: {
        if (!matches.some(function(n) { return n.path === page.selectedPath }))
            selectedPath = matches.length ? matches[0].path : ""
        revealed = false
    }
    onSelectedPathChanged: revealed = false
    function move(step) {
        var index = selectedIndex + step
        if (index >= 0 && index < matches.length) {
            selectedPath = matches[index].path
            noteList.positionViewAtIndex(index, ListView.Contain)
        }
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            AppButton { objectName: "writingNotesBack"; text: "← 写作主页"; onClicked: page.back() }
            Text { text: "写作笔记"; font.pixelSize: 21; font.weight: Font.DemiBold; color: "#26342C"; Layout.fillWidth: true }
            AppButton { objectName: "writingNotesReview"; text: page.reviewing ? "结束复习" : "开始复习"; primary: !page.reviewing
                enabled: page.matches.length > 0 || page.reviewing
                onClicked: { page.reviewing = !page.reviewing; page.revealed = false } }
            AppButton { text: "＋ 记一条"; onClicked: page.newNote() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            TextField { objectName: "writingNotesSearch"; Layout.fillWidth: true; Layout.preferredHeight: 36; font.pixelSize: 12
                placeholderText: "搜索摘录、心得或来源作文"; onTextChanged: page.query = text
                background: Rectangle { radius: 8; color: settings.palette.surface; border.color: "#DCE4DE" } }
            AppCombo { objectName: "writingNotesLanguage"; Layout.preferredWidth: 110; model: ["全部语言", "英语", "日语"]
                onActivated: page.language = ["all", "en", "ja"][currentIndex] }
            AppCombo { objectName: "writingNotesSource"; Layout.preferredWidth: Math.min(220, page.width * 0.29)
                model: page.sources.map(function(s) { return s.title })
                onActivated: page.essayPath = page.sources[currentIndex].path }
        }
        Text { text: page.matches.length + " 条笔记" + (page.reviewing ? " · 先回想表达与用法，再展开心得" : " · 按最近更新排序")
            color: "#78877D"; font.pixelSize: 12 }
        GridLayout {
            id: content
            Layout.fillWidth: true; Layout.fillHeight: true
            columns: page.width >= 800 ? 2 : 1; columnSpacing: 14; rowSpacing: 12
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.preferredWidth: 290; Layout.preferredHeight: content.columns === 1 ? 165 : -1
                Layout.maximumHeight: content.columns === 1 ? 165 : Infinity
                radius: 12; color: settings.palette.surface; border.color: "#E0E7E1"
                ListView {
                    id: noteList; objectName: "writingNotesList"
                    anchors.fill: parent; anchors.margins: 8; clip: true; spacing: 6
                    model: page.matches
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        required property var modelData
                        width: noteList.width; height: 99; radius: 8
                        color: page.selectedPath === modelData.path ? settings.palette.selection : settings.palette.page
                        border.color: page.selectedPath === modelData.path ? settings.palette.accent : "transparent"
                        Column {
                            anchors.fill: parent; anchors.margins: 11; spacing: 7
                            Text { width: parent.width; text: modelData.sourceQuote || modelData.text; textFormat: Text.PlainText
                                maximumLineCount: 2; elide: Text.ElideRight; wrapMode: Text.Wrap; font.pixelSize: 13; color: "#26342C" }
                            Text { width: parent.width; text: modelData.essayTitle || "自由笔记"; elide: Text.ElideRight; font.pixelSize: 11; color: "#78877D" }
                            Text { text: (modelData.language === "ja" ? "日语" : "英语") + " · " + String(modelData.updated).slice(0, 10); font.pixelSize: 10; color: "#89958B" }
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: page.selectedPath = parent.modelData.path }
                    }
                    Text { anchors.centerIn: parent; visible: page.matches.length === 0; text: "没有符合条件的笔记"; color: "#78877D"; font.pixelSize: 13 }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 600
                radius: 12; color: settings.palette.surface; border.color: "#E0E7E1"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 10
                    visible: page.selectedIndex >= 0
                    RowLayout {
                        Layout.fillWidth: true
                        Text { Layout.fillWidth: true; text: page.currentNote.essayTitle || "自由笔记"; elide: Text.ElideRight; color: "#78877D"; font.pixelSize: 12 }
                        AppButton { objectName: "writingNotesEdit"; text: "编辑"; flat: true; onClicked: page.editNote(page.currentNote) }
                        AppButton { visible: !!page.currentNote.essayPath; text: "原作文"; flat: true; onClicked: page.openDraft(page.currentNote.essayPath) }
                    }
                    ScrollView {
                        id: detailScroll
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        Column {
                            width: detailScroll.availableWidth; spacing: 16
                            Text { visible: !!page.currentNote.sourceQuote; text: "摘录 / 好句"; color: settings.palette.accent; font.pixelSize: 12 }
                            TextEdit { width: parent.width; visible: !!page.currentNote.sourceQuote
                                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                                text: page.currentNote.sourceQuote || ""; color: "#26342C"; font.pixelSize: 19
                                font.family: page.currentNote.language === "en" ? "Georgia" : "Yu Gothic UI" }
                            Text { text: "我的理解与用法"; color: settings.palette.accent; font.pixelSize: 12 }
                            TextEdit { objectName: "writingNotesDetail"; width: parent.width; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                                visible: !page.reviewing || page.revealed; text: page.currentNote.text || "尚未记录心得，可点击编辑补充。"; color: "#45584A"; font.pixelSize: 15 }
                            AppButton { objectName: "writingNotesReveal"; visible: page.reviewing && !page.revealed; text: "查看心得"; primary: true; onClicked: page.revealed = true }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton { objectName: "writingNotesPrev"; text: "上一条"; enabled: page.selectedIndex > 0; onClicked: page.move(-1) }
                        Text { text: (page.selectedIndex + 1) + " / " + page.matches.length; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: "#78877D"; font.pixelSize: 12 }
                        AppButton { objectName: "writingNotesNext"; text: "下一条"; enabled: page.selectedIndex + 1 < page.matches.length; onClicked: page.move(1) }
                    }
                }
                Text { anchors.centerIn: parent; visible: page.selectedIndex < 0; text: "选择一条笔记开始回看"; color: "#78877D"; font.pixelSize: 13 }
            }
        }
    }
}
