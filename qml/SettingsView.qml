import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: settingsPage
    FolderDialog { id: folderPicker; title: "选择下载目录"
        onAccepted: folderField.text = settings.localFolder(selectedFolder.toString()) }
    Flickable {
        anchors.fill: parent; contentWidth: width; contentHeight: panel.height + 24
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        Rectangle { id: panel; x: 4; y: 4; width: parent.width - 8; height: settingsColumn.height + 38
            color: "#FFFFFF"; radius: 10; border.color: "#DFE4E0"
            Column { id: settingsColumn; x: 22; y: 19; width: parent.width - 44; spacing: 13
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
