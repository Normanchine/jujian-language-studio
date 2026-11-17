import QtQuick
import QtQuick.Controls

Menu {
    popupType: Popup.Item
    width: 200; padding: 6; margins: 10
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    background: Rectangle {
        radius: 10; color: settings.palette.surface
        border.color: "#DCE4DE"
        Rectangle { z: -1; x: 0; y: 3; width: parent.width; height: parent.height
            radius: 10; color: "#10263D30" }
    }
}
