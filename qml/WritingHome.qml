import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: home
    objectName: "writingHome"
    signal startDraft(string language, string mode)
    signal pickTask()
    signal openDraft(string path)
    signal deleteDraft(string path, string title)
    signal newNote()
    signal editNote(var note)
    signal allNotes()
    property string query: ""
    property string noteQuery: ""
    property string status: "all"
    property bool favoriteMode: false
    property bool wide: width >= 850 && height >= 540
    property int activeTab: 0
    property int page: 0
    property int pageSize: Math.max(1, Math.floor((draftViewport.height + 8) / 88))
    property int noteCount: Math.max(1, Math.ceil((noteViewport.height + 10) / 122))
    property int favoriteCount: Math.max(1, Math.ceil((favoriteViewport.height + 8) / 80))
    property var matches: filteredDrafts()
    property var matchingNotes: writer.notes.filter(function(n) {
        return (n.text + " " + (n.sourceQuote || "") + " " + (n.essayTitle || "")).toLowerCase().indexOf(home.noteQuery.trim().toLowerCase()) >= 0
    })
    property var favoriteDrafts: writer.drafts.filter(function(d) { return d.favorite })
    onQueryChanged: page = 0
    onStatusChanged: page = 0
    onFavoriteModeChanged: page = 0
    onPageSizeChanged: page = Math.min(page, Math.max(0, Math.ceil(matches.length / pageSize) - 1))
    onMatchesChanged: page = Math.min(page, Math.max(0, Math.ceil(matches.length / pageSize) - 1))
    function filteredDrafts() {
        return writer.drafts.filter(function(d) {
            return (!home.favoriteMode || d.favorite)
                && (home.status === "all" || (home.status === "reviewed" ? d.reviewed : !d.reviewed))
                && (d.title + " " + d.preview).toLowerCase().indexOf(home.query.trim().toLowerCase()) >= 0
        })
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        Rectangle {
            Layout.fillWidth: true; implicitHeight: practice.implicitHeight + 28; radius: 14
            color: settings.palette.surface; border.color: "#E3E8E2"
            Column {
                id: practice
                x: 18; y: 14; width: parent.width - 36; spacing: 10
                Text { text: "开始新的练习"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#26342C" }
                Flow { width: parent.width; spacing: 9
                    AppButton { text: "日语表达练习"; onClicked: home.startDraft("ja", "practice") }
                    AppButton { text: "英语自由写作"; onClicked: home.startDraft("en", "practice") }
                    AppButton { objectName: "writingTaskEntry"; text: "托福专项"; primary: true; onClicked: home.pickTask() }
                    AppButton { text: "托福邮件"; onClicked: home.startDraft("en", "toefl_email") }
                    AppButton { text: "托福学术讨论"; onClicked: home.startDraft("en", "toefl_discussion") }
                }
            }
        }
        RowLayout {
            visible: !home.wide; Layout.fillWidth: true; Layout.preferredHeight: 36; spacing: 8
            Repeater { model: ["我的作文", "我的收藏", "写作笔记"]
                AppButton { required property string modelData; required property int index
                    objectName: "writingHomeTab" + index; text: modelData; primary: home.activeTab === index; Layout.fillWidth: true
                    onClicked: home.activeTab = index }
            }
        }
        GridLayout {
            id: panels
            Layout.fillWidth: true; Layout.fillHeight: true
            columns: home.wide ? 2 : 1; columnSpacing: 16
            Rectangle {
                id: essayPanel; objectName: "writingDraftPanel"
                visible: home.wide || home.activeTab === 0
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: panels.width * 0.62
                radius: 14; color: settings.palette.surface; border.color: "#E3E8E2"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 10
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 28
                        Text { text: home.favoriteMode ? "收藏的作文" : "我的作文"; color: "#26342C"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Text { text: home.matches.length + " 篇"; color: "#78877D"; font.pixelSize: 12 }
                        AppButton { visible: home.favoriteMode; text: "全部作文"; flat: true; onClicked: home.favoriteMode = false }
                    }
                    RowLayout { Layout.fillWidth: true; spacing: 8
                        TextField { Layout.fillWidth: true; Layout.preferredHeight: 35; placeholderText: "搜索标题或正文"; font.pixelSize: 12
                            onTextChanged: home.query = text
                            background: Rectangle { radius: 7; color: settings.palette.page; border.color: "#DCE4DE" } }
                        AppCombo { Layout.preferredWidth: 100; model: ["全部", "待批改", "已批改"]
                            onActivated: home.status = ["all", "draft", "reviewed"][currentIndex] }
                    }
                    Item {
                        id: draftViewport; objectName: "writingDraftViewport"
                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
                        Column {
                            id: draftCards; objectName: "writingHomeDraftCards"; width: parent.width; spacing: 8
                            // Keep the next card mounted so resizing reveals it continuously.
                            Repeater { model: home.matches.slice(home.page * home.pageSize, (home.page + 1) * home.pageSize + 1)
                                WritingDraftCard { required property var modelData; entry: modelData; width: draftCards.width
                                    objectName: "homeDraft_" + modelData.path
                                    onOpened: function(path) { home.openDraft(path) }
                                    onRemoved: function(path, title) { home.deleteDraft(path, title) } }
                            }
                        }
                        Text { visible: home.matches.length === 0; width: parent.width; wrapMode: Text.Wrap
                            text: writer.drafts.length ? "没有符合条件的作文。" : "从上面选择一种练习，开始第一篇作文。"; color: "#78877D"; font.pixelSize: 13 }
                    }
                    RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 36
                        AppButton { objectName: "writingDraftPrev"; text: "上一页"; enabled: home.page > 0; onClicked: home.page-- }
                        Text { text: (home.page + 1) + " / " + Math.max(1, Math.ceil(home.matches.length / home.pageSize)); color: "#78877D"; font.pixelSize: 12; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                        AppButton { objectName: "writingDraftNext"; text: "下一页"; enabled: (home.page + 1) * home.pageSize < home.matches.length; onClicked: home.page++ }
                    }
                }
            }
            ColumnLayout {
                visible: home.wide || home.activeTab !== 0
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: panels.width * 0.38; spacing: 12
                Rectangle {
                    id: favoritesPanel; objectName: "writingFavoritesPanel"
                    visible: home.wide || home.activeTab === 1
                    Layout.fillWidth: true; Layout.fillHeight: !home.wide
                    Layout.preferredHeight: home.wide ? Math.max(130, Math.min(240, panels.height * 0.30)) : -1
                    radius: 14; color: settings.palette.surface; border.color: "#E3E8E2"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 16; spacing: 8
                        RowLayout { Layout.fillWidth: true
                            Text { text: "我的收藏"; color: "#26342C"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                            AppButton { objectName: "writingShowFavorites"; text: "查看全部"; flat: true
                                onClicked: { home.favoriteMode = true; home.activeTab = 0 } }
                        }
                        Item {
                            id: favoriteViewport; objectName: "writingFavoriteViewport"
                            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
                            Column { id: favoriteCards; width: parent.width; spacing: 8
                                Repeater { model: home.favoriteDrafts.slice(0, home.favoriteCount)
                                    WritingDraftCard { required property var modelData; entry: modelData; compact: true; width: favoriteCards.width
                                        onOpened: function(path) { home.openDraft(path) } }
                                }
                            }
                            Text { visible: home.favoriteDrafts.length === 0; width: parent.width; wrapMode: Text.Wrap
                                text: "点作文旁的 ☆，收藏想反复学习的文章。"; color: "#78877D"; font.pixelSize: 12; lineHeight: 1.4 }
                        }

                    }
                }
                Rectangle {
                    id: notesPanel; objectName: "writingHomeNotesPanel"
                    visible: home.wide || home.activeTab === 2
                    Layout.fillWidth: true; Layout.fillHeight: true
                    radius: 14; color: settings.palette.surface; border.color: "#E3E8E2"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 16; spacing: 10
                        RowLayout { Layout.fillWidth: true
                            Text { text: "写作笔记"; color: "#26342C"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                            AppButton { objectName: "writingNotesAll"; text: "全部 · " + writer.notes.length; flat: true; onClicked: home.allNotes() }
                            AppButton { objectName: "writingHomeNewNote"; text: "＋ 记一条"; flat: true; onClicked: home.newNote() }
                        }
                        TextField { Layout.fillWidth: true; Layout.preferredHeight: 34; placeholderText: "找好句、心得或来源作文"; font.pixelSize: 12
                            onTextChanged: home.noteQuery = text
                            background: Rectangle { radius: 7; color: settings.palette.page; border.color: "#DCE4DE" } }
                        Item {
                            id: noteViewport; objectName: "writingNoteViewport"
                            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
                        Column { id: noteCards; width: parent.width; spacing: 10
                            Repeater { model: home.matchingNotes.slice(0, home.noteCount)
                                Rectangle { required property var modelData
                                    width: noteCards.width; height: 112; radius: 9
                                    color: settings.palette.page; border.color: "#E3E9E3"
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: home.editNote(parent.modelData) }
                                    ColumnLayout { anchors.fill: parent; anchors.margins: 11; spacing: 6
                                        Text { visible: !!modelData.sourceQuote; Layout.fillWidth: true; text: modelData.sourceQuote; textFormat: Text.PlainText
                                            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            color: settings.palette.accent; font.family: modelData.language === "en" ? "Georgia" : "Yu Gothic UI"; font.pixelSize: 13 }
                                        Text { Layout.fillWidth: true; text: modelData.text; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 1; elide: Text.ElideRight; color: "#45584A"; font.pixelSize: 12 }
                                        Item { Layout.fillHeight: true }
                                        RowLayout { Layout.fillWidth: true
                                            Text { text: modelData.essayTitle || "自由笔记"; elide: Text.ElideRight; color: "#89958B"; font.pixelSize: 10; Layout.fillWidth: true }
                                            AppButton { visible: !!modelData.essayPath; text: "原作文"; flat: true; implicitHeight: 24; implicitWidth: 54
                                                onClicked: home.openDraft(modelData.essayPath) }
                                        }
                                    }
                                }
                            }
                        }
                        Text { visible: home.matchingNotes.length === 0; width: parent.width; wrapMode: Text.Wrap
                            text: home.noteQuery ? "没有找到这条笔记。" : "遇到好句就摘录，也可以记下批改后的发现。"; color: "#78877D"; font.pixelSize: 12 }
                        }
                        Text { visible: home.matchingNotes.length > 0; Layout.fillWidth: true; color: "#89958B"; font.pixelSize: 11
                            text: "最近笔记 · 进入全部笔记继续复习" }
                    }
                }
            }
        }
    }
}
