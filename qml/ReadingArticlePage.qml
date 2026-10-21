import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: reader
    objectName: "readingArticlePage"
    property var article: ({})
    property var record: ({})
    property string mode: "intensive"
    property bool favorite: false
    property bool grammarVisible: true
    property bool hiraganaVisible: true
    property var activeAnnotation: ({})
    property var selectionEditor: null
    property string detailMode: ""
    property var assistant: reading.intensive
    property var gesture: assistant.gesture
    property var assistance: assistant.view
    property var detail: detailMode === "lookup" ? assistance.lookup : activeAnnotation
    property color ink: "#293B32"
    property color muted: "#738278"
    property bool wide: width>=850
    property var paragraphs: (article.body || "").split(/\n\s*\n/)
    property var expandedTranslations: ({})
    property bool allTranslations: false
    readonly property string selectedText: selectionEditor ? selectionEditor.selectedText.replace(/\u2060/g,"") : ""
    readonly property var bandLabels: ({basic:"N5–N4",intermediate:"N3–N2",advanced:"N1"})
    readonly property bool allBands: assistance.preferences.bands.indexOf("unknown")>=0
    signal backRequested()
    signal favoriteRequested()
    signal bookmarkEdited(var changes)
    signal grammarFavoritesRequested()
    signal studyFavoritesRequested()

    function htmlEscape(value) { return String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
    function bandVisible(a) { return allBands || (assistance.preferences.bands || []).indexOf(a.band || "unknown")>=0; }
    function highlighted(a) { return bandVisible(a) && (a.kind==="grammar" ? grammarVisible : a.kind==="hiragana" && hiraganaVisible); }
    function annotationColor(a) { return highlighted(a) ? (a.kind==="grammar" ? "#477E9A" : "#3C806B") : ink; }
    function render(text,paragraph) {
        var layout=paragraph===-1 ? assistance.titleLayout : assistance.layout[paragraph] || ({joiners:[]});
        var joiners=article.language==="ja" && assistance.preferences.furigana ? layout.joiners : [];
        function run(start,end) {
            var value="";
            for (var i=start;i<end;i++) { value+=htmlEscape(text.slice(i,i+1));if (joiners.indexOf(i+1)>=0) value+="\u2060"; }
            return value;
        }
        var candidates=(assistance.annotations || []).filter(function(a) {return a.paragraph===paragraph && (a.kind!=="grammar" || highlighted(a));});
        candidates.sort(function(a,b) {return (b.kind==="grammar" ? 2 : 1)-(a.kind==="grammar" ? 2 : 1) || (b.end-b.start)-(a.end-a.start);});
        var spans=[];
        candidates.forEach(function(a) {
            if (a.start<0 || a.end>text.length || text.slice(a.start,a.end)!==a.text) return;
            if (!spans.some(function(b) {return a.start<b.end && b.start<a.end;})) spans.push(a);
        });
        spans.sort(function(a,b) {return a.start-b.start;});
        var output="",end=0;
        spans.forEach(function(a) {
            output+=run(end,a.start);
            output+='<a href="annotation:'+a.id+'" style="color:'+annotationColor(a)+';text-decoration:'+(highlighted(a) ? 'underline' : 'none')+'">'+run(a.start,a.end)+'</a>';
            end=a.end;
        });
        return '<p style="line-height:'+(paragraph===-1 ? '145%' : article.language==="ja" && assistance.preferences.furigana ? '205%' : '175%')+';margin:0">'+output+run(end,text.length)+'</p>';
    }
    function activate(link) {
        activeAnnotation=(assistance.annotations || []).find(function(a) {return a.id===link.split(":")[1];}) || {};
        detailMode="annotation";
        if (selectionEditor) selectionEditor.deselect();
        if (activeAnnotation.kind!=="grammar") queryAnnotation();
    }
    function queryAnnotation() {
        if (!activeAnnotation.text) return;
        assistant.lookup(activeAnnotation.paragraph,activeAnnotation.start,activeAnnotation.end,"word");detailMode="lookup";
    }
    function querySelection() {
        queryEditor(selectionEditor);
    }
    function clearTextSelection() {
        if (selectionEditor) selectionEditor.deselect();
    }
    function queryEditor(editor) {
        if (!editor || !editor.selectedText.replace(/\u2060/g,"").trim()) return;
        selectionEditor=editor;
        assistant.lookup(editor.paragraphIndex,editor.sourceOffset(editor.selectionStart),editor.sourceOffset(editor.selectionEnd),"auto");
        activeAnnotation=({});detailMode="lookup";
    }
    function changeLookupMode(value) {
        if (!detail.text || detailMode!=="lookup") return;
        assistant.lookup(detail.paragraph,detail.start,detail.end,value);
    }
    function toggleBand(band) {
        var next=allBands ? [] : (assistance.preferences.bands || []).slice(),index=next.indexOf(band);
        if (index>=0) next.splice(index,1);else next.push(band);
        if (next.length===3) next.push("unknown");
        assistant.setPreference("bands",next);
    }
    function translationOpen(index) { return allTranslations || !!expandedTranslations[index]; }
    function toggleTranslation(index) {
        var next=Object.assign({},expandedTranslations);
        if (allTranslations) {
            for (var i=0;i<paragraphs.length;i++) next[i]=true;
            allTranslations=false;
        }
        next[index]=!next[index];expandedTranslations=next;
        if (next[index]) {
            assistant.translateParagraph(index);
            Qt.callLater(function() {passage.positionViewAtIndex(index,ListView.Beginning);});
        }
    }
    function sentenceHtml(item) {
        if (!item.sentence) return "";
        return '<p style="line-height:165%;margin:0">'+htmlEscape(item.sentence.slice(0,item.mark_start))+
            '<span style="color:#477E9A;text-decoration:underline">'+htmlEscape(item.sentence.slice(item.mark_start,item.mark_end))+'</span>'+htmlEscape(item.sentence.slice(item.mark_end))+'</p>';
    }
    function savePosition() {
        if (mode!=="intensive") return;
        if (article.language==="en" && englishReader.item) {englishReader.item.savePosition();return;}
        var index=passage.indexAt(10,passage.contentY+10);
        var top=passage.headerItem ? passage.headerItem.y : passage.originY;
        bookmarkEdited({position:Math.max(0,passage.contentY-top),readParagraph:Math.max(0,index)+1,paragraphCount:paragraphs.length,visited:Date.now()});
    }
    function resume() {
        gesture.reset();
        gesture.setCursorStyle(settings.palette.accent,article.language!=="en");
        activeAnnotation=({});detailMode="";selectionEditor=null;expandedTranslations=({});allTranslations=false;
        assistant.openDocument(String(article.id || ""),article.language || "ja",article.body || "",article.title || "",article.sourceLabel || article.setTitle || "");
        if (article.language==="en") {
            assistant.english.ensureAnnotated();
            if (englishReader.item) englishReader.item.restorePosition();
            return;
        }
        Qt.callLater(function() {
            passage.forceLayout();
            var top=passage.headerItem ? passage.headerItem.y : passage.originY;
            passage.contentY=top+Math.min(record.position || 0,Math.max(0,passage.contentHeight-passage.height));
        });
    }
    function focusFavorite(item) {
        passage.positionViewAtIndex(item.paragraph,ListView.Center);
        activeAnnotation=Object.assign({},item,{id:item.annotation_id,kind:"grammar",label:"语法结构",fromFavorite:true});detailMode="annotation";
    }
    function focusStudyFavorite(item) {
        if (article.language==="en" && englishReader.item) englishReader.item.focusFavorite(item);
    }
    Component.onCompleted: { gesture.setScope(reader);gesture.setTrigger(settings.values.shortcut_reading_query);gesture.setCursorStyle(settings.palette.accent,article.language!=="en"); }
    onVisibleChanged: { if (visible) resume();else {gesture.reset();assistant.cancel();} }
    onArticleChanged: if (visible) resume()
    Connections { target: settings
        function onChanged() {reader.gesture.setTrigger(settings.values.shortcut_reading_query);reader.gesture.setCursorStyle(settings.palette.accent,reader.article.language!=="en");}
    }
    Connections {
        target: reader.assistant
        function onChanged() {
            if (reader.detailMode==="annotation" && reader.activeAnnotation.id) {
                var previous=reader.activeAnnotation;
                reader.activeAnnotation=reader.assistance.annotations.find(function(a) {return a.id===previous.id;}) || (previous.fromFavorite ? previous : {});
            }
        }
    }

    component SectionText: ColumnLayout {
        property string label: ""
        property string value: ""
        property bool expanded: false
        spacing: 7
        visible: !!value
        Layout.fillWidth: true
        RowLayout { Layout.fillWidth: true
            Text { text: parent.parent.label;color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true }
            AppButton { visible: parent.parent.value.length>100;text: parent.parent.expanded ? "收起" : "展开";flat: true;implicitHeight: 24;
                onClicked: parent.parent.expanded=!parent.parent.expanded }
        }
        TextEdit { text: '<p style="line-height:165%;margin:0">'+reader.htmlEscape(parent.value.length>100 && !parent.expanded ? parent.value.slice(0,90)+"…" : parent.value)+'</p>';textFormat: TextEdit.RichText;
            readOnly: true;selectByMouse: true;color: reader.ink;font.pixelSize: 14;wrapMode: TextEdit.Wrap;Layout.fillWidth: true;Layout.preferredHeight: contentHeight }
    }
    component DetailBody: ColumnLayout {
        spacing: reader.wide ? 18 : 10
        RowLayout {
            Layout.fillWidth: true
            Text { text: reader.detailMode==="lookup" ? (reader.detail.kind==="sentence" ? "句子解析" : "词语 · 语境释义") : "语法结构";
                color: reader.muted;font.pixelSize: 12;Layout.fillWidth: true }
            AppButton { objectName: "readingSaveGrammar";visible: reader.detailMode==="annotation" && reader.activeAnnotation.kind==="grammar";
                text: (reader.assistance.favoriteAnnotations || []).indexOf(reader.activeAnnotation.id)>=0 ? "★ 已收藏" : "☆ 收藏";flat: true;
                onClicked: reader.assistant.toggleGrammarFavorite(reader.activeAnnotation.id) }
            AppButton { text: "×";flat: true;implicitWidth: 26;onClicked: {reader.activeAnnotation=({});reader.detailMode="";} }
        }
        Text { objectName: "readingDetailWord";text: reader.detail.text || "";textFormat: Text.PlainText;
            color: reader.ink;font.pixelSize: !reader.wide ? 19 : reader.detail.kind==="sentence" ? 21 : 25;font.weight: Font.DemiBold;wrapMode: Text.Wrap;Layout.fillWidth: true }
        Text { visible: !!reader.detail.reading && reader.detail.kind!=="sentence" && reader.detail.reading!==reader.detail.text;
            text: reader.detail.reading || "";color: reader.muted;font.pixelSize: 13;wrapMode: Text.Wrap;Layout.fillWidth: true }
        AppButton { visible: reader.detailMode==="lookup";text: reader.detail.kind==="sentence" ? "改查词义" : "改按句子解析";
            flat: true;enabled: !reader.assistance.queryBusy;onClicked: reader.changeLookupMode(reader.detail.kind==="sentence" ? "word" : "sentence") }
        Text { visible: reader.detailMode==="lookup" && (reader.wide || reader.assistance.queryBusy);text: reader.assistance.queryStatus;color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
        ColumnLayout {
            visible: !!reader.detail.meaning;Layout.fillWidth: true;spacing: 7
            Text { text: reader.detail.kind==="sentence" ? "参考译文" : reader.detailMode==="annotation" ? "本句含义" : "本句词义";color: reader.muted;font.pixelSize: 11 }
            TextEdit { objectName: "readingDetailMeaning";text: '<p style="line-height:165%;margin:0">'+reader.htmlEscape(reader.detail.meaning)+'</p>';textFormat: TextEdit.RichText;
                readOnly: true;selectByMouse: true;color: "#426E57";font.pixelSize: 15;wrapMode: TextEdit.Wrap;Layout.fillWidth: true;Layout.preferredHeight: contentHeight }
        }
        ColumnLayout {
            visible: !!reader.detail.connection;Layout.fillWidth: true;spacing: 7
            Text { text: "接续结构";color: reader.muted;font.pixelSize: 11 }
            Rectangle {
                Layout.fillWidth: true;implicitHeight: connectionText.contentHeight+24;radius: 7;color: settings.palette.selection
                TextEdit { id: connectionText;x: 12;y: 12;width: parent.width-24;readOnly: true;selectByMouse: true;wrapMode: TextEdit.Wrap;
                    text: reader.detail.connection || "";textFormat: TextEdit.PlainText;color: "#477E9A";font.pixelSize: 14 }
            }
        }
        SectionText { label: "理解要点";value: reader.detail.point || "" }
        SectionText { label: reader.detail.kind==="sentence" ? "理解提示" : "本句用法";value: reader.detail.usage || "" }
        SectionText { label: "句子主干";value: reader.detail.main_clause || "" }
        ColumnLayout {
            visible: (reader.detail.structure || []).length>0;Layout.fillWidth: true;spacing: 10
            Text { text: "成分拆解";color: reader.muted;font.pixelSize: 11 }
            Repeater {
                model: reader.detail.structure || []
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true;implicitHeight: structureContent.implicitHeight+24;radius: 7;color: settings.palette.page
                    ColumnLayout { id: structureContent;x: 12;y: 12;width: parent.width-24;spacing: 6
                        Text { text: modelData.role;color: "#477E9A";font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
                        Text { text: modelData.text;color: reader.ink;font.pixelSize: 15;Layout.fillWidth: true;wrapMode: Text.Wrap }
                        Text { text: modelData.meaning;color: reader.muted;font.pixelSize: 12;Layout.fillWidth: true;wrapMode: Text.Wrap;lineHeight: 1.5 }
                    }
                }
            }
        }
        ColumnLayout {
            visible: (reader.detail.grammar || []).length>0;Layout.fillWidth: true;spacing: 10
            Text { text: "句中语法";color: reader.muted;font.pixelSize: 11 }
            Repeater {
                model: reader.detail.grammar || []
                delegate: ColumnLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true;spacing: 6
                    RowLayout { Layout.fillWidth: true
                        Text { text: modelData.text;color: "#477E9A";font.pixelSize: 16;Layout.fillWidth: true;wrapMode: Text.Wrap }
                        AppButton { text: "☆ 收藏";flat: true;onClicked: reader.assistant.favoriteLookupGrammar(index) }
                    }
                    Text { text: modelData.connection;color: reader.muted;font.pixelSize: 12;Layout.fillWidth: true;wrapMode: Text.Wrap }
                    Text { text: modelData.meaning;color: reader.ink;font.pixelSize: 13;Layout.fillWidth: true;wrapMode: Text.Wrap;lineHeight: 1.5 }
                }
            }
        }
        ColumnLayout {
            visible: !!reader.detail.sentence;Layout.fillWidth: true;spacing: 10
            Rectangle { Layout.fillWidth: true;height: 1;color: "#DFE7E1" }
            Text { text: "在原句中";color: reader.muted;font.pixelSize: 11 }
            TextEdit { text: reader.sentenceHtml(reader.detail);textFormat: TextEdit.RichText;readOnly: true;selectByMouse: true;
                color: reader.ink;font.family: reader.article.language==="en" ? "Georgia" : "Yu Gothic UI";font.pixelSize: 16;
                wrapMode: TextEdit.Wrap;Layout.fillWidth: true;Layout.preferredHeight: contentHeight }
            Text { text: reader.article.title || "";color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
        }
        Text { visible: reader.detailMode==="annotation" || !!reader.detail.band;text: reader.detail.band && reader.detail.band!=="unknown" ? reader.bandLabels[reader.detail.band]+" · "+(reader.detail.level_source==="AI 参考估计" ? "AI 参考估计" : "参考等级") : "等级尚未确定 · 在全部中显示";
            color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
        RowLayout {
            visible: !!reader.detail.meaning
            AppButton { objectName: "readingCorrectAnnotation";text: "更正";flat: true;
                onClicked: {correction.text=reader.detail.meaning || "";correctionReading.text=reader.detail.reading || "";correctionPopup.open();} }
            AppButton { objectName: "readingHideAnnotation";visible: reader.detailMode==="annotation" && !!reader.activeAnnotation.id;text: "隐藏标记";flat: true;
                onClicked: {reader.assistant.hideAnnotation(reader.activeAnnotation.id);reader.activeAnnotation=({});reader.detailMode="";} }
        }
    }

    ColumnLayout {
        anchors.fill: parent;spacing: 12;visible: reader.article.language!=="en"
        RowLayout {
            Layout.fillWidth: true;spacing: 8
            ReadingBackButton { objectName: "readingBack";onClicked: {reader.savePosition();reader.backRequested();} }
            Text { text: "精读";font.pixelSize: 19;font.weight: Font.DemiBold;color: reader.ink }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "readingOpenGrammarFavorites";text: "语法收藏";flat: true;onClicked: {reader.savePosition();reader.grammarFavoritesRequested();} }
            AppButton { objectName: "readingArticleFavorite";text: reader.favorite ? "★ 已收藏" : "☆ 收藏";flat: true;onClicked: reader.favoriteRequested() }
            AppButton { objectName: "readingEndReview";text: "结束精读";primary: true;
                onClicked: {reader.savePosition();reader.bookmarkEdited({lastReviewed:Date.now(),reviewCount:(reader.record.reviewCount || 0)+1});reader.backRequested();} }
        }
        Flow {
            Layout.fillWidth: true;spacing: 8
            AppButton { objectName: "readingFuriganaToggle";visible: reader.article.language==="ja";text: "注音";checkable: true;
                checked: !!reader.assistance.preferences.furigana;primary: checked;onClicked: reader.assistant.setPreference("furigana",!reader.assistance.preferences.furigana) }
            AppButton { objectName: "readingGrammarToggle";visible: reader.article.language==="ja";text: "语法";checkable: true;checked: reader.grammarVisible;primary: checked;onToggled: reader.grammarVisible=checked }
            AppButton { objectName: "readingHiraganaToggle";visible: reader.article.language==="ja";text: "平假名词汇";checkable: true;checked: reader.hiraganaVisible;primary: checked;onToggled: reader.hiraganaVisible=checked }
            AppButton { id: levelsButton;objectName: "readingLevelFilter";visible: reader.article.language==="ja";
                text: "等级 · "+(reader.allBands ? "全部" : reader.assistance.preferences.bands.map(function(b) {return reader.bandLabels[b];}).join(" / ") || "无")+" ▾";
                onClicked: levelsPopup.open()
                Popup {
                    id: levelsPopup;objectName: "readingLevelsPopup"
                    width: Math.min(324,reader.width-8);padding: 16
                    x: Math.min(0,reader.width-levelsButton.x-width)
                    y: levelsButton.height+8;focus: true
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    background: Item {
                        Rectangle { x: -2;y: 4;width: parent.width+4;height: parent.height+2;radius: 14;color: "#102D4637" }
                        Rectangle { anchors.fill: parent;radius: 12;color: settings.palette.surface;border.color: "#DCE6DE" }
                    }
                    enter: Transition { NumberAnimation { property: "opacity";from: 0;to: 1;duration: uiAnimationsEnabled ? 120 : 0 } }
                    exit: Transition { NumberAnimation { property: "opacity";to: 0;duration: uiAnimationsEnabled ? 90 : 0 } }
                    contentItem: ColumnLayout {
                        spacing: 14
                        RowLayout { Layout.fillWidth: true
                            Text { text: "标注范围";color: reader.ink;font.pixelSize: 14;Layout.fillWidth: true }
                            Text { text: "可多选";color: reader.muted;font.pixelSize: 11 }
                        }
                        GridLayout {
                            columns: 2;rowSpacing: 10;columnSpacing: 10;Layout.fillWidth: true
                            ReadingLevelChip { objectName: "readingBandAll";heading: "全部";subtitle: "所有难度";selected: reader.allBands;Layout.fillWidth: true;
                                onClicked: reader.assistant.setPreference("bands",["basic","intermediate","advanced","unknown"]) }
                            ReadingLevelChip { objectName: "readingBandBasic";heading: "基础";subtitle: "N5–N4";selected: !reader.allBands && reader.assistance.preferences.bands.indexOf("basic")>=0;Layout.fillWidth: true;
                                onClicked: reader.toggleBand("basic") }
                            ReadingLevelChip { objectName: "readingBandIntermediate";heading: "进阶";subtitle: "N3–N2";selected: !reader.allBands && reader.assistance.preferences.bands.indexOf("intermediate")>=0;Layout.fillWidth: true;
                                onClicked: reader.toggleBand("intermediate") }
                            ReadingLevelChip { objectName: "readingBandAdvanced";heading: "高阶";subtitle: "N1";selected: !reader.allBands && reader.assistance.preferences.bands.indexOf("advanced")>=0;Layout.fillWidth: true;
                                onClicked: reader.toggleBand("advanced") }
                        }
                    }
                }
            }
            AppButton { objectName: "readingAnalyze";visible: reader.article.language==="ja";enabled: !reader.assistance.busy;
                text: reader.assistance.busy ? "分析中…" : reader.assistance.analyzed ? "重新分析" : "分析标注";onClicked: reader.assistant.analyze(reader.assistance.analyzed) }
            AppButton { objectName: "readingTranslateAll";text: reader.allTranslations ? "收起译文" : "显示译文";
                onClicked: {reader.allTranslations=!reader.allTranslations;if (reader.allTranslations) reader.assistant.translateAll();else reader.expandedTranslations=({});} }
            AppButton { visible: reader.assistance.busy || reader.assistance.queryBusy || reader.assistance.translationBusy>=0;text: "停止";onClicked: reader.assistant.cancel() }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: reader.assistance.status;color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true;elide: Text.ElideRight }
            AppButton { visible: reader.assistance.hiddenCount>0;text: "恢复隐藏";flat: true;onClicked: reader.assistant.restoreHidden() }
        }
        RowLayout {
            Layout.fillWidth: true;Layout.fillHeight: true;spacing: 14
            Rectangle {
                id: articleSurface
                property var page: reader
                Layout.fillWidth: true;Layout.fillHeight: true;radius: 12;color: settings.palette.surface;border.color: "#DFE7E1"
                ColumnLayout {
                    anchors.fill: parent;anchors.margins: reader.wide ? 28 : 16;spacing: 10
                    ListView {
                        id: passage;objectName: "readingPassage";Layout.fillWidth: true;Layout.fillHeight: true
                        model: reader.paragraphs;spacing: 24;clip: true;boundsBehavior: Flickable.StopAtBounds
                        onMovementEnded: reader.savePosition()
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded;onPressedChanged: if (!pressed) reader.savePosition() }
                        delegate: Column {
                            id: paragraphBlock
                            required property string modelData
                            required property int index
                            width: passage.width-12;spacing: 8
                            property var translation: reader.assistance.translations[index] || ({text:"",status:""})
                            property var page: reader
                            Loader {
                                active: paragraphBlock.index===0;visible: active;width: parent.width
                                sourceComponent: Column {
                            width: passage.width-12;spacing: 10
                            Item { width: parent.width;height: articleHeading.implicitHeight+(articleHeading.rubyVisible ? 16 : 0)
                                ReadingRubyText { id: articleHeading;objectName: "readingArticleHeading";reader: articleSurface.page;paragraphIndex: -1;sourceText: reader.article.title || "";
                                    y: rubyVisible ? 16 : 0;width: parent.width;font.pixelSize: 24;font.weight: Font.DemiBold }
                            }
                            Text { text: reader.article.mock ? "模拟条目 · 无真实正文" : reader.article.sourceLabel || "自编演示材料";
                                width: parent.width;color: reader.muted;font.pixelSize: 11;wrapMode: Text.Wrap }
                            Item { width: parent.width;height: 14 }
                        }
                            }
                            Item {
                                width: parent.width;height: rubyParagraph.implicitHeight+(rubyParagraph.rubyVisible ? 16 : 0)
                                ReadingRubyText {
                                    id: rubyParagraph;objectName: "readingParagraph_"+paragraphBlock.index
                                    y: rubyVisible ? 16 : 0
                                    width: parent.width;reader: paragraphBlock.page;paragraphIndex: paragraphBlock.index;sourceText: paragraphBlock.modelData
                                }
                            }
                            Item {
                                width: parent.width;height: 27
                                MouseArea {
                                    anchors.fill: parent;anchors.topMargin: -paragraphBlock.spacing;anchors.bottomMargin: -paragraphBlock.spacing
                                    acceptedButtons: Qt.LeftButton
                                    onClicked: reader.clearTextSelection()
                                }
                                AppButton { objectName: "readingParagraphTranslation_"+paragraphBlock.index;text: reader.translationOpen(paragraphBlock.index) ? "收起译文  ⌃" : "查看译文  ⌄";
                                    flat: true;implicitHeight: 27;onClicked: {reader.clearTextSelection();reader.toggleTranslation(paragraphBlock.index);} }
                            }
                            Rectangle {
                                visible: reader.translationOpen(paragraphBlock.index);width: parent.width;height: translationContent.implicitHeight+24;radius: 7;color: settings.palette.page
                                ColumnLayout {
                                    id: translationContent;x: 14;y: 12;width: parent.width-28;spacing: 7
                                    TextEdit { objectName: "readingTranslationText_"+paragraphBlock.index;visible: !!paragraphBlock.translation.text;
                                        text: '<p style="line-height:170%;margin:0">'+reader.htmlEscape(paragraphBlock.translation.text)+'</p>';textFormat: TextEdit.RichText;
                                        readOnly: true;selectByMouse: true;wrapMode: TextEdit.Wrap;color: "#607367";font.pixelSize: 14;
                                        Layout.fillWidth: true;Layout.preferredHeight: contentHeight }
                                    RowLayout { Layout.fillWidth: true
                                        Text { text: paragraphBlock.translation.status;color: reader.muted;font.pixelSize: 11;Layout.fillWidth: true;wrapMode: Text.Wrap }
                                        AppButton { visible: !paragraphBlock.translation.text && reader.assistance.translationBusy!==paragraphBlock.index && reader.assistance.translationQueued.indexOf(paragraphBlock.index)<0;
                                            text: "重试";flat: true;onClicked: reader.assistant.translateParagraph(paragraphBlock.index) }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Rectangle {
                visible: reader.wide;Layout.preferredWidth: 292;Layout.fillHeight: true;radius: 12;color: settings.palette.surface;border.color: "#DFE7E1"
                ScrollView { id: detailScroll;anchors.fill: parent;anchors.margins: 20;clip: true;contentWidth: availableWidth
                    ColumnLayout { width: detailScroll.availableWidth;spacing: 16
                        DetailBody { visible: !!reader.detail.text && reader.detailMode!=="";Layout.fillWidth: true }
                        ColumnLayout { visible: !reader.detail.text || reader.detailMode==="";Layout.fillWidth: true;spacing: 13
                            Text { text: "读到哪里，理解到哪里";color: reader.ink;font.pixelSize: 17;Layout.fillWidth: true;wrapMode: Text.Wrap }
                            Text { text: "点击标注查看用法。按住 "+settings.values.shortcut_reading_query+" 划选词句，松开鼠标查询；普通划选可复制。";color: reader.muted;font.pixelSize: 13;lineHeight: 1.7;Layout.fillWidth: true;wrapMode: Text.Wrap }
                        }
                    }
                }
            }
        }
        Rectangle {
            visible: !reader.wide && !!reader.detail.text && reader.detailMode!=="";Layout.fillWidth: true;Layout.preferredHeight: Math.min(170,reader.height*0.28,inlineBody.implicitHeight+32);
            radius: 12;color: settings.palette.surface;border.color: "#DFE7E1"
            ScrollView { id: inlineScroll;anchors.fill: parent;anchors.margins: 16;clip: true;contentWidth: availableWidth
                DetailBody { id: inlineBody;width: inlineScroll.availableWidth }
            }
        }
    }
    Loader {
        id: englishReader;anchors.fill: parent;active: reader.article.language==="en"
        sourceComponent: ReadingEnglishPage { reader: englishReader.parent }
        onLoaded: item.restorePosition()
    }
    Popup {
        id: correctionPopup;objectName: "readingCorrectionPopup";parent: Overlay.overlay;anchors.centerIn: parent;modal: true;focus: true
        width: Math.min(450,parent.width-40);padding: 22
        background: Rectangle { radius: 12;color: settings.palette.surface }
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: "更正解释";color: reader.ink;font.pixelSize: 17;Layout.fillWidth: true;wrapMode: Text.Wrap }
            TextField { id: correctionReading;objectName: "readingCorrectionReading";visible: reader.article.language==="ja";Layout.fillWidth: true;placeholderText: "读音（可选）";color: reader.ink }
            ScrollView { Layout.fillWidth: true;Layout.preferredHeight: 150;clip: true
                TextArea { id: correction;objectName: "readingCorrectionText";wrapMode: TextEdit.Wrap;selectByMouse: true;font.pixelSize: 14;color: reader.ink;placeholderText: "填写这处表达的含义或用法" }
            }
            RowLayout { Layout.alignment: Qt.AlignRight
                AppButton { text: "取消";flat: true;onClicked: correctionPopup.close() }
                AppButton { objectName: "readingSaveCorrection";text: "保存";primary: true;enabled: correction.text.trim().length>0;
                    onClicked: {
                        var saved=reader.detailMode==="lookup" ? reader.assistant.correctLookup(correction.text,correctionReading.text,reader.detail.usage || "") : reader.assistant.correctAnnotation(reader.activeAnnotation.id,correction.text,correctionReading.text);
                        if (saved) correctionPopup.close();
                    }
                }
            }
        }
    }
}
