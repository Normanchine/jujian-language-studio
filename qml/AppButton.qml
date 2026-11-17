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
    font.family: "Microsoft YaHei UI"; font.pixelSize: 12; font.weight: Font.DemiBold
    readonly property bool motion: typeof uiAnimationsEnabled !== "undefined" && uiAnimationsEnabled
    contentItem: Text {
        id: label; text: button.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        color: !button.enabled ? "#A0AAA2" : button.primary ? "#FFFFFF" : "#334039"
        font: button.font
    }
    background: Rectangle {
        radius: 8
        color: !button.enabled ? settings.palette.page
             : button.primary ? Qt.darker(button.primaryColor, button.down ? 1.18 : button.hovered ? 1.08 : 1)
             : button.flat ? (button.hovered ? settings.palette.selection : "transparent")
             : button.down ? settings.palette.selection : button.hovered ? settings.palette.page : settings.palette.surface
        border.color: !button.enabled ? "#E1E6E1" : button.activeFocus ? button.accent
                    : button.flat ? "transparent" : button.primary ? button.primaryColor : "#DDE3DD"
        Behavior on color { enabled: button.motion; ColorAnimation { duration: 100 } }
    }
}
