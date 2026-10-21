import QtQuick

TextEdit {
    id: source
    required property var reader
    property int paragraphIndex: 0
    property string sourceText: ""
    readonly property bool selectionDragging: dragObserver.active
    function sourceOffset(position) {return position;}
    function displayOffset(position) {return position;}
    property var selectedRange: {
        var start=selectionStart,end=selectionEnd;
        while (start<end && /\s/.test(sourceText.charAt(start))) start++;
        while (end>start && /\s/.test(sourceText.charAt(end-1))) end--;
        return {start:start,end:end};
    }
    function selectionActionContains(sceneX,sceneY) {
        return saveSelection.visible && saveSelection.contains(saveSelection.mapFromItem(null,sceneX,sceneY));
    }
    text: reader.render(sourceText,paragraphIndex)
    textFormat: TextEdit.RichText
    wrapMode: TextEdit.Wrap
    height: implicitHeight
    readOnly: true;selectByMouse: true;persistentSelection: true
    font.family: "Cambria";font.pixelSize: 22
    color: reader.ink;selectionColor: settings.palette.selection;selectedTextColor: reader.ink
    onSelectedTextChanged: {
        if (selectedText.trim()) {
            if (reader.selectionEditor && reader.selectionEditor!==source) reader.selectionEditor.deselect();
            reader.selectionEditor=source;
        }
        else if (reader.selectionEditor===source) reader.selectionEditor=null;
    }
    onLinkActivated: function(link) {
        reader.activate(link);
        Qt.callLater(source.deselect);
    }
    Keys.onPressed: function(event) {
        if ((event.modifiers & Qt.ControlModifier) && event.key===Qt.Key_C) {
            reader.assistant.copyText(selectedText);event.accepted=true;
        }
    }
    PointHandler { id: dragObserver;acceptedButtons: Qt.LeftButton;cursorShape: Qt.IBeamCursor }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: function(eventPoint) {source.reader.removeWordForLink(source.linkAt(eventPoint.position.x,eventPoint.position.y));}
    }
    HoverHandler { cursorShape: dragObserver.active ? Qt.IBeamCursor : hovered && source.linkAt(point.position.x,point.position.y).length>0 ? Qt.PointingHandCursor : Qt.IBeamCursor }
    AppButton {
        id: saveSelection;objectName: "englishSaveSentence_"+source.paragraphIndex
        visible: source.selectedText.trim().length>0 && !source.selectionDragging
        property bool saved: source.reader.isSaved("sentence",source.paragraphIndex,source.selectedRange.start,source.selectedRange.end)
        property rect endBox: source.positionToRectangle(source.selectionEnd)
        x: Math.max(0,Math.min(source.width-width,endBox.x));y: endBox.y+endBox.height+3;z: 20
        implicitHeight: 32;text: saved ? "★ 已收藏选句" : "☆ 收藏选句"
        onClicked: source.reader.assistant.toggleSentenceFavorite(source.paragraphIndex,source.selectedRange.start,source.selectedRange.end)
    }
    function markerSegments(start,end) {
        // Group actual character rectangles so wrapped phrases get one stroke per line.
        var geometry=width+height+contentHeight+text.length;
        var segments=[];
        for (var i=start;i<end;i++) {
            var box=positionToRectangle(displayOffset(i)),after=positionToRectangle(displayOffset(i+1));
            var right=after.y===box.y ? after.x : box.x+font.pixelSize*0.5;
            if (right<=box.x) continue;
            var last=segments.length ? segments[segments.length-1] : null;
            if (last && Math.abs(last.y-(box.y+box.height-5))<1) last.width=Math.max(last.width,right-last.x);
            else segments.push({x:box.x,y:box.y+box.height-5,width:right-box.x});
        }
        return segments;
    }
    Repeater {
        model: source.reader.underlines ? source.reader.vocabulary.paragraphs[source.paragraphIndex] || [] : []
        delegate: Item {
            required property var modelData
            property var strokes: source.markerSegments(modelData.start,modelData.end)
            z: -1
            Repeater {
                model: parent.strokes
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    objectName: "englishWordMarker_"+parent.modelData.id+"_"+index
                    x: modelData.x;y: modelData.y;width: modelData.width;height: 5;radius: 1.5
                    color: settings.palette.accent
                    opacity: source.reader.activeWordId===parent.modelData.id ? 0.58 : 0.26
                }
            }
        }
    }
}
