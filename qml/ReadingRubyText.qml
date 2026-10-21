import QtQuick

TextEdit {
    id: paragraphText
    required property var reader
    property int paragraphIndex: 0
    property string sourceText: ""
    property var liveLayout: paragraphIndex===-1 ? reader.assistance.titleLayout : reader.assistance.layout[paragraphIndex] || ({ruby:[],joiners:[]})
    property bool renderingFrozen: false
    property string displayedHtml: ""
    property string liveHtml: reader.render(sourceText,paragraphIndex)
    property var layoutData: ({ruby:[],joiners:[]})
    function refreshRendering() {
        if (reader && !renderingFrozen) {displayedHtml=liveHtml;layoutData=liveLayout;}
    }
    onLiveHtmlChanged: refreshRendering()
    onLiveLayoutChanged: refreshRendering()
    Component.onCompleted: refreshRendering()
    property bool rubyVisible: reader.article.language === "ja" && reader.assistance.preferences.furigana
    property var breaks: rubyVisible ? layoutData.joiners : []
    property bool queryGesture: false
    property bool dragMoved: false
    property bool gestureCancelled: false
    readonly property bool selectionDragging: pointer.active
    property point pressPoint
    function displayOffset(source) {
        var added=0;
        for (var i=0;i<breaks.length;i++) if (breaks[i]<=source) added++; else break;
        return source+added;
    }
    function sourceOffset(display) {
        var added=0;
        for (var i=0;i<breaks.length;i++) if (breaks[i]+i<display) added++; else break;
        return display-added;
    }
    text: displayedHtml
    textFormat: TextEdit.RichText
    wrapMode: TextEdit.Wrap
    height: implicitHeight
    readOnly: true
    selectByMouse: true
    persistentSelection: true
    color: reader.ink
    selectionColor: pointer.active ? settings.palette.selection : Qt.darker(settings.palette.selection,1.08)
    Behavior on selectionColor { enabled: uiAnimationsEnabled;ColorAnimation { duration: 110 } }
    selectedTextColor: reader.ink
    font.family: reader.article.language === "en" ? "Georgia" : "Yu Gothic UI"
    font.pixelSize: 19
    onLinkActivated: function(link) { if (!queryGesture && !reader.gesture.held) reader.activate(link); }
    onSelectedTextChanged: {
        if (paragraphIndex<0) return;
        if (selectedText.replace(/\u2060/g,"").trim()) {
            if (reader.selectionEditor!==paragraphText) reader.selectionEditor=paragraphText;
        }
        else if (reader.selectionEditor===paragraphText) reader.selectionEditor=null;
    }
    Keys.onPressed: function(event) {
        if ((event.modifiers & Qt.ControlModifier) && event.key===Qt.Key_C) {
            reader.assistant.copyText(selectedText);event.accepted=true;
        }
    }
    HoverHandler {
        id: textHover
        objectName: "readingTextHover_"+paragraphText.paragraphIndex
        cursorShape: reader.gesture.held || pointer.active ? Qt.IBeamCursor : hovered && paragraphText.linkAt(point.position.x,point.position.y).length>0 ? Qt.PointingHandCursor : Qt.IBeamCursor
    }
    PointHandler {
        id: pointer
        acceptedButtons: Qt.LeftButton
        enabled: paragraphText.paragraphIndex>=0
        cursorShape: Qt.IBeamCursor
        onActiveChanged: {
            if (active) {
                paragraphText.renderingFrozen=true;
                paragraphText.gestureCancelled=false;
                settle.stop();paragraphText.pressPoint=point.position;
                paragraphText.dragMoved=false;paragraphText.queryGesture=reader.gesture.held;
                reader.gesture.setQueryDragging(paragraphText.queryGesture);
                // A previous query must not leave a draggable native selection
                // under the next press, even when it is in the same paragraph.
                if (reader.selectionEditor && (reader.selectionEditor!==paragraphText || paragraphText.queryGesture)) reader.selectionEditor.deselect();
            } else settle.restart();
        }
        onPointChanged: {
            if (active && !paragraphText.gestureCancelled && reader.gesture.held) paragraphText.queryGesture=true;
            if (active) reader.gesture.setQueryDragging(paragraphText.queryGesture);
            if (active && (Math.abs(point.position.x-paragraphText.pressPoint.x)>3 || Math.abs(point.position.y-paragraphText.pressPoint.y)>3)) paragraphText.dragMoved=true;
        }
        onCanceled: { reader.gesture.setQueryDragging(false);paragraphText.gestureCancelled=true;paragraphText.queryGesture=false;paragraphText.dragMoved=false;paragraphText.renderingFrozen=false;paragraphText.refreshRendering();settle.stop(); }
    }
    Timer {
        id: settle;interval: 0
        onTriggered: {
            var start=paragraphText.selectionStart,end=paragraphText.selectionEnd;
            var refresh=paragraphText.displayedHtml!==paragraphText.liveHtml;
            var submit=!paragraphText.gestureCancelled && paragraphText.queryGesture && paragraphText.dragMoved && paragraphText.visible && paragraphText.selectedText.trim();
            // End this gesture before lookup emits updates or changes focus.
            paragraphText.queryGesture=false;
            reader.gesture.setQueryDragging(false);
            paragraphText.dragMoved=false;
            if (submit) reader.queryEditor(paragraphText);
            paragraphText.renderingFrozen=false;
            paragraphText.refreshRendering();
            if (submit) paragraphText.deselect();
            else if (refresh && start!==end) paragraphText.select(start,end);
        }
    }
    Connections { target: reader.gesture
        function onCancelled() {paragraphText.gestureCancelled=true;paragraphText.queryGesture=false;paragraphText.dragMoved=false;paragraphText.renderingFrozen=false;paragraphText.refreshRendering();settle.stop();}
        function onChanged() {
            // Accept the modifier throughout the drag, including a key event that
            // arrives just after the mouse press. Keep it latched until release.
            if (pointer.active && !paragraphText.gestureCancelled && reader.gesture.held) paragraphText.queryGesture=true;
            if (pointer.active) reader.gesture.setQueryDragging(paragraphText.queryGesture);
            if (textHover.hovered) reader.gesture.syncTextCursor(paragraphText,
                reader.gesture.held || pointer.active ? Qt.IBeamCursor : paragraphText.linkAt(textHover.point.position.x,textHover.point.position.y).length>0 ? Qt.PointingHandCursor : Qt.IBeamCursor);
        }
    }
    Repeater {
        model: paragraphText.rubyVisible ? paragraphText.layoutData.ruby : []
        delegate: Text {
            required property var modelData
            objectName: "readingRuby_"+paragraphText.paragraphIndex+"_"+modelData.start
            property rect first: {
                var geometry=paragraphText.width+paragraphText.contentHeight+paragraphText.text.length;
                return paragraphText.positionToRectangle(paragraphText.displayOffset(modelData.start));
            }
            property rect last: {
                var geometry=paragraphText.width+paragraphText.contentHeight+paragraphText.text.length;
                return paragraphText.positionToRectangle(paragraphText.displayOffset(modelData.end)-1);
            }
            property rect after: {
                var geometry=paragraphText.width+paragraphText.contentHeight+paragraphText.text.length;
                return paragraphText.positionToRectangle(paragraphText.displayOffset(modelData.end));
            }
            x: first.x
            y: first.y-14
            width: Math.max(1,(after.y===first.y ? after.x : last.x+paragraphText.font.pixelSize)-first.x)
            height: 13
            visible: Math.abs(first.y-last.y)<2
            text: modelData.reading
            color: reader.muted
            font.family: "Yu Gothic UI"
            font.pixelSize: 11
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 8
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignBottom
            z: 2
        }
    }
}
