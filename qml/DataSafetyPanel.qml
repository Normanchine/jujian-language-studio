import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    objectName: "dataSafetyPanel"
    property var safety: settings.dataSafety
    property string selectedBackup: ""
    spacing: 10
    onVisibleChanged: if (visible) safety.refresh()

    Text { text: "学习数据"; font.pixelSize: 17; font.weight: Font.DemiBold; color: "#27352D" }
    Text {
        Layout.fillWidth: true; wrapMode: Text.Wrap
        text: "备份学习记录，或找回误删的作文。备份与原数据在同一磁盘。"
        font.pixelSize: 12; color: "#78857A"
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: cardContent.implicitHeight + 34
        radius: 10; color: "#F8FAF8"; border.color: "#E1E8E1"
        ColumnLayout {
            id: cardContent
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.margins: 17
            spacing: 13

            RowLayout {
                Layout.fillWidth: true; spacing: 8
                ColumnLayout { spacing: 2
                    Text { text: "备份与恢复"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#293B32" }
                    Text { text: "保存当前学习记录的可校验快照"; font.pixelSize: 11; color: "#819087" }
                }
                Item { Layout.fillWidth: true }
                AppButton { objectName: "backupNowButton"; text: "立即备份"; primary: true
                    onClicked: panel.safety.backup() }
            }

            RowLayout {
                Layout.fillWidth: true; spacing: 8
                AppCombo {
                    id: backups; objectName: "backupSelector"
                    Layout.fillWidth: true; textRole: "label"
                    model: panel.safety.snapshots
                    enabled: model.length > 0
                    displayText: model.length ? currentText : "暂无备份"
                }
                AppButton { text: "恢复…"; enabled: backups.currentIndex >= 0 && backups.model.length > 0
                    onClicked: { panel.selectedBackup = panel.safety.snapshots[backups.currentIndex].name; restoreConfirm.open() } }
            }
            Text {
                visible: panel.safety.restorePending
                Layout.fillWidth: true; wrapMode: Text.Wrap
                text: "已安排恢复，下次启动生效。"; color: "#815B34"; font.pixelSize: 12
            }
            AppButton { visible: panel.safety.restorePending; text: "取消待执行的恢复"; flat: true
                onClicked: panel.safety.cancelRestore() }
            Text { Layout.fillWidth: true; text: panel.safety.status; visible: text.length > 0
                wrapMode: Text.Wrap; color: "#815B34"; font.pixelSize: 12 }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#E1E8E1" }
            RowLayout { Layout.fillWidth: true
                Text { text: "作文回收站"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#293B32" }
                Item { Layout.fillWidth: true }
                Text { text: panel.safety.essays.length + " 篇"; font.pixelSize: 11; color: "#819087" }
            }
            Text { visible: panel.safety.essays.length === 0; text: "暂无可恢复的作文"; color: "#819087"; font.pixelSize: 12 }
            Repeater {
                model: panel.safety.essays
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true; spacing: 10
                    Text { Layout.fillWidth: true; text: modelData.title + " · " + modelData.deleted
                        elide: Text.ElideRight; color: "#4B5A50"; font.pixelSize: 12 }
                    AppButton { text: "恢复"; onClicked: panel.safety.restoreEssay(modelData.id) }
                }
            }
        }
    }

    Flow {
        Layout.fillWidth: true; spacing: 6
        AppButton { text: "打开数据目录"; flat: true; onClicked: panel.safety.openData() }
        AppButton { text: "打开备份目录"; flat: true; onClicked: panel.safety.openBackups() }
        AppButton { text: "刷新"; flat: true; onClicked: panel.safety.refresh() }
    }
    Text { Layout.fillWidth: true; text: "当前目录：" + panel.safety.directory
        wrapMode: Text.WrapAnywhere; font.pixelSize: 11; color: "#91A096" }
    Text { Layout.fillWidth: true
        text: "备份包含记录、设置与文本资料；不包含原音视频、模型或 API 密钥。"
        wrapMode: Text.Wrap; font.pixelSize: 11; color: "#91A096" }

    Dialog {
        id: restoreConfirm
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 32)
        modal: true; title: "恢复学习记录"
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Text { wrapMode: Text.Wrap; text: "将恢复备份：\n" + panel.selectedBackup + "\n\n关闭并重开程序后执行。当前记录会先另存备份，原音视频不会删除。" }
        onAccepted: panel.safety.scheduleRestore(panel.selectedBackup)
    }
}
