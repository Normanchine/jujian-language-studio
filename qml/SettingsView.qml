import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: settingsPage
    property string appVersion: ""
    component ShortcutField: TextField {
        id: keyField
        property string sequence: ""
        property bool allowModifier: false
        property string modifierCandidate: ""
        onActiveFocusChanged: if (activeFocus) modifierCandidate=""
        implicitWidth: 165; implicitHeight: 36
        readOnly: true; text: activeFocus ? "请按快捷键…" : sequence
        selectByMouse: false
        background: Rectangle { radius: 9; color: keyField.activeFocus ? "#EAF2EC" : "#F8FAF8"
            border.color: keyField.activeFocus ? "#4E8068" : "#DEE4DE" }
        Keys.onPressed: function(event) {
            event.accepted = true
            if (event.key === Qt.Key_Escape) { focus = false; return }
            var modifier=event.key===Qt.Key_Alt || event.key===Qt.Key_Control || event.key===Qt.Key_Shift || event.key===Qt.Key_Meta;
            if (allowModifier && modifier) {modifierCandidate=settings.readingTriggerSequence(event.key,event.modifiers);return;}
            var value = allowModifier ? settings.readingTriggerSequence(event.key,event.modifiers) : settings.keySequence(event.key, event.modifiers)
            if (value.length) { sequence = value; focus = false }
        }
        Keys.onReleased: function(event) {
            if (allowModifier && activeFocus && modifierCandidate.length && settings.readingTriggerSequence(event.key,event.modifiers)===modifierCandidate) {
                sequence=modifierCandidate;modifierCandidate="";focus=false;event.accepted=true;
            }
        }
    }
    FolderDialog { id: folderPicker; title: "选择下载目录"
        onAccepted: folderField.text = settings.localFolder(selectedFolder.toString()) }
    Flickable {
        anchors.fill: parent; clip: true; contentWidth: width; contentHeight: panel.height + 24
        ScrollBar.vertical: ScrollBar {
            id: settingsScroll
            policy: ScrollBar.AsNeeded; width: 8
            background: Item { }
            contentItem: Rectangle { implicitWidth: 6; radius: 3
                color: settingsScroll.pressed ? "#87998C" : "#B8C7BC" }
        }
        Rectangle { id: panel; x: 4; y: 4; width: parent.width - 8; height: settingsColumn.height + 38
            color: "#FFFFFF"; radius: 10; border.color: "#DFE4E0"
            Column { id: settingsColumn; x: 22; y: 19; width: parent.width - 44; spacing: 13
                RowLayout { width: parent.width
                    Text { text: "设置"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D"
                        Layout.fillWidth: true }
                    Text { objectName: "settingsVersionLabel"; text: "句间 v" + settingsPage.appVersion
                        font.pixelSize: 12; color: "#819087" }
                }
                Rectangle { width: parent.width; height: 1; color: "#E9EDE9" }
                Text { text: "外观"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
                Flow {
                    width: parent.width; spacing: 10
                    Repeater {
                        model: settings.themeOptions
                        delegate: Rectangle {
                            id: themeOption
                            required property var modelData
                            objectName: "themeOption_" + modelData.key
                            width: Math.min(138, (settingsColumn.width - 30) / 4)
                            height: 64; radius: 9; color: "#FFFFFF"
                            border.width: settings.values.theme === modelData.key ? 2 : 1
                            border.color: settings.values.theme === modelData.key ? modelData.accent : "#DEE4DE"
                            Rectangle { x: 9; y: 9; width: parent.width - 18; height: 28; radius: 5
                                color: themeOption.modelData.page
                                Rectangle { width: 31; height: parent.height; radius: 5
                                    color: themeOption.modelData.side }
                                Rectangle { x: 39; y: 8; width: 28; height: 11; radius: 3
                                    color: themeOption.modelData.accent }
                            }
                            Text { x: 10; y: 42; text: themeOption.modelData.name
                                color: "#334039"; font.family: "Microsoft YaHei UI"; font.pixelSize: 11 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: settings.setTheme(themeOption.modelData.key) }
                        }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: "#E9EDE9" }
                Text { text: "精听快捷键"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
                Text { text: "点击输入框后按下快捷键，再保存。仅在精听页生效；输入文字时不会触发。"
                    width: parent.width; wrapMode: Text.Wrap; color: "#78857A"; font.pixelSize: 12 }
                GridLayout {
                    columns: 4; columnSpacing: 12; rowSpacing: 10
                    Text { text: "上一句"; color: "#4B5A50" }
                    ShortcutField { id: previousKey; objectName: "previousShortcut"; sequence: settings.values.shortcut_previous }
                    Text { text: "下一句"; color: "#4B5A50" }
                    ShortcutField { id: nextKey; objectName: "nextShortcut"; sequence: settings.values.shortcut_next }
                    Text { text: "播放 / 暂停"; color: "#4B5A50" }
                    ShortcutField { id: playKey; sequence: settings.values.shortcut_play }
                    Text { text: "循环本句"; color: "#4B5A50" }
                    ShortcutField { id: loopKey; sequence: settings.values.shortcut_loop }
                    Text { text: "重播当前句"; color: "#4B5A50" }
                    ShortcutField { id: replayKey; sequence: settings.values.shortcut_replay }
                }
                Row { spacing: 10
                    AppButton { text: "保存快捷键"
                        onClicked: settings.saveShortcuts(previousKey.sequence, nextKey.sequence, playKey.sequence, loopKey.sequence, replayKey.sequence) }
                    AppButton { text: "恢复默认快捷键"
                        onClicked: {
                            previousKey.sequence = "Ctrl+Left"; nextKey.sequence = "Ctrl+Right"
                            playKey.sequence = "Space"; loopKey.sequence = "Ctrl+L"; replayKey.sequence = "Ctrl+R"
                            settings.saveShortcuts("Ctrl+Left", "Ctrl+Right", "Space", "Ctrl+L", "Ctrl+R")
                        } }
                }
                Text { text: settings.status; color: "#748178"; font.pixelSize: 12; width: parent.width; wrapMode: Text.Wrap }
                Rectangle { width: parent.width; height: 1; color: "#E9EDE9" }
                Text { text: "精读快捷键"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
                Text { text: "按住快捷键拖选词句，松开鼠标查询。普通划选用于复制。";width: parent.width;wrapMode: Text.Wrap;color: "#78857A";font.pixelSize: 12 }
                RowLayout { width: parent.width;spacing: 12
                    Text { text: "划选查询";color: "#4B5A50" }
                    ShortcutField { id: readingQueryKey;objectName: "readingQueryShortcut";allowModifier: true;sequence: settings.values.shortcut_reading_query }
                    AppButton { objectName: "saveReadingQueryShortcut";text: "保存";onClicked: settings.saveReadingShortcut(readingQueryKey.sequence) }
                    AppButton { text: "恢复 Alt";flat: true;onClicked: {readingQueryKey.sequence="Alt";settings.saveReadingShortcut("Alt");} }
                }
                Rectangle { width: parent.width; height: 1; color: "#E9EDE9" }
                Text { text: "下载"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
                RowLayout { width: parent.width; height: 38
                    TextField { id: folderField; Layout.fillWidth: true; placeholderText: "下载文件保存目录"
                        Component.onCompleted: text = settings.values.download_dir
                        background: Rectangle { radius: 7; color: "#F8FAF8"; border.color: "#DEE4DE" } }
                    AppButton { text: "选择目录"; onClicked: folderPicker.open() }
                }
                Rectangle { width: parent.width; height: 1; color: "#E9EDE9" }
                Text { text: "模型"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
                Text { text: "本地使用 Ollama；选择云端时，对应任务的文本会发送到所填接口。"
                    color: "#78857A"; font.pixelSize: 12 }
                Text { text: "接口：DeepSeek https://api.deepseek.com；千问 https://dashscope.aliyuncs.com/compatible-mode/v1"
                    width: parent.width; wrapMode: Text.WrapAnywhere
                    color: "#4B5A50"; font.pixelSize: 12 }
                TextField { id: endpointField; width: parent.width; height: 36
                    placeholderText: "填写 Chat Completions 接口根地址"
                    Component.onCompleted: text = settings.values.cloud_endpoint
                    background: Rectangle { radius: 7; color: "#F8FAF8"; border.color: "#DEE4DE" } }
                Text { visible: /\/anthropic\/?$/.test(endpointField.text.trim())
                    text: "这是 Anthropic 格式地址；本应用请填 https://api.deepseek.com。"
                    color: "#B33E51"; font.pixelSize: 11 }
                Text { text: "云端模型名"; color: "#4B5A50"; font.pixelSize: 12 }
                TextField { id: modelField; width: parent.width; height: 36
                    placeholderText: "填写接口支持的模型名"
                    Component.onCompleted: text = settings.values.cloud_model
                    background: Rectangle { radius: 7; color: "#F8FAF8"; border.color: "#DEE4DE" } }
                RowLayout { width: parent.width; height: 38
                    TextField { id: keyField; Layout.fillWidth: true; echoMode: TextInput.Password
                        placeholderText: settings.hasKey ? "已保存 API Key；输入新值可替换" : "输入 API Key"
                        background: Rectangle { radius: 7; color: "#F8FAF8"; border.color: "#DEE4DE" } }
                    AppButton { text: "保存密钥"; enabled: keyField.text.trim().length > 0
                        onClicked: {
                            if (settings.save(folderField.text, endpointField.text, modelField.text,
                                    translationRoute.currentIndex ? "cloud" : "local",
                                    analysisRoute.currentIndex ? "cloud" : "local",
                                    writingRoute.currentIndex ? "cloud" : "local") && settings.saveKey(keyField.text))
                                keyField.clear()
                        } }
                    AppButton { text: "移除密钥"; enabled: settings.hasKey; onClicked: settings.clearKey() }
                }
                Text { text: settings.hasKey ? "此接口的 API Key 已保存；切换服务商需保存对应密钥。" : "此接口尚无 API Key；密钥只保存在 Windows 凭据管理器。"
                    color: "#839087"; font.pixelSize: 11 }
                RowLayout { width: parent.width; height: 39; spacing: 14
                    Text { text: "中文翻译"; color: "#4B5A50"; Layout.preferredWidth: 80 }
                    AppCombo { id: translationRoute; Layout.preferredWidth: 120
                        model: ["本地 Ollama", "云端 API"]
                        Component.onCompleted: currentIndex = settings.values.translation_backend === "cloud" ? 1 : 0 }
                    Text { text: "句子解析"; color: "#4B5A50"; Layout.preferredWidth: 80 }
                    AppCombo { id: analysisRoute; Layout.preferredWidth: 120
                        model: ["本地 Ollama", "云端 API"]
                        Component.onCompleted: currentIndex = settings.values.analysis_backend === "cloud" ? 1 : 0 }
                    Text { text: "作文"; color: "#4B5A50"; Layout.preferredWidth: 40 }
                    AppCombo { id: writingRoute; Layout.preferredWidth: 120
                        model: ["本地 Ollama", "云端 API"]
                        Component.onCompleted: currentIndex = settings.values.writing_backend === "cloud" ? 1 : 0 }
                    Item { Layout.fillWidth: true }
                }
                RowLayout { width: parent.width; height: 38
                    Text { text: settings.status; Layout.fillWidth: true; color: "#748178"; font.pixelSize: 12 }
                    AppButton { text: "保存设置"
                        onClicked: settings.save(folderField.text, endpointField.text, modelField.text,
                                                 translationRoute.currentIndex ? "cloud" : "local",
                                                 analysisRoute.currentIndex ? "cloud" : "local",
                                                 writingRoute.currentIndex ? "cloud" : "local") }
                }
            }
        }
    }
}
