import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    text: "已读完"
    spacing: 5
    leftPadding: 7; rightPadding: 8; topPadding: 4; bottomPadding: 4
    implicitHeight: 32
    hoverEnabled: true
    Accessible.name: checked ? "已读完，点击取消" : "手动标记已读完"
    background: Rectangle {
        radius: 6
        color: control.checked ? settings.palette.selection : control.hovered ? settings.palette.page : "transparent"
        border.color: control.activeFocus ? settings.palette.accent : "transparent"
    }
    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height-height)/2
        implicitWidth: 18; implicitHeight: 18; radius: 4
        color: control.checked ? settings.palette.accent : "transparent"
        border.width: control.activeFocus ? 2 : 1
        border.color: control.checked || control.hovered || control.activeFocus ? settings.palette.accent : "#7B8981"
        Text { anchors.centerIn: parent; text: "✓"; visible: control.checked; color: "white"; font.pixelSize: 13; font.weight: Font.DemiBold }
    }
    contentItem: Text {
        text: control.text
        leftPadding: control.indicator.width+control.spacing
        verticalAlignment: Text.AlignVCenter
        color: control.checked ? settings.palette.accent : "#7B8981"
        font.pixelSize: 11
    }
    ToolTip.visible: hovered
    ToolTip.text: checked ? "已读完，点击取消" : "读完后手动打勾"
}
