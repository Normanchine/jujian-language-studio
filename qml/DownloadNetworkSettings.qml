import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: networkPanel
    objectName: "downloadNetworkPanel"
    height: content.height + 36
    radius: 12; color: "#F6F9F6"; border.color: "#E1E8E2"
    property var network: downloads.network
    property bool locked: downloads.busy || network.busy
    property bool advanced: false
    property color accent: settings.palette.accent
    property string formStatus: ""
    function saveNetwork() {
        var saved = settings.saveDownloadNetwork(proxyField.text, controllerField.text,
                                                secretField.text, autoNode.checked)
        formStatus = saved ? "连接设置已保存" : settings.status
        if (saved) secretField.clear()
        return saved
    }
    component ConnectionField: TextField {
        implicitHeight: 38; leftPadding: 12; rightPadding: 12
        font.family: "Microsoft YaHei UI"; font.pixelSize: 12
        color: "#33443A"; placeholderTextColor: "#93A097"
        readOnly: networkPanel.locked; selectByMouse: true
        background: Rectangle {
            radius: 8; color: "#FFFFFF"
            border.color: parent.activeFocus ? networkPanel.accent : "#DCE5DE"
        }
    }
    Column {
        id: content; x: 18; y: 18; width: parent.width - 36; spacing: 15
        RowLayout { width: parent.width; spacing: 11
            Rectangle { width: 34; height: 34; radius: 10; color: "#E4EEE6"
                Text { anchors.centerIn: parent; text: "↗"; color: networkPanel.accent; font.pixelSize: 23 }
            }
            Column { spacing: 4; Layout.fillWidth: true
                Text { text: "YouTube 下载"; color: "#2D4033"; font.pixelSize: 15; font.weight: Font.DemiBold }
                Text { text: "Clash 提供连接，国内来源保持直连"; color: "#819086"; font.pixelSize: 11 }
            }
            Rectangle { implicitWidth: connectionBadge.implicitWidth + 25; height: 25; radius: 12
                color: network.ready ? "#E5F0E8" : "#EDF0ED"
                Text { id: connectionBadge; anchors.centerIn: parent
                    text: network.busy ? "连接处理中" : network.ready ? "● 已连接" : "未连接"
                    color: network.ready ? "#4B805B" : "#859087"; font.pixelSize: 11 }
            }
        }
        Rectangle { width: parent.width; height: 1; color: "#E2E9E3" }
        Column { width: parent.width; spacing: 8
            RowLayout { width: parent.width
                Text { text: "下载节点"; color: "#526359"; font.pixelSize: 12; Layout.fillWidth: true }
                AppButton { text: network.busy ? "检测中…" : "检测延迟"; flat: true; height: 27
                    visible: network.ready; enabled: !networkPanel.locked
                    onClicked: network.run("test", "") }
                AppButton { text: "取消"; flat: true; height: 27; visible: network.testing
                    onClicked: network.cancel() }
            }
            RowLayout { width: parent.width; spacing: 8; visible: network.ready
                AppCombo {
                    id: nodeChoice; objectName: "youtubeNodeChoice"
                    Layout.fillWidth: true; implicitHeight: 40
                    enabled: !networkPanel.locked; model: network.nodes; textRole: "name"
                    popup.objectName: "youtubeNodePopup"
                    property var selectedNode: currentIndex >= 0 && currentIndex < network.nodes.length ? network.nodes[currentIndex] : ({})
                    contentItem: RowLayout {
                        spacing: 12
                        Text { Layout.leftMargin: 12; Layout.fillWidth: true; text: nodeChoice.selectedNode.name || "选择节点"
                            elide: Text.ElideRight; color: "#34463A"; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                        Text { Layout.rightMargin: 31
                            text: nodeChoice.selectedNode.tested ? (nodeChoice.selectedNode.delay ? nodeChoice.selectedNode.delay + " ms" : "超时") : "未检测"
                            color: !nodeChoice.selectedNode.tested ? "#96A199" : nodeChoice.selectedNode.delay ? "#3F8A5A" : "#C36363"
                            font.pixelSize: 12; font.weight: Font.Medium; verticalAlignment: Text.AlignVCenter }
                    }
                    delegate: ItemDelegate {
                        required property var modelData
                        required property int index
                        width: nodeChoice.width; height: 40; highlighted: nodeChoice.highlightedIndex === index
                        contentItem: RowLayout {
                            Text { Layout.fillWidth: true; text: modelData.name; elide: Text.ElideRight
                                color: "#34463A"; font.pixelSize: 12 }
                            Text { text: modelData.tested ? (modelData.delay ? modelData.delay + " ms" : "超时") : "未检测"
                                color: !modelData.tested ? "#96A199" : modelData.delay ? "#3F8A5A" : "#C36363"
                                font.pixelSize: 12 }
                        }
                        background: Rectangle { radius: 5; color: parent.highlighted ? "#EAF1EB" : "#FFFFFF" }
                    }
                    onModelChanged: {
                        for (var i = 0; i < network.nodes.length; i++) {
                            if (network.nodes[i].name === network.current) { currentIndex = i; return }
                        }
                        currentIndex = network.nodes.length ? 0 : -1
                    }
                }
                AppButton { text: "切换节点"; height: 40
                    enabled: !networkPanel.locked && nodeChoice.currentIndex >= 0 && nodeChoice.selectedNode.name !== network.current
                    onClicked: network.run("select", nodeChoice.selectedNode.name) }
            }
            Row { visible: !network.ready; spacing: 8
                AppButton { text: "连接 Clash"; enabled: !networkPanel.locked
                    onClicked: if (networkPanel.saveNetwork()) network.run("refresh", "") }
                AppButton { text: "启用节点管理"; primary: true; enabled: !networkPanel.locked
                    onClicked: routeDialog.open() }
            }
        }
        Rectangle { width: parent.width; height: automaticRow.height + 24; radius: 9
            color: "#EDF3EE"
            RowLayout { id: automaticRow; x: 12; y: 12; width: parent.width - 24; spacing: 16
                Column { Layout.fillWidth: true; spacing: 5
                    Text { text: "自动选择可用节点"; color: "#3B5243"; font.pixelSize: 13; font.weight: Font.Medium }
                    Text { text: "下载前检测连接，超时后尝试备用节点"; color: "#849287"; font.pixelSize: 11 }
                }
                Switch {
                    id: autoNode; objectName: "youtubeAutoNode"
                    checked: settings.values.youtube_auto_node; enabled: !networkPanel.locked
                    implicitWidth: 40; implicitHeight: 24; padding: 0
                    indicator: Rectangle {
                        implicitWidth: 40; implicitHeight: 23; radius: 12
                        color: autoNode.checked ? networkPanel.accent : "#C7D1C9"
                        opacity: autoNode.enabled ? 1 : 0.65
                        Rectangle { x: autoNode.checked ? 20 : 3; y: 3; width: 17; height: 17; radius: 9; color: "#FFFFFF"
                            Behavior on x { NumberAnimation { duration: 120 } } }
                    }
                    onClicked: if (!networkPanel.saveNetwork()) checked = settings.values.youtube_auto_node
                    ToolTip.visible: hovered
                    ToolTip.text: "最多尝试 3 个节点；不会改变其他程序的节点选择"
                }
            }
        }
        Column { width: parent.width; spacing: 6; visible: network.status.length > 0
            Text { objectName: "clashStatus"; text: network.status; width: parent.width
                wrapMode: Text.Wrap; color: "#7B8B80"; font.pixelSize: 11 }
            Rectangle { width: parent.width; height: 3; radius: 2; color: "#E2EAE3"; visible: network.testing
                Rectangle { width: parent.width * network.testProgress; height: 3; radius: 2; color: networkPanel.accent }
            }
        }
        Column { width: parent.width; spacing: 12
            RowLayout { width: parent.width
                AppButton { text: networkPanel.advanced ? "连接设置  ⌃" : "连接设置  ⌄"; flat: true; height: 25
                    onClicked: networkPanel.advanced = !networkPanel.advanced }
                Item { Layout.fillWidth: true }
                Text { text: "保留当前 TUN 设置"; font.pixelSize: 11; color: "#95A198" }
            }
            Column { width: parent.width; spacing: 13; visible: networkPanel.advanced
                Rectangle { width: parent.width; height: 1; color: "#E2E9E3" }
                RowLayout { width: parent.width; spacing: 16
                    Column { Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0; spacing: 7
                        Text { text: "下载代理"; color: "#64776A"; font.pixelSize: 11 }
                        ConnectionField { id: proxyField; objectName: "youtubeProxyField"; width: parent.width
                            text: settings.values.youtube_proxy; placeholderText: "http://127.0.0.1:7897" }
                    }
                    Column { Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0; spacing: 7
                        Text { text: "控制接口"; color: "#64776A"; font.pixelSize: 11 }
                        ConnectionField { id: controllerField; objectName: "clashControllerField"; width: parent.width
                            text: settings.values.clash_controller; placeholderText: "自动读取 Clash Verge" }
                    }
                }
                Column { width: parent.width; spacing: 7
                    Text { text: "控制密钥"; color: "#64776A"; font.pixelSize: 11 }
                    ConnectionField { id: secretField; width: parent.width; echoMode: TextInput.Password
                        placeholderText: "自动读取本机配置；仅在需要时手动填写" }
                }
                RowLayout { width: parent.width
                    Text { Layout.fillWidth: true; text: formStatus || "手动密钥保存在 Windows 凭据管理器"; color: "#91A095"; font.pixelSize: 11 }
                    AppButton { text: "保存连接设置"; enabled: !networkPanel.locked
                        onClicked: if (networkPanel.saveNetwork()) network.run("refresh", "") }
                }
                Text { width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11; color: "#91A095"
                    text: "节点管理使用独立的下载通道。Clash 重启或切换订阅后，可重新启用。" }
            }
        }
    }
    Dialog {
        id: routeDialog; title: "启用节点管理"; modal: true
        anchors.centerIn: Overlay.overlay; width: Math.min(480, networkPanel.width)
        height: 210
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Text { wrapMode: Text.Wrap; color: "#4B5A50"; font.pixelSize: 13
            text: "将加载一次 Clash 当前运行配置，建立专用下载通道，并保留 TUN、运行模式和原有节点选择。加载时现有连接可能短暂受影响。不会修改订阅文件。" }
        onAccepted: if (networkPanel.saveNetwork()) network.run("setup", "")
    }
}
