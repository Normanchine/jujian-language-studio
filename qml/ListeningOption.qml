import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: option
    property string letter: "A"
    property bool chosen: false
    property bool motion: typeof uiAnimationsEnabled !== "undefined" && uiAnimationsEnabled
    hoverEnabled: true; focusPolicy: Qt.StrongFocus
    implicitHeight: Math.max(56, optionText.implicitHeight + 26)
    implicitWidth: 600
    leftPadding: 16; rightPadding: 16; topPadding: 13; bottomPadding: 13
    scale: down ? 0.993 : 1
    Behavior on scale { enabled: option.motion; NumberAnimation { duration: 85; easing.type: Easing.OutCubic } }
    Accessible.name: letter + ". " + text
    background: Rectangle {
        radius: 11
        color: option.chosen ? settings.palette.selection : option.hovered ? settings.palette.page : settings.palette.surface
        border.width: option.chosen ? 1.5 : 1
        border.color: option.chosen ? settings.palette.accent : option.activeFocus ? "#9FAFA4" : option.hovered ? "#B7C8BC" : "#DDE6DF"
        Behavior on color { enabled: option.motion; ColorAnimation { duration: 130 } }
        Behavior on border.color { enabled: option.motion; ColorAnimation { duration: 130 } }
    }
    contentItem: RowLayout {
        spacing: 14
        Rectangle {
            Layout.preferredWidth: 28; Layout.preferredHeight: 28; radius: 7
            color: option.chosen ? settings.palette.accent : settings.palette.page
            Behavior on color { enabled: option.motion; ColorAnimation { duration: 130 } }
            Text { anchors.centerIn: parent; text: option.letter; color: option.chosen ? "#FFFFFF" : "#718077"; font.pixelSize: 13; font.weight: Font.DemiBold }
        }
        Text { id: optionText; Layout.fillWidth: true; text: option.text; textFormat: Text.PlainText
            wrapMode: Text.Wrap; font.family: "Georgia"; font.pixelSize: 17; color: "#26372D"; lineHeight: 1.2 }
        Rectangle {
            Layout.preferredWidth: 17; Layout.preferredHeight: 17; radius: 9
            color: "transparent"; border.color: option.chosen ? settings.palette.accent : "#C6D3CA"
            Rectangle { anchors.centerIn: parent; width: 9; height: 9; radius: 5; color: settings.palette.accent
                opacity: option.chosen ? 1 : 0; scale: option.chosen ? 1 : 0.5
                Behavior on opacity { enabled: option.motion; NumberAnimation { duration: 120 } }
                Behavior on scale { enabled: option.motion; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } } }
        }
    }
}
