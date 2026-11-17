import QtQuick
import QtQuick.Controls

TextField {
    id: field
    implicitHeight: 40
    leftPadding: 12; rightPadding: 12
    color: "#33463B"; placeholderTextColor: "#99A59C"
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    selectByMouse: true; hoverEnabled: true
    selectionColor: settings.palette.selection; selectedTextColor: "#26342C"
    background: Rectangle {
        radius: 8; color: field.enabled ? settings.palette.surface : settings.palette.page
        border.color: field.activeFocus ? settings.palette.accent : "#DCE4DE"
    }
    ContextMenu.menu: AppTextMenu { editor: field }
}
