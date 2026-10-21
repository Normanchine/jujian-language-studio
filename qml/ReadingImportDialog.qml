import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Popup {
    id: dialog
    objectName: "readingImportDialog"
    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    width: Math.min(900, parent.width - 32)
    height: Math.min(740, parent.height - 32)
    padding: width < 600 ? 16 : 24
    property string filename: ""
    property int tab: 0
    property var importer: reading.importer
    property color ink: "#293B32"
    signal articleImported(string articleId, bool openNow)
    function invalidate() { importer.invalidate(); tab = 0; }
    function prepare() {
        if (importer.prepare(source.text, titleInput.text, ["auto", "en", "ja"][languageInput.currentIndex],
                             folderInput.text, markdownInput.checked, filename)) tab = 1;
    }
    function save(openNow) {
        var articleId = importer.save();
        if (articleId) {
            articleImported(articleId, openNow);
            source.clear(); titleInput.clear(); filename = "";
            close();
        }
    }
    onClosed: importer.cancelAI()
    background: Rectangle { radius: 14; color: settings.palette.surface; border.color: "#DFE7E1" }
    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { text: "导入精读文章"; color: dialog.ink; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true }
            AppButton { text: "关闭"; flat: true; onClicked: dialog.close() }
        }
        Text { text: "粘贴正文，或选择 TXT / Markdown 文件。原文会随文章一起保留。"; color: "#7B8981"; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            TextField { id: titleInput; objectName: "readingImportTitle"; placeholderText: "文章标题"; Layout.fillWidth: true; Layout.minimumWidth: 40; selectByMouse: true; maximumLength: 300; onTextChanged: dialog.invalidate() }
            ComboBox { id: languageInput; objectName: "readingImportLanguage"; model: ["自动识别", "英语", "日语"]; Layout.preferredWidth: 112; onCurrentIndexChanged: dialog.invalidate() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Text { text: "目录"; color: "#7B8981"; font.pixelSize: 12 }
            TextField { id: folderInput; objectName: "readingImportFolder"; text: "未分类"; placeholderText: "我的文章 / 文件夹名称"; Layout.fillWidth: true; Layout.minimumWidth: 40; selectByMouse: true; maximumLength: 100; onTextChanged: dialog.invalidate() }
            AppButton { objectName: "readingImportFile"; text: "选择文件"; onClicked: filePicker.open() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            AppButton { text: "原始正文"; flat: dialog.tab !== 0; onClicked: dialog.tab = 0 }
            AppButton { text: "排版预览"; flat: dialog.tab !== 1; enabled: dialog.importer.view.prepared; onClicked: dialog.tab = 1 }
            Item { Layout.fillWidth: true }
            CheckBox { id: markdownInput; text: "Markdown"; onCheckedChanged: dialog.invalidate() }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 100
            color: settings.palette.page; radius: 8; border.color: "#DFE7E1"
            ScrollView {
                id: sourceScroll; anchors.fill: parent; anchors.margins: 10; visible: dialog.tab === 0; clip: true
                TextArea {
                    id: source; objectName: "readingImportSource"
                    implicitWidth: 0; width: sourceScroll.availableWidth
                    placeholderText: "在这里粘贴文章正文…"; textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap; selectByMouse: true; color: dialog.ink
                    font.pixelSize: 15; background: null
                    onTextChanged: dialog.invalidate()
                }
            }
            ScrollView {
                id: previewScroll; anchors.fill: parent; anchors.margins: 10; visible: dialog.tab === 1; clip: true
                TextArea {
                    objectName: "readingImportPreview"
                    implicitWidth: 0; width: previewScroll.availableWidth
                    text: dialog.importer.view.text; textFormat: TextEdit.PlainText
                    readOnly: true; wrapMode: TextEdit.Wrap; selectByMouse: true
                    color: dialog.ink; font.pixelSize: 15; background: null
                }
            }
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12
            color: dialog.importer.view.error ? "#B44A4A" : "#7B8981"
            text: dialog.importer.view.error || dialog.importer.view.message || "先预览排版，再确认导入。AI整理为可选项，使用设置中的解析模型。"
        }
        Flow {
            Layout.fillWidth: true; spacing: 8
            AppButton { objectName: "readingImportPrepare"; text: "预览排版"; onClicked: dialog.prepare() }
            AppButton { objectName: "readingImportAI"; text: dialog.importer.view.busy ? "停止等待" : "AI整理段落"
                enabled: dialog.importer.view.prepared
                onClicked: { if (dialog.importer.view.busy) dialog.importer.cancelAI(); else { dialog.tab = 1; dialog.importer.formatAI(); } }
            }
            AppButton { objectName: "readingImportSave"; text: "仅导入"; enabled: dialog.importer.view.prepared && !dialog.importer.view.busy; onClicked: dialog.save(false) }
            AppButton { objectName: "readingImportRead"; text: "导入并精读"; primary: true; enabled: dialog.importer.view.prepared && !dialog.importer.view.busy; onClicked: dialog.save(true) }
        }
    }
    FileDialog {
        id: filePicker
        title: "选择精读文章"
        nameFilters: ["文章 (*.txt *.md *.markdown)"]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var result = dialog.importer.loadFile(selectedFile.toString());
            if (!result.ok) return;
            source.text = result.raw; titleInput.text = result.title;
            markdownInput.checked = result.markdown;
            dialog.filename = result.filename; dialog.tab = 0;
        }
    }
}
