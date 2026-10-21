import QtQuick
import QtQuick.Layouts

RowLayout {
    id: progress
    property string label: ""
    property string detail: ""
    property real value: 0
    property color tint: settings.palette.accent
    spacing: 7
    height: 14
    Text { text: progress.label; color: "#7B8981"; font.pixelSize: 10 }
    Rectangle {
        Layout.fillWidth: true; Layout.maximumWidth: 180; Layout.minimumWidth: 24
        height: 5; radius: 2.5; color: "#E3EBE6"
        Rectangle { height: parent.height; radius: parent.radius; width: parent.width * Math.max(0, Math.min(1, progress.value)); color: progress.tint }
    }
    Text { text: progress.detail; color: progress.value > 0 ? progress.tint : "#7B8981"; font.pixelSize: 10; Layout.preferredWidth: 86; elide: Text.ElideRight }
    Item { Layout.fillWidth: true }
}
