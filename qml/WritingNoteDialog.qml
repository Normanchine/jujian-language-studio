import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dialog
    objectName: "writingNoteDialog"
    property string notePath: ""
    property string essayPath: ""
    property string language: "en"
    property var draftOptions: [{title: "不关联作文", path: ""}].concat(writer.drafts)
    function newNote(path, lang, quote) {
        notePath = ""; essayPath = path; language = lang || "en"
        quoteField.text = quote || ""; bodyField.text = ""; open()
    }
    function editNote(note) {
        notePath = note.path; essayPath = note.essayPath || ""; language = note.language || "en"
        quoteField.text = note.sourceQuote || ""; bodyField.text = note.text || ""; open()
    }
    modal: true; focus: true; anchors.centerIn: Overlay.overlay
    width: Math.min(580, parent.width - 32); height: Math.min(570, parent.height - 32); padding: 22
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { radius: 14; color: settings.palette.surface; border.color: "#DCE4DE" }
    Overlay.modal: Rectangle { color: "#650F1C16" }
    ColumnLayout {
        anchors.fill: parent; spacing: 11
        Text { text: dialog.notePath ? "好句与写作笔记" : "记下好句与发现"; color: "#26342C"; font.pixelSize: 20; font.weight: Font.DemiBold }
        RowLayout { Layout.fillWidth: true
            AppCombo { Layout.fillWidth: true; model: dialog.draftOptions.map(function(d) { return d.title })
                currentIndex: { for (var i = 0; i < dialog.draftOptions.length; i++) if (dialog.draftOptions[i].path === dialog.essayPath) return i; return 0 }
                onActivated: { dialog.essayPath = dialog.draftOptions[currentIndex].path
                    if (dialog.draftOptions[currentIndex].language) dialog.language = dialog.draftOptions[currentIndex].language } }
            AppCombo { Layout.preferredWidth: 90; model: ["英语", "日语"]; currentIndex: dialog.language === "ja" ? 1 : 0
                onActivated: dialog.language = currentIndex === 1 ? "ja" : "en" }
        }
        Text { text: "摘录 / 好句"; color: "#718077"; font.pixelSize: 12 }
        ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 120; clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            TextArea { id: quoteField; objectName: "writingNoteQuote"; width: parent.width
                wrapMode: TextEdit.Wrap; selectByMouse: true; font.pixelSize: 15
                font.family: dialog.language === "en" ? "Georgia" : "Yu Gothic UI"
                placeholderText: "粘贴一句值得学习的表达（可选）"
                background: Rectangle { radius: 8; color: settings.palette.page; border.color: "#DCE4DE" } }
        }
        Text { text: "我的理解与用法"; color: "#718077"; font.pixelSize: 12 }
        ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            TextArea { id: bodyField; objectName: "writingNoteBody"; width: parent.width
                wrapMode: TextEdit.Wrap; selectByMouse: true; font.pixelSize: 14
                placeholderText: "哪里写得好？可以用在什么地方？也可以记录这次修改的发现。"
                background: Rectangle { radius: 8; color: settings.palette.page; border.color: "#DCE4DE" } }
        }
        RowLayout { Layout.fillWidth: true
            AppButton { visible: !!dialog.essayPath; text: "打开原作文"; flat: true
                onClicked: { dialog.close(); dialog.openEssay(dialog.essayPath) } }
            Item { Layout.fillWidth: true }
            AppButton { text: "取消"; onClicked: dialog.close() }
            AppButton { objectName: "writingNoteSave"; text: "保存笔记"; primary: true
                enabled: quoteField.text.trim().length > 0 || bodyField.text.trim().length > 0
                onClicked: if (writer.saveWritingNote(dialog.notePath, bodyField.text, quoteField.text, dialog.essayPath, dialog.language)) dialog.close() }
        }
    }
    signal openEssay(string path)
}
