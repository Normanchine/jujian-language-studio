import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "readingEnglishPage"
    required property var reader
    readonly property var article: reader.article
    readonly property var assistant: reader.assistant
    readonly property var gesture: reader.gesture
    readonly property var assistance: assistant.view
    readonly property var vocabularyBridge: assistant.english
    readonly property var vocabulary: vocabularyBridge.view
    readonly property var saved: assistant.saved.view
    readonly property var paragraphs: (article.body || "").split(/\n\s*\n/)
    property color ink: "#303B34"
    property color muted: "#7F897F"
    property bool underlines: true
    property bool sideNotes: width>=760
    property var selectionEditor: null
    property var selectedWords: ({})
    property string activeWordId: ""
    property var expandedTranslations: ({})
    property bool allTranslations: false
    property bool restoring: false
    signal wordChosen(int paragraph,string wordId)
    signal wordRemoved(int paragraph,string wordId)

    function htmlEscape(value) {return String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
    function render(text,paragraph) {
        // Keep links independent from lookup results: adding a card must not
        // rebuild the native text document underneath the completed click.
        var pattern=/[A-Za-z]+(?:['’\-][A-Za-z]+)*/g,match,previous=0,result="";
        while ((match=pattern.exec(text))!==null) {
            var left=match.index,right=left+match[0].length;
            result+=htmlEscape(text.slice(previous,left));
            result+='<a href="lookup:'+paragraph+':'+left+':'+right+'" style="color:'+page.ink+';text-decoration:none">'+htmlEscape(match[0])+'</a>';
            previous=right;
        }
        return '<p style="line-height:165%;margin:0">'+result+htmlEscape(text.slice(previous))+'</p>';
    }
    function chooseWord(word) {
        if (selectionEditor) selectionEditor.deselect();
        var next=Object.assign({},selectedWords);next[word.paragraph]=word.id;selectedWords=next;
        activeWordId=word.id;wordChosen(word.paragraph,word.id);
        Qt.callLater(function() {if (page.selectionEditor && !page.selectionEditor.selectionDragging) page.selectionEditor.deselect();});
    }
    function activate(link) {
        if (link.indexOf("lookup:")===0) {
            var parts=link.split(":"),p=Number(parts[1]),start=Number(parts[2]),end=Number(parts[3]);
            var existing=(vocabulary.paragraphs[p] || []).find(function(w) {return w.start===start && w.end===end;});
            if (existing) chooseWord(existing);
            else queryWord({id:"en_"+p+"_"+start+"_"+end,paragraph:p,start:start,end:end,text:paragraphs[p].slice(start,end)});
            return;
        }
        var id=link.slice(5);
        for (var i=0;i<vocabulary.paragraphs.length;i++) {
            var word=vocabulary.paragraphs[i].find(function(w) {return w.id===id;});
            if (word) {chooseWord(word);return;}
        }
    }
    function queryWord(word) {
        chooseWord(word);assistant.lookup(word.paragraph,word.start,word.end,"word");
    }
    function removeWordForLink(link) {
        if (link.indexOf("lookup:")!==0) return;
        var parts=link.split(":"),p=Number(parts[1]),start=Number(parts[2]),end=Number(parts[3]);
        var word=(vocabulary.paragraphs[p] || []).find(function(w) {return w.start===start && w.end===end;});
        removeLookupWord(word);
    }
    function removeLookupWord(word) {
        if (!word || !word.canRemove) return;
        if (!vocabularyBridge.removeLookup(word.id)) return;
        var next=Object.assign({},selectedWords);
        if (next[word.paragraph]===word.id) delete next[word.paragraph];
        selectedWords=next;
        if (activeWordId===word.id) activeWordId="";
        wordRemoved(word.paragraph,word.id);
    }
    function queryEditor(editor) {
        if (!editor || !editor.selectedText.trim()) return;
        var start=editor.sourceOffset(editor.selectionStart),end=editor.sourceOffset(editor.selectionEnd),p=editor.paragraphIndex;
        assistant.lookup(p,start,end,"word");
        chooseWord({id:"en_"+p+"_"+start+"_"+end,paragraph:p});
    }
    function clearSelection() {
        if (selectionEditor) selectionEditor.deselect();
        activeWordId="";
    }
    function isSaved(kind,paragraph,start,end) {return !!saved.currentIds[kind+":"+paragraph+":"+start+":"+end];}
    function focusFavorite(item) {
        passage.positionViewAtIndex(item.paragraph,ListView.Center);
        Qt.callLater(function() {
            var block=passage.itemAtIndex(item.paragraph);
            if (!block) return;
            block.sourceEditor.select(item.start,item.end);
            if (item.kind==="word") {
                var word=(page.vocabulary.paragraphs[item.paragraph] || []).find(function(a) {return a.start===item.start && a.end===item.end;});
                if (word) page.chooseWord(word);
            }
        });
    }
    Connections {
        target: page.gesture
        function onPointerPressed(sceneX,sceneY) {
            if (page.selectionEditor && page.selectionEditor.selectionActionContains(sceneX,sceneY)) return;
            for (var i=0;i<passage.count;i++) {
                var block=passage.itemAtIndex(i);
                if (!block || !block.sourceEditor) continue;
                var editor=block.sourceEditor,local=editor.mapFromItem(null,sceneX,sceneY);
                if (editor.contains(local)) {
                    if (!editor.linkAt(local.x,local.y)) page.activeWordId="";
                    return;
                }
            }
            page.clearSelection();
        }
    }
    function translationOpen(index) {return allTranslations || !!expandedTranslations[index];}
    function toggleTranslation(index) {
        clearSelection();
        var next=Object.assign({},expandedTranslations);
        if (allTranslations) {for (var i=0;i<paragraphs.length;i++) next[i]=true;allTranslations=false;}
        next[index]=!next[index];expandedTranslations=next;
        if (next[index]) assistant.translateParagraph(index);
    }
    function savePosition() {
        if (restoring) return;
        var index=passage.indexAt(10,passage.contentY+10);
        reader.bookmarkEdited({position:Math.max(0,passage.contentY-passage.originY),readParagraph:Math.max(0,index)+1,
            paragraphCount:paragraphs.length,visited:Date.now()});
    }
    function restorePosition() {
        restoring=true;selectedWords=({});activeWordId="";expandedTranslations=({});allTranslations=false;
        Qt.callLater(function() {
            passage.forceLayout();
            passage.contentY=passage.originY+Math.max(0,Math.min(reader.record.position || 0,passage.contentHeight-passage.height));
            restoring=false;
        });
    }
    Component.onCompleted: restorePosition()
    onArticleChanged: restorePosition()

    ColumnLayout {
        anchors.fill: parent;spacing: 12
        RowLayout {
            Layout.fillWidth: true;spacing: 12
            ToolButton {objectName: "readingBack";text: "‹";implicitWidth: 34;implicitHeight: 34;font.pixelSize: 27
                Accessible.name: "返回";ToolTip.visible: hovered;ToolTip.text: "返回"
                background: Rectangle {radius: 6;color: parent.hovered ? settings.palette.selection : "transparent"}
                onClicked: {reader.savePosition();reader.backRequested();} }
            Text {text: "阅读  /  英语精读";font.pixelSize: 12;color: page.muted}
            Item { Layout.fillWidth: true }
            AppButton { objectName: "englishOpenSaved";text: "词句收藏";flat: true;onClicked: {reader.savePosition();reader.studyFavoritesRequested();} }
            ToolButton {objectName: "readingArticleFavorite";text: reader.favorite ? "★" : "☆";implicitWidth: 32;implicitHeight: 34;font.pixelSize: 21
                Accessible.name: reader.favorite ? "取消收藏文章" : "收藏文章"
                contentItem: Text {text: parent.text;font.pixelSize: 21;color: settings.palette.accent;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter}
                background: Rectangle {radius: 6;color: parent.hovered ? settings.palette.selection : "transparent"}
                ToolTip.visible: hovered;ToolTip.text: reader.favorite ? "取消收藏文章" : "收藏整篇文章";onClicked: reader.favoriteRequested() }
            AppButton { objectName: "readingEndReview";text: "完成阅读";flat: true;
                onClicked: {reader.savePosition();reader.bookmarkEdited({lastReviewed:Date.now(),reviewCount:(reader.record.reviewCount || 0)+1});reader.backRequested();} }
        }
        Text { visible: page.vocabulary.busy;text: "正在标注第 "+(page.vocabulary.active+1)+" / "+page.paragraphs.length+" 段…";
            color: page.muted;font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
        Text {visible: page.saved.status.indexOf("失败")>=0;text: page.saved.status;color: "#9A753E";font.pixelSize: 12;Layout.fillWidth: true;wrapMode: Text.Wrap}
        Rectangle {
            Layout.fillWidth: true;Layout.fillHeight: true;radius: 12;color: "#FCFDF9";border.color: "#DFE6DA"
            ListView {
                id: passage;objectName: "englishPassage"
                anchors.fill: parent;anchors.margins: page.sideNotes ? 28 : 18
                model: page.paragraphs;spacing: 48;clip: true;boundsBehavior: Flickable.StopAtBounds
                onMovementEnded: page.savePosition()
                ScrollBar.vertical: ScrollBar {policy: ScrollBar.AsNeeded;onPressedChanged: if (!pressed) page.savePosition()}
                header: Column {
                    width: passage.width-10;spacing: 12;bottomPadding: 26
                    Text { text: page.article.title || "";font.family: "Cambria";font.pixelSize: page.sideNotes ? 31 : 26;font.weight: Font.DemiBold;
                        color: page.ink;width: parent.width;wrapMode: Text.Wrap }
                    RowLayout {
                        width: parent.width;spacing: 4
                        Text {text: page.article.sourceLabel || page.article.setTitle || "";font.pixelSize: 11;color: page.muted;Layout.fillWidth: true;wrapMode: Text.Wrap}
                        AppButton {objectName: "englishVocabularyAnalyze";text: page.vocabulary.busy ? "标注中…" : page.vocabulary.failed ? "重试标注" : page.vocabulary.count ? "AI 词汇 · "+page.vocabulary.count : "AI 标注";
                            flat: true;enabled: !page.vocabulary.busy;onClicked: page.vocabularyBridge.analyze(false)}
                        AppButton {objectName: "englishUnderlineToggle";text: page.underlines ? "✓ 重点词" : "重点词";flat: true
                            checkable: true;checked: page.underlines;onToggled: page.underlines=checked}
                        AppButton {objectName: "englishTranslateAll";text: page.allTranslations ? "收起译文" : "显示译文";flat: true
                            onClicked: {page.allTranslations=!page.allTranslations;if (page.allTranslations) page.assistant.translateAll();else page.expandedTranslations=({});}}
                        ToolButton {id: more;objectName: "englishMore";text: "⋯";implicitWidth: 32;implicitHeight: 32;font.pixelSize: 21
                            Accessible.name: "更多阅读操作";onClicked: tools.open()
                            background: Rectangle {radius: 6;color: parent.hovered ? settings.palette.selection : "transparent"}
                            Menu {id: tools;y: more.height
                                MenuItem {objectName: "englishAutoVocabulary";text: "进入文章自动标注";checkable: true;checked: page.vocabulary.automatic;
                                    onTriggered: page.vocabularyBridge.setAutomatic(checked)}
                                MenuItem {objectName: "englishAnalyze";text: page.vocabulary.ready ? "重新标注词汇" : "标注重点词汇"
                                    enabled: !page.vocabulary.busy;onTriggered: page.vocabularyBridge.analyze(page.vocabulary.ready)}
                                MenuItem {text: "停止当前解析";enabled: page.vocabulary.busy || page.assistance.queryBusy || page.assistance.translationBusy>=0;onTriggered: page.assistant.cancel()}
                            }
                        }
                    }
                    Rectangle {width: parent.width;height: 1;color: "#E8EDE4"}
                }
                delegate: Column {
                    id: paragraphBlock
                    required property string modelData
                    required property int index
                    property alias sourceEditor: paragraphText
                    width: passage.width-10;spacing: 10
                    property var translation: page.assistance.translations[index] || ({text:"",status:""})
                    property var englishPage: page
                    Item {
                        width: parent.width
                        height: page.sideNotes ? Math.max(paragraphText.height,note.height) : paragraphText.height+16+note.height
                        ReadingEnglishText {
                            id: paragraphText;objectName: "englishParagraph_"+paragraphBlock.index
                            reader: page;paragraphIndex: paragraphBlock.index;sourceText: paragraphBlock.modelData
                            width: page.sideNotes ? parent.width-note.width-32 : parent.width
                            font.family: "Cambria";font.pixelSize: 22
                        }
                        ReadingWordNote {
                            id: note;page: paragraphBlock.englishPage;paragraphIndex: paragraphBlock.index
                            x: page.sideNotes ? parent.width-width : 0;y: page.sideNotes ? 0 : paragraphText.height+16
                            width: page.sideNotes ? 268 : parent.width
                            height: page.sideNotes ? Math.min(420,Math.max(340,paragraphText.height+40)) : 280
                            onWordClicked: function(word) {page.chooseWord(word);}
                        }
                    }
                    Item {
                        width: parent.width;height: 27
                        MouseArea {anchors.fill: parent;anchors.topMargin: -8;anchors.bottomMargin: -8;onClicked: page.clearSelection()}
                        AppButton { objectName: "englishTranslationToggle_"+paragraphBlock.index;text: page.translationOpen(paragraphBlock.index) ? "收起译文  ⌃" : "查看译文  ⌄";
                            flat: true;implicitHeight: 27;onClicked: page.toggleTranslation(paragraphBlock.index) }
                    }
                    Column {
                        visible: page.translationOpen(paragraphBlock.index);width: page.sideNotes ? paragraphText.width : parent.width;spacing: 8
                        TextEdit { visible: !!paragraphBlock.translation.text;text: '<p style="line-height:170%;margin:0">'+page.htmlEscape(paragraphBlock.translation.text)+'</p>';textFormat: TextEdit.RichText;
                            readOnly: true;selectByMouse: true;width: parent.width;height: contentHeight;
                            wrapMode: TextEdit.Wrap;font.pixelSize: 15;color: "#617362" }
                        Text { visible: !!paragraphBlock.translation.status;text: paragraphBlock.translation.status;color: page.muted;font.pixelSize: 11;width: parent.width;wrapMode: Text.Wrap }
                        AppButton { visible: !paragraphBlock.translation.text && page.assistance.translationBusy!==paragraphBlock.index && page.assistance.translationQueued.indexOf(paragraphBlock.index)<0;
                            text: "重试";flat: true;onClicked: page.assistant.translateParagraph(paragraphBlock.index) }
                    }
                }
            }
        }
    }
}
