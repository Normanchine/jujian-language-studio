import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ComboBox {
    id: control
    property color accent: settings.values.theme === "classic" ? "#4E8068" : settings.palette.accent
    property color selection: settings.palette.selection
    implicitHeight: 36
    implicitWidth: 128
    hoverEnabled: true
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
    indicator: Canvas {
        x: control.width - 26; width: 12; height: 8
        anchors.verticalCenter: parent.verticalCenter
        onPaint: {
            var ctx=getContext("2d");ctx.clearRect(0,0,width,height)
            ctx.strokeStyle=control.enabled ? "#748178" : "#B0B9B2";ctx.lineWidth=1.5
            ctx.lineCap="round";ctx.lineJoin="round";ctx.beginPath();ctx.moveTo(2,2);ctx.lineTo(6,6);ctx.lineTo(10,2);ctx.stroke()
        }
        Connections { target: control; function onEnabledChanged() { control.indicator.requestPaint() } }
    }
    background: Rectangle {
        radius: 8; color: !control.enabled ? settings.palette.page : control.pressed ? control.selection
                        : control.hovered ? settings.palette.page : settings.palette.surface
        border.color: control.activeFocus || control.popup.visible ? control.accent : "#DCE4DE"
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width - 12; height: 38
        text: control.textRole ? modelData[control.textRole] : modelData
        font: control.font
        highlighted: control.highlightedIndex === index
        hoverEnabled: true
        contentItem: RowLayout {
            spacing: 8
            Text { Layout.fillWidth: true; text: control.textRole ? modelData[control.textRole] : modelData
                font: control.font; color: "#33463B"; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
            Text { text: "✓"; font.pixelSize: 13; color: control.accent; opacity: index===control.currentIndex ? 1 : 0 }
        }
        background: Rectangle { radius: 6; color: parent.highlighted || parent.hovered ? control.selection
                                             : index===control.currentIndex ? settings.palette.page : "transparent" }
    }
    popup: Popup {
        y: control.height + 4; width: control.width
        implicitHeight: Math.min(260, contentItem.implicitHeight + 12)
        padding: 6
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            spacing: 2
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 5
                background: Item {}
                contentItem: Rectangle { implicitWidth: 4; radius: 2; color: "#B8C7BC" } }
        }
        background: Rectangle { radius: 10; color: settings.palette.surface; border.color: "#DCE4DE" }
    }
}
