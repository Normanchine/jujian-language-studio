import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Menu {
    id: menu
    property var editor
    popupType: Popup.Item
    width: 220; padding: 6; margins: 8
    overlap: 0
    readonly property bool hasSelection: !!editor && editor.selectedText.length > 0
    readonly property bool editable: !!editor && !editor.readOnly
    component Entry: MenuItem {
        id: entry
        property string shortcutLabel: ""
        implicitHeight: 34; leftPadding: 11; rightPadding: 10
        hoverEnabled: true
        contentItem: RowLayout {
            spacing: 24
            Text { text: entry.text; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                color: entry.enabled ? "#304137" : "#A9B3AC"; Layout.fillWidth: true }
            Text { text: entry.shortcutLabel; font.family: "Segoe UI"; font.pixelSize: 11
                color: entry.enabled ? "#87978C" : "#BCC4BE" }
        }
        background: Rectangle {
            x: 1; y: 1; width: entry.width-2; height: entry.height-2; radius: 7
            color: entry.enabled && (entry.highlighted || entry.hovered) ? settings.palette.selection : "transparent"
        }
    }
    component Divider: MenuSeparator {
        implicitHeight: 10; leftPadding: 10; rightPadding: 10
        contentItem: Rectangle { implicitHeight: 1; color: "#E7ECE8" }
    }
    background: Rectangle {
        radius: 11; color: settings.palette.surface; border.color: "#D8E2DB"
        Rectangle { z: -1; anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: -3; radius: 11; color: "#0D263D30" }
    }
    Entry { objectName: "textMenuUndo"; text: "撤销"; shortcutLabel: "Ctrl+Z"; enabled: menu.editable && menu.editor.canUndo
        onTriggered: { menu.editor.undo(); menu.editor.forceActiveFocus() } }
    Entry { objectName: "textMenuRedo"; text: "重做"; shortcutLabel: "Ctrl+Y"; enabled: menu.editable && menu.editor.canRedo
        onTriggered: { menu.editor.redo(); menu.editor.forceActiveFocus() } }
    Divider { }
    Entry { objectName: "textMenuCut"; text: "剪切"; shortcutLabel: "Ctrl+X"; enabled: menu.editable && menu.hasSelection
        onTriggered: { menu.editor.cut(); menu.editor.forceActiveFocus() } }
    Entry { objectName: "textMenuCopy"; text: "复制"; shortcutLabel: "Ctrl+C"; enabled: menu.hasSelection
        onTriggered: { menu.editor.copy(); menu.editor.forceActiveFocus() } }
    Entry { objectName: "textMenuPaste"; text: "粘贴"; shortcutLabel: "Ctrl+V"; enabled: menu.editable && menu.editor.canPaste
        onTriggered: { menu.editor.paste(); menu.editor.forceActiveFocus() } }
    Entry { objectName: "textMenuDelete"; text: "删除"; shortcutLabel: "Del"; enabled: menu.editable && menu.hasSelection
        onTriggered: { menu.editor.remove(menu.editor.selectionStart,menu.editor.selectionEnd); menu.editor.forceActiveFocus() } }
    Divider { }
    Entry { objectName: "textMenuSelectAll"; text: "全选"; shortcutLabel: "Ctrl+A"; enabled: !!menu.editor && menu.editor.length > 0
        onTriggered: { menu.editor.selectAll(); menu.editor.forceActiveFocus() } }
}
