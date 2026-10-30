import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Popup {
    id: dialog
    objectName: "readingPaperImportDialog"
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1120, parent.width - 24)
    height: Math.min(880, parent.height - 24)
    padding: width < 940 ? 16 : 22
    modal: true; focus: true
    closePolicy: Popup.CloseOnEscape
    property var importer: reading.paperImporter
    property string libraryLanguage: "en"
    property string filename: ""
    property bool assigning: false
    property bool conversionSettings: false
    property bool revealAnswers: false
    property bool protectSource: true
    property int tab: 0
    property int narrowPreview: 1
    readonly property bool compact: width < 940
    readonly property string backend: modelRoute.currentIndex ? "cloud" : "local"
    readonly property string language: languageInput.currentIndex ? "ja" : "en"
    readonly property var state: importer.view
    readonly property var currentPaper: state.papers[paperSelector.currentIndex] || ({})
    property color ink: "#293B32"
    property color muted: "#7B8981"
    property color line: "#DDE6DF"
    signal paperImported(string paperId)

    function edited() {
        if (!assigning) { importer.invalidate(); confirmed.checked = false; tab = 0; }
    }
    function populate(raw, title, name) {
        assigning = true; source.text = raw; titleInput.text = title; filename = name; assigning = false;
        confirmed.checked = false; revealAnswers = false; protectSource = true; tab = 0;
    }
    function parse() {
        confirmed.checked = false;
        if (importer.parse(source.text, titleInput.text, language, filename)) tab = 1;
    }
    function organize() {
        confirmed.checked = false;
        importer.organize(source.text, titleInput.text, language, filename, backend);
    }
    function prepareAutomatically() {
        protectSource = true; revealAnswers = false; confirmed.checked = false;
        importer.prepareAutomatically(source.text, titleInput.text, language, filename, backend);
    }
    onOpened: {
        assigning = true;
        languageInput.currentIndex = libraryLanguage === "ja" ? 1 : 0;
        pythonInput.text = importer.preferences.python;
        deviceInput.currentIndex = Math.max(0, ["auto", "cpu", "cuda"].indexOf(importer.preferences.device));
        modelRoute.currentIndex = importer.preferences.backend === "cloud" ? 1 : 0;
        if (!source.text && state.raw) { source.text = state.raw; titleInput.text = state.title; filename = state.filename; }
        assigning = false;
    }
    onClosed: importer.cancel()
    Connections {
        target: dialog.importer
        function onSourceReady(raw, title, name) { dialog.populate(raw, title, name); dialog.prepareAutomatically() }
        function onChanged() {
            if (dialog.importer.view.busy) confirmed.checked = false;
            if (dialog.importer.view.parsed) dialog.tab = 1;
        }
    }
    background: Rectangle { radius: 15; color: settings.palette.surface; border.color: dialog.line }
    Overlay.modal: Rectangle { color: "#750F1C16" }

    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout { spacing: 4
                Text { text: "导入阅读题"; font.pixelSize: 23; font.weight: Font.DemiBold; color: dialog.ink }
                Text { text: "AI 整理好题目，答案留到交卷后再看"; color: dialog.muted; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "readingPaperImportClose"; text: "关闭"; flat: true; onClicked: dialog.close() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            TextField {
                id: titleInput; objectName: "readingPaperImportTitle"; Layout.fillWidth: true
                placeholderText: "试卷或书籍名称"; selectByMouse: true; maximumLength: 300; implicitHeight: 38
                color: dialog.ink; leftPadding: 12
                background: Rectangle { radius: 8; color: settings.palette.page; border.color: titleInput.activeFocus ? settings.palette.accent : dialog.line }
                onTextChanged: dialog.edited()
                ContextMenu.menu: AppTextMenu { editor: titleInput }
            }
            AppCombo { id: languageInput; objectName: "readingPaperImportLanguage"; model: ["英语", "日语"]; Layout.preferredWidth: 100; onCurrentIndexChanged: dialog.edited() }
            AppButton { objectName: "readingPaperImportFile"; text: "选择文件"; enabled: !dialog.state.busy
                onClicked: { if (dialog.importer.lastSourceFolder) filePicker.currentFolder=dialog.importer.lastSourceFolder; filePicker.open() } }
            AppButton { text: "转换设置"; flat: true; onClicked: dialog.conversionSettings = !dialog.conversionSettings }
        }
        Rectangle {
            visible: dialog.conversionSettings
            Layout.fillWidth: true; implicitHeight: conversionColumn.implicitHeight + 24
            radius: 9; color: settings.palette.page; border.color: dialog.line
            ColumnLayout { id: conversionColumn; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12; y: 12; spacing: 8
                Text { text: "PDF、Word、PPT、EPUB 和图片在本地转换；MD/TXT 直接读取。"; color: dialog.ink; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                RowLayout { Layout.fillWidth: true
                    Text { text: "MinerU Python"; color: dialog.muted; font.pixelSize: 12 }
                    TextField { id: pythonInput; objectName: "readingPaperMineruPython"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "已安装 MinerU 的 Python 路径"
                        ContextMenu.menu: AppTextMenu { editor: pythonInput } }
                }
                RowLayout { Layout.fillWidth: true
                    Text { text: "PDF 页码"; color: dialog.muted; font.pixelSize: 12; Layout.preferredWidth: 92 }
                    TextField { id: pagesInput; objectName: "readingPaperPages"; Layout.fillWidth: true; placeholderText: "全部，或 3-12（含首尾页）；答案在其他页时请一并包含"
                        ContextMenu.menu: AppTextMenu { editor: pagesInput } }
                    AppCombo { id: deviceInput; model: ["自动选择设备", "仅用 CPU", "使用 GPU"]; Layout.preferredWidth: 135 }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            AppButton { objectName: "readingPaperImportSourceTab"; text: "导入材料"; flat: dialog.tab !== 0; onClicked: dialog.tab = 0 }
            AppButton { objectName: "readingPaperImportPreviewTab"; text: "题目预览"; flat: dialog.tab !== 1; enabled: dialog.state.parsed; onClicked: dialog.tab = 1 }
            Item { Layout.fillWidth: true }
            Text { text: "整理模型"; color: dialog.muted; font.pixelSize: 12 }
            AppCombo { id: modelRoute; objectName: "readingPaperModelRoute"; model: ["本地 Ollama", "云端模型"]; Layout.preferredWidth: 140 }
        }
        Rectangle {
            visible: dialog.tab === 0; Layout.fillWidth: true; Layout.fillHeight: true
            radius: 10; color: settings.palette.page; border.color: dialog.line
            ScrollView { id: sourceScroll; visible: !dialog.protectSource; anchors.fill: parent; anchors.margins: 10; clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea { id: source; objectName: "readingPaperImportSource"; width: sourceScroll.availableWidth; implicitWidth: 0
                    wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText; selectByMouse: true; color: dialog.ink; font.pixelSize: 15
                    background: null; onTextChanged: dialog.edited()
                    ContextMenu.menu: AppTextMenu { editor: source }
                }
            }
            Text { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 24
                visible: !dialog.protectSource && !source.text; wrapMode: Text.Wrap; color: dialog.muted; font.pixelSize: 15
                text: "在此粘贴原始材料。原始材料可能包含答案；也可使用“从剪贴板整理”直接在后台处理。" }
            ColumnLayout { anchors.centerIn: parent; width: Math.min(520, parent.width-48); spacing: 16; visible: dialog.protectSource
                Text { text: dialog.state.busy ? "正在准备阅读题…" : "把试卷交给 AI 整理"; font.pixelSize: 22; color: dialog.ink; Layout.alignment: Qt.AlignHCenter }
                Text { text: "选择文件，或复制整份材料后点击下方按钮。\n文章、题目和答案会分开保存，导入过程不展示答案。"; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 14; color: dialog.muted }
                AppButton { text: "从剪贴板整理"; primary: true; Layout.alignment: Qt.AlignHCenter; enabled: !dialog.state.busy
                    onClicked: { var raw=dialog.importer.clipboardSource(); dialog.populate(raw,titleInput.text,""); dialog.prepareAutomatically() } }
                AppButton { text: "手动输入／编辑原始文本（可能含答案）"; flat: true; Layout.alignment: Qt.AlignHCenter; enabled: !dialog.state.busy; onClicked: dialog.protectSource = false }
            }
        }
        RowLayout {
            visible: dialog.tab === 1; Layout.fillWidth: true; spacing: 8
            AppCombo { id: paperSelector; objectName: "readingPaperSelector"; Layout.fillWidth: true; textRole: "title"; model: dialog.state.papers }
            Text { text: dialog.state.papers.length + " 篇 · " + dialog.state.selectedCount + " 题选中" + (dialog.state.missing ? " · " + dialog.state.missing + " 题缺答案" : ""); color: dialog.muted; font.pixelSize: 12 }
            AppButton { objectName: "readingPaperRevealAnswers"; text: dialog.revealAnswers ? "隐藏答案" : "显示答案核对"; flat: true; onClicked: dialog.revealAnswers = !dialog.revealAnswers }
            AppButton { visible: dialog.compact; text: dialog.narrowPreview ? "查看原文" : "查看题目"; flat: true; onClicked: dialog.narrowPreview = 1-dialog.narrowPreview }
        }
        RowLayout {
            visible: dialog.tab === 1; Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
            Rectangle {
                visible: !dialog.compact || !dialog.narrowPreview
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 40
                radius: 10; color: settings.palette.page; border.color: dialog.line
                ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 8
                    Text { text: "原文预览"; font.pixelSize: 12; color: dialog.muted }
                    ScrollView { id: passageScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        TextArea { objectName: "readingPaperImportPassage"; width: passageScroll.availableWidth; implicitWidth: 0
                            text: dialog.currentPaper.body || ""; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                            font.family: dialog.language === "en" ? "Georgia" : "Yu Gothic UI"; font.pixelSize: 16; color: dialog.ink; background: null }
                    }
                }
            }
            ListView {
                id: questionList; objectName: "readingPaperImportQuestions"
                visible: !dialog.compact || !!dialog.narrowPreview
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 60; clip: true; spacing: 10
                model: dialog.state.questions.filter(function(q) { return q.paperIndex === paperSelector.currentIndex })
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    id: card; required property var modelData
                    width: questionList.width - 10; implicitHeight: content.implicitHeight + 24
                    radius: 11; color: settings.palette.surface; border.color: modelData.included ? dialog.line : "#E9EEEA"
                    ColumnLayout { id: content; x: 12; y: 12; width: parent.width - 24; spacing: 8
                        RowLayout { Layout.fillWidth: true
                            AppCheck { checked: card.modelData.included; text: "第 " + card.modelData.number + " 题"; font.weight: Font.DemiBold
                                onClicked: { confirmed.checked=false; dialog.importer.includeQuestion(card.modelData.paperIndex, card.modelData.questionIndex, checked) } }
                            Item { Layout.fillWidth: true }
                            Text { text: card.modelData.answerSource; color: card.modelData.answerSource === "AI 参考答案" ? "#AE6556" : dialog.muted; font.pixelSize: 11 }
                        }
                        Text { Layout.fillWidth: true; text: card.modelData.stem; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: dialog.ink
                            font.family: dialog.language === "en" ? "Georgia" : "Yu Gothic UI"; font.pixelSize: 16; lineHeight: 1.2 }
                        Repeater { model: card.modelData.options
                            RowLayout { id: optionRow; required property string modelData; required property int index; Layout.fillWidth: true; spacing: 10
                                Rectangle { Layout.preferredWidth: 24; Layout.preferredHeight: 24; Layout.alignment: Qt.AlignTop; radius: 6; color: settings.palette.page; border.color: "#E0E8E2"
                                    Text { anchors.centerIn: parent; text: "ABCDEF"[optionRow.index]; font.pixelSize: 11; font.weight: Font.DemiBold; color: "#74857A" } }
                                Text { text: optionRow.modelData; textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap; color: dialog.ink
                                    font.family: dialog.language === "en" ? "Georgia" : "Yu Gothic UI"; font.pixelSize: 14; lineHeight: 1.15 }
                            }
                        }
                        RowLayout { visible: dialog.revealAnswers; spacing: 4
                            Text { text: "答案"; font.pixelSize: 12; color: dialog.muted }
                            Repeater { model: card.modelData.options.length
                                AppButton { required property int index
                                    objectName: "readingPaperAnswer_" + card.modelData.paperIndex + "_" + card.modelData.questionIndex + "_" + index
                                    text: "ABCDEF"[index]; implicitWidth: 34; implicitHeight: 28; primary: card.modelData.answer === text
                                    onClicked: { confirmed.checked=false; dialog.importer.setAnswer(card.modelData.paperIndex, card.modelData.questionIndex, text) }
                                }
                            }
                        }
                    }
                }
            }
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; color: dialog.state.error ? "#B44A4A" : dialog.muted
            text: dialog.state.error || dialog.state.message || (dialog.backend === "cloud" ? "云端整理会发送上面的文本，使用设置页的接口与模型。原文件由本地 MinerU 处理。" : "本地整理使用 Ollama；原文件和文本保留在本机。")
            maximumLineCount: 3; elide: Text.ElideRight
        }
        ScrollView { visible: dialog.state.warnings.length > 0; Layout.fillWidth: true; Layout.preferredHeight: 55; clip: true
            TextArea { text: dialog.state.warnings.join("\n"); readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                font.pixelSize: 11; color: "#A06A41"; background: null }
        }
        AppCheck { id: confirmed; objectName: "readingPaperImportConfirm"; visible: dialog.tab === 1; Layout.fillWidth: true
            text: "题目排版正常，可以开始练习（答案交卷后显示）"; enabled: !dialog.state.busy }
        Flow {
            Layout.fillWidth: true; spacing: 8
            AppButton { objectName: "readingPaperImportParse"; text: "规则识别"; enabled: !dialog.state.busy && !!source.text.trim(); onClicked: dialog.parse() }
            AppButton { objectName: "readingPaperImportOrganize"; text: "模型整理题目"; enabled: !dialog.state.busy && !!source.text.trim(); onClicked: dialog.organize() }
            AppButton { objectName: "readingPaperImportAuto"; text: "AI 自动准备"; visible: dialog.tab === 0; enabled: !dialog.state.busy && !!source.text.trim(); onClicked: dialog.prepareAutomatically() }
            AppButton { objectName: "readingPaperImportFill"; text: "AI 补缺失答案"; visible: dialog.tab === 1; enabled: !dialog.state.busy && dialog.state.missing > 0; onClicked: dialog.importer.fillAnswers(dialog.backend) }
            AppButton { text: "排除缺答案题"; visible: dialog.tab === 1 && dialog.state.missing > 0; enabled: !dialog.state.busy; flat: true; onClicked: { confirmed.checked=false; dialog.importer.skipUnanswered() } }
            AppButton { text: "取消任务"; visible: dialog.state.busy; onClicked: dialog.importer.cancel() }
            AppButton { objectName: "readingPaperImportSave"; text: "导入并练习"; primary: true
                enabled: confirmed.checked && !dialog.state.busy && dialog.state.selectedCount > 0 && !dialog.state.missing
                onClicked: { var id=dialog.importer.save(confirmed.checked); if (id) { dialog.paperImported(id); dialog.close() } }
            }
        }
    }
    FileDialog {
        id: filePicker; objectName: "readingPaperSourceFilePicker"; title: "选择阅读试卷或书籍"; fileMode: FileDialog.OpenFile
        nameFilters: ["阅读文档 (*.md *.markdown *.txt *.pdf *.docx *.pptx *.epub *.png *.jpg *.jpeg *.webp *.bmp)"]
        onAccepted: dialog.importer.loadFile(selectedFile.toString(), "local", pythonInput.text, pagesInput.text, dialog.language, ["auto", "cpu", "cuda"][deviceInput.currentIndex])
    }
}
