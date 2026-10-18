import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool primary: false
    property bool destructive: false
    property color accent: settings.values.theme === "classic" ? "#4E8068" : settings.palette.accent
    property color primaryColor: destructive ? "#C94859" : accent
    implicitWidth: Math.max(68, label.implicitWidth + 24)
    implicitHeight: 36
    hoverEnabled: true
    contentItem: Text {
        id: label; text: button.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        color: !button.enabled ? "#A0AAA2" : button.primary ? "#FFFFFF" : "#334039"
        font.family: "Microsoft YaHei UI"; font.pixelSize: 12; font.weight: Font.DemiBold
    }
    background: Rectangle {
        radius: 8
        color: !button.enabled ? "#F1F3F1" : button.primary ? (button.hovered ? Qt.darker(button.primaryColor, 1.12) : button.primaryColor)
             : button.flat ? (button.hovered ? "#F1F4F1" : "transparent")
             : button.hovered ? "#EEF1EE" : "#FFFFFF"
        border.color: button.flat ? "transparent" : button.primary ? button.primaryColor : "#DDE3DD"
    }
}
