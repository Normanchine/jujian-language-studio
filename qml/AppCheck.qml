import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    spacing: 9
    leftPadding: 6; rightPadding: 9; topPadding: 6; bottomPadding: 6
    hoverEnabled: true
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    implicitWidth: label.implicitWidth + leftPadding + rightPadding
    implicitHeight: Math.max(36, label.implicitHeight + topPadding + bottomPadding)
    readonly property bool motion: typeof uiAnimationsEnabled !== "undefined" && uiAnimationsEnabled
    property color accent: settings.palette.accent
    opacity: enabled ? 1 : 0.5
    background: Rectangle {
        radius: 7
        color: control.hovered ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.055) : "transparent"
        border.color: control.activeFocus ? settings.palette.accent : "transparent"
        Behavior on color { enabled: control.motion; ColorAnimation { duration: 110 } }
    }
    indicator: Rectangle {
        x: control.leftPadding; y: (control.height-height)/2
        implicitWidth: 18; implicitHeight: 18; radius: 5
        color: control.checked ? settings.palette.accent : settings.palette.surface
        border.width: 1
        border.color: control.checked || control.hovered ? settings.palette.accent : "#C1CEC5"
        Behavior on color { enabled: control.motion; ColorAnimation { duration: 120 } }
        Behavior on border.color { enabled: control.motion; ColorAnimation { duration: 120 } }
        Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: Font.DemiBold
            opacity: control.checked ? 1 : 0; scale: control.checked ? 1 : 0.75
            Behavior on opacity { enabled: control.motion; NumberAnimation { duration: 100 } }
            Behavior on scale { enabled: control.motion; NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Text {
        id: label
        text: control.text; font: control.font; textFormat: Text.PlainText; wrapMode: Text.Wrap
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter; color: control.enabled ? "#33463B" : "#94A198"
    }
}
