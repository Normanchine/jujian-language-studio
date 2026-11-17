import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: panel
    objectName: "recordingSettingsPanel"
    property var service: study.recorder
    property var deviceOptions: {
        var options=[{name:"",label:"跟随系统默认播放设备"}].concat(service.devices)
        var saved=service.preferences.deviceName
        if (saved && !options.some(function(d) {return d.name===saved}))
            options.push({name:saved,label:saved.replace(" [Loopback]","")+"（未连接）"})
        return options
    }
    property bool locked: service.busy
    height: content.implicitHeight + 40
    radius: 12; color: settings.palette.page
    border.color: Qt.tint(settings.palette.surface, Qt.rgba(settings.palette.accent.r, settings.palette.accent.g, settings.palette.accent.b, .16))

    function load() {
        device.currentIndex=Math.max(0,deviceOptions.findIndex(function(d) {return d.name===service.preferences.deviceName}))
        padding.currentIndex=service.preferences.padding===1 ? 1 : 0
        sensitivity.currentIndex=Math.max(0,[-50,-60,-40].indexOf(service.preferences.thresholdDb))
        language.currentIndex=service.preferences.language==="ja" ? 1 : 0
        transcribe.checked=service.preferences.transcribe
    }
    Component.onCompleted: {
        load()
        if (visible && !service.devices.length && !service.busy) service.refreshDevices()
    }
    onDeviceOptionsChanged: {
        if (device) device.currentIndex=Math.max(0,deviceOptions.findIndex(function(d) {return d.name===service.preferences.deviceName}))
    }
    Connections { target: panel.service; function onPreferencesChanged() { panel.load() } }
    ColumnLayout {
        id: content; x: 20; y: 20; width: parent.width-40; spacing: 14
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                width: 36; height: 36; radius: 10; color: settings.palette.selection
                Row { anchors.centerIn: parent; spacing: 3
                    Repeater { model: [10,20,14,24,10]
                        delegate: Rectangle { required property int modelData; width: 2; height: modelData; radius: 1
                            color: settings.palette.accent; anchors.verticalCenter: parent.verticalCenter } }
                }
            }
            ColumnLayout { spacing: 3; Layout.fillWidth: true
                Text { text: "录制导入"; color: "#2D4033"; font.pixelSize: 15; font.weight: Font.DemiBold }
                Text { text: "首页一键录制，停止后试听、命名并归档"; color: "#819086"; font.pixelSize: 12
                    Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: "#E1E7E2" }
        Text { text: "播放设备"; color: "#526359"; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            AppCombo { id: device; objectName: "recordingSettingsDevice"; Layout.fillWidth: true; implicitHeight: 40
                model: panel.deviceOptions; textRole: "label"; enabled: !panel.locked
                popup.objectName: "recordingSettingsDevicePopup"
                onPressedChanged: if (pressed && !service.devices.length && !service.busy) service.refreshDevices()
            }
            AppButton { objectName: "recordingSettingsRefresh"; text: "刷新"; implicitHeight: 40
                enabled: !panel.locked; onClicked: service.refreshDevices() }
        }
        Text { text: "只录电脑播放的声音，不使用麦克风。戴耳机也能录制。"; color: "#819086"; font.pixelSize: 12
            Layout.fillWidth: true; wrapMode: Text.Wrap }
        GridLayout {
            Layout.fillWidth: true; columns: panel.width>=600 ? 2 : 1; columnSpacing: 18; rowSpacing: 14
            ColumnLayout { spacing: 7; Layout.fillWidth: true
                Text { text: "首尾各保留"; color: "#526359"; font.pixelSize: 12 }
                AppCombo { id: padding; objectName: "recordingSettingsPadding"; model: ["0.5 秒", "1 秒"]; Layout.fillWidth: true; implicitHeight: 40; enabled: !panel.locked }
            }
            ColumnLayout { spacing: 7; Layout.fillWidth: true
                Text { text: "静音检测"; color: "#526359"; font.pixelSize: 12 }
                AppCombo { id: sensitivity; objectName: "recordingSettingsSensitivity"; model: ["默认", "保留更轻的声音", "忽略较低底噪"]
                    Layout.fillWidth: true; implicitHeight: 40; enabled: !panel.locked }
            }
            ColumnLayout { spacing: 7; Layout.fillWidth: true
                Text { text: "默认语言"; color: "#526359"; font.pixelSize: 12 }
                AppCombo { id: language; objectName: "recordingSettingsLanguage"; model: ["英语", "日语"]
                    Layout.fillWidth: true; implicitHeight: 40; enabled: !panel.locked }
            }
            ColumnLayout { spacing: 7; Layout.fillWidth: true
                Text { text: "停止录制"; color: "#526359"; font.pixelSize: 12 }
                Text { text: "Ctrl + Shift + R"; color: settings.palette.accent; font.pixelSize: 13; font.weight: Font.Medium; Layout.preferredHeight: 40; verticalAlignment: Text.AlignVCenter }
            }
        }
        AppCheck { id: transcribe; objectName: "recordingSettingsTranscribe"; text: "导入后默认开始本地转写"; enabled: !panel.locked; Layout.fillWidth: true }
        Text { text: "只整理首尾静音，保留听力中间的停顿。导入时仍可调整范围、语言和转写选项。"; color: "#819086"; font.pixelSize: 12
            Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Text { text: panel.locked ? "录音处理完成后可修改设置" : service.preferencesStatus
                color: service.preferencesError ? "#B64050" : "#748178"; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            AppButton { objectName: "recordingSettingsSave"; text: "保存录制设置"; primary: true; enabled: !panel.locked
                onClicked: service.saveOptions((panel.deviceOptions[device.currentIndex] || {}).name || "",padding.currentIndex===1 ? 1 : .5,
                    [-50,-60,-40][sensitivity.currentIndex],transcribe.checked,language.currentIndex===1 ? "ja" : "en") }
        }
    }
}
