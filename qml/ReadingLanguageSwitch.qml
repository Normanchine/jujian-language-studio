import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: control
    property string language: "en"
    signal chosen(string value)
    implicitWidth: 212; implicitHeight: 40
    width: implicitWidth; height: implicitHeight
    radius: 9; color: Qt.tint(settings.palette.page, "#0A536B5D")
    Rectangle {
        id: selection
        objectName: "readingLanguageThumb"
        x: control.language === "ja" ? 4 : control.width / 2 + 1
        y: 4; width: (control.width - 11) / 2; height: control.height - 8
        radius: 7; color: settings.palette.surface; border.color: "#DFE7E1"
        Behavior on x { NumberAnimation { duration: uiAnimationsEnabled ? 190 : 0; easing.type: Easing.OutCubic } }
    }
    RowLayout {
        anchors.fill: parent; anchors.margins: 4; spacing: 3
        Repeater { model: [{label:"日语阅读", value:"ja"}, {label:"英语阅读", value:"en"}]
            Button {
                id: tab; required property var modelData
                objectName: "readingLanguage_" + modelData.value
                Layout.fillWidth: true; Layout.fillHeight: true; hoverEnabled: true
                background: Rectangle { radius: 7; color: tab.hovered && control.language !== tab.modelData.value ? settings.palette.selection : "transparent" }
                contentItem: Text { text: tab.modelData.label; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 12; font.weight: control.language === tab.modelData.value ? Font.DemiBold : Font.Normal
                    color: control.language === tab.modelData.value ? settings.palette.accent : "#819087"
                    Behavior on color { ColorAnimation { duration: uiAnimationsEnabled ? 150 : 0 } } }
                onClicked: control.chosen(modelData.value)
            }
        }
    }
}
