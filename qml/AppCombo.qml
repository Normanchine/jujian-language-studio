import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: 36
    implicitWidth: 128
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    contentItem: Text {
        leftPadding: 12; rightPadding: 27
        text: control.displayText
        color: control.enabled ? "#26342C" : "#9DA7A0"
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width - 23
        anchors.verticalCenter: parent.verticalCenter
        text: "⌄"; color: "#6D7A71"; font.pixelSize: 17
    }
    background: Rectangle {
        radius: 8; color: control.pressed ? "#F8EFF1" : "#FFFFFF"
        border.color: control.activeFocus ? "#C94859" : "#DCE4DE"
    }
    delegate: ItemDelegate {
        width: control.width
        text: control.textRole ? modelData[control.textRole] : modelData
        font: control.font
        highlighted: control.highlightedIndex === index
        background: Rectangle { color: parent.highlighted ? "#F9E9ED" : "#FFFFFF" }
    }
    popup: Popup {
        y: control.height + 4; width: control.width
        implicitHeight: Math.min(260, contentItem.implicitHeight + 8)
        padding: 4
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
        background: Rectangle { radius: 8; color: "#FFFFFF"; border.color: "#DCE4DE" }
    }
}
