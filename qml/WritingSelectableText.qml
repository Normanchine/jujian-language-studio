import QtQuick

TextEdit {
    id: textItem
    readOnly: true
    selectByMouse: true
    persistentSelection: true
    wrapMode: TextEdit.Wrap
    textFormat: TextEdit.PlainText
    selectionColor: settings.palette.selection
    selectedTextColor: "#26342C"
    signal noteRequested(var source)
    signal selectionCleared(var source)
    WritingSelectionHook {
        onNoteRequested: function(source) { textItem.noteRequested(source) }
        onSelectionCleared: function(source) { textItem.selectionCleared(source) }
    }
}
