import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var entry
    property bool compact: false
    signal opened(string path)
    signal removed(string path, string title)
    implicitHeight: compact ? 72 : 80
    radius: 9; color: hover.containsMouse ? settings.palette.selection : settings.palette.page
    border.color: "#E3E9E3"
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true
        cursorShape: Qt.PointingHandCursor; onClicked: card.opened(card.entry.path) }
    Column {
        x: 14; y: 12; width: parent.width - (card.compact ? 28 : 146); spacing: 6
        Text { width: parent.width; text: card.entry.title; elide: Text.ElideRight
            color: "#26342C"; font.pixelSize: 14; font.weight: Font.DemiBold }
        Text { width: parent.width; text: card.entry.preview || "空白草稿，点击继续写作"; elide: Text.ElideRight
            color: "#718077"; font.pixelSize: 12 }
        Text { visible: !card.compact; width: parent.width; elide: Text.ElideRight
            text: (card.entry.language === "ja" ? "日语" : "英语") + " · " + card.entry.updatedLabel
                  + (card.entry.reviewed ? " · 已有批改" : " · 待批改")
            color: "#89958C"; font.pixelSize: 11 }
    }
    Row { visible: !card.compact; anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 1
        AppButton { text: card.entry.favorite ? "★" : "☆"; flat: true
            onClicked: writer.toggleDraftFavorite(card.entry.path) }
        AppButton { text: "删除"; flat: true; onClicked: card.removed(card.entry.path, card.entry.title) }
    }
}
