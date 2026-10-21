import QtQuick

Item {
    id: hook
    anchors.fill: parent
    property var editor: parent
    signal noteRequested(var source)
    signal selectionCleared(var source)
    function schedule() {
        if (!editor.selectedText || !editor.selectedText.trim()) {
            selectionCleared(editor)
            return
        }
        if (!pointer.active) settle.restart()
    }
    // A passive pointer observer leaves the editor's native drag selection intact.
    PointHandler {
        id: pointer
        acceptedButtons: Qt.LeftButton
        onActiveChanged: {
            if (active) { settle.stop(); hook.selectionCleared(hook.editor) }
            else hook.schedule()
        }
    }
    Connections {
        target: hook.editor
        function onSelectedTextChanged() { hook.schedule() }
        function onVisibleChanged() { if (!hook.editor.visible) hook.selectionCleared(hook.editor) }
    }
    Timer {
        id: settle; interval: 100
        onTriggered: if (hook.editor.visible && hook.editor.selectedText.trim() && !pointer.active)
            hook.noteRequested(hook.editor)
    }
}
