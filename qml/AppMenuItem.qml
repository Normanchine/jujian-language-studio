import QtQuick
import QtQuick.Controls

MenuItem {
    id: item
    implicitHeight: 38; leftPadding: 12; rightPadding: 12
    hoverEnabled: true
    contentItem: Text {
        text: item.text; textFormat: Text.PlainText
        font.family: "Microsoft YaHei UI"; font.pixelSize: 13
        color: !item.enabled ? "#A0AAA2" : "#33463B"
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    background: Rectangle {
        x: 1; y: 1; width: item.width-2; height: item.height-2; radius: 6
        color: item.enabled && (item.highlighted || item.hovered) ? settings.palette.selection : "transparent"
    }
}
