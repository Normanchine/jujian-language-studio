import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: chip
    property string heading: ""
    property string subtitle: ""
    property bool selected: false
    implicitWidth: 140
    implicitHeight: 64
    hoverEnabled: true
    Accessible.name: heading+" "+subtitle
    Accessible.checkable: true
    Accessible.checked: selected
    contentItem: ColumnLayout {
        spacing: 3
        Text { text: chip.heading;color: chip.selected ? "#FFFFFF" : "#34483B";font.family: "Microsoft YaHei UI";font.pixelSize: 14;Layout.alignment: Qt.AlignHCenter }
        Text { text: chip.subtitle;color: chip.selected ? "#E5F0E9" : "#7C8A80";font.family: "Microsoft YaHei UI";font.pixelSize: 11;Layout.alignment: Qt.AlignHCenter }
    }
    background: Rectangle {
        radius: 9
        color: chip.selected ? settings.palette.accent : chip.hovered ? settings.palette.selection : settings.palette.page
        border.color: chip.selected ? settings.palette.accent : chip.hovered ? "#C3D5C8" : "#E3EAE5"
        Behavior on color { enabled: uiAnimationsEnabled;ColorAnimation { duration: 110 } }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
