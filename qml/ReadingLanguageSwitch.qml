import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: control
    property string language: "en"
    signal chosen(string value)
    implicitWidth: 212; implicitHeight: 40
    width: implicitWidth; height: implicitHeight
    radius: 11; color: Qt.tint(settings.palette.page, "#0A536B5D")
    RowLayout {
        anchors.fill: parent; anchors.margins: 4; spacing: 3
        Repeater { model: [{label:"日语阅读", value:"ja"}, {label:"英语阅读", value:"en"}]
            Button {
                id: tab; required property var modelData
                objectName: "readingLanguage_" + modelData.value
                Layout.fillWidth: true; Layout.fillHeight: true; hoverEnabled: true
                background: Rectangle { radius: 8; color: control.language === tab.modelData.value ? settings.palette.surface : tab.hovered ? settings.palette.selection : "transparent"
                    border.color: control.language === tab.modelData.value ? "#DFE7E1" : "transparent" }
                contentItem: Text { text: tab.modelData.label; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 12; font.weight: control.language === tab.modelData.value ? Font.DemiBold : Font.Normal
                    color: control.language === tab.modelData.value ? settings.palette.accent : "#819087" }
                onClicked: control.chosen(modelData.value)
            }
        }
    }
}
