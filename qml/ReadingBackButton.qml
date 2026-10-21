import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: button
    text: "返回"
    implicitWidth: 84
    implicitHeight: 38
    hoverEnabled: true
    Accessible.name: "返回阅读"
    contentItem: RowLayout {
        spacing: 7
        NavGlyph { kind: "back";width: 18;height: 18;active: true;activeColor: "#52695B";Layout.alignment: Qt.AlignVCenter }
        Text { text: button.text;font.family: "Microsoft YaHei UI";font.pixelSize: 13;font.weight: Font.Normal;color: "#425B4B";Layout.alignment: Qt.AlignVCenter }
        Item { Layout.fillWidth: true }
    }
    leftPadding: 12
    rightPadding: 12
    background: Rectangle {
        radius: 9;color: button.down ? "#DCE9DF" : button.hovered ? settings.palette.selection : settings.palette.surface
        border.color: button.hovered ? "#CBDBD0" : "#DDE6DF"
        Behavior on color { enabled: uiAnimationsEnabled;ColorAnimation { duration: 100 } }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
