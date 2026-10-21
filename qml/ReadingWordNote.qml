import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: note
    required property var page
    required property int paragraphIndex
    property var words: page.vocabulary.paragraphs[paragraphIndex] || []
    property string selectedId: page.selectedWords[paragraphIndex] || ""
    property string status: page.vocabulary.statuses[paragraphIndex] || "未标注"
    property bool pendingCenter: false
    property bool waitingLookup: false
    property bool followSelected: false
    property real scrollTarget: 0
    objectName: "englishWordNote_"+paragraphIndex
    signal wordClicked(var word)
    function centerSelected() {
        var index=words.findIndex(function(w) {return w.id===selectedId;});
        if (index<0) return;
        var card=cardRepeater.itemAt(index);
        if (!card) {pendingCenter=true;return;}
        scrollToPosition(card.y+card.height/2-cards.height/2,true);
        waitingLookup=!!words[index].busy;
        pendingCenter=false;
    }
    function scrollToPosition(position,animated) {
        scrollAnimation.stop();cards.cancelFlick();
        scrollTarget=Math.max(0,Math.min(Math.max(0,cards.contentHeight-cards.height),position));
        if (animated && uiAnimationsEnabled && Math.abs(cards.contentY-scrollTarget)>0.5) {
            scrollAnimation.from=cards.contentY;scrollAnimation.to=scrollTarget;scrollAnimation.start();
        } else cards.contentY=scrollTarget;
    }
    function stopFollowing() {
        scrollAnimation.stop();pendingCenter=false;waitingLookup=false;followSelected=false;scrollTarget=cards.contentY;
    }
    onWordsChanged: if (pendingCenter || waitingLookup || followSelected) Qt.callLater(centerSelected)
    Connections {
        target: note.page
        function onWordChosen(paragraph,wordId) {
            if (paragraph!==note.paragraphIndex) return;
            note.pendingCenter=true;note.followSelected=true;Qt.callLater(note.centerSelected);
        }
        function onWordRemoved(paragraph,wordId) {
            if (paragraph!==note.paragraphIndex) return;
            note.stopFollowing();
            Qt.callLater(function() {note.scrollToPosition(cards.contentY,false);});
        }
    }
    NumberAnimation { id: scrollAnimation;target: cards;property: "contentY";duration: 170;easing.type: Easing.OutCubic }
    Rectangle { x: 2;y: 3;width: parent.width;height: parent.height;radius: 8;color: "#0A5B5332" }
    Rectangle {
        anchors.fill: parent;radius: 7;color: "#FBF5DE"
        Rectangle { anchors.top: parent.top;anchors.left: parent.left;anchors.right: parent.right;height: 3;radius: 2;color: "#EADFAD" }
    }
    ColumnLayout {
        anchors.fill: parent;anchors.margins: 12;spacing: 7
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Word notes";font.family: "Segoe UI";font.pixelSize: 12;font.weight: Font.DemiBold;color: "#89774C";Layout.fillWidth: true }
            Text { text: note.words.length;color: "#A18C5E";font.pixelSize: 11 }
        }
        Flickable {
            id: cards;objectName: "englishWordCards_"+note.paragraphIndex
            visible: note.words.length>0
            Layout.fillWidth: true;Layout.fillHeight: true
            contentWidth: width;contentHeight: cardStack.height;clip: true
            flickableDirection: Flickable.VerticalFlick
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded;active: cards.contentHeight>cards.height;width: 5;
                onPressedChanged: if (pressed) note.stopFollowing() }
            onDraggingChanged: if (dragging) note.stopFollowing()
            WheelHandler {
                onWheel: function(event) {
                    var target=scrollAnimation.running ? note.scrollTarget : cards.contentY;
                    note.pendingCenter=false;note.waitingLookup=false;note.followSelected=false;
                    var pixels=event.pixelDelta.y;
                    var delta=pixels || event.angleDelta.y/120*72;
                    note.scrollToPosition((pixels ? cards.contentY : target)-delta,!pixels);
                    event.accepted=true;
                }
            }
            Column {
                id: cardStack;width: cards.width-8;spacing: 10
                onHeightChanged: if (note.followSelected) Qt.callLater(note.centerSelected)
                Repeater {
                    id: cardRepeater;model: note.words
                    delegate: Rectangle {
                id: card
                required property var modelData
                required property int index
                objectName: "englishWordCard_"+modelData.id
                width: cardStack.width;height: details.implicitHeight+22;radius: 5
                color: note.selectedId===modelData.id ? settings.palette.selection : "transparent"
                Behavior on color { enabled: uiAnimationsEnabled;ColorAnimation {duration: 120} }
                TapHandler { onTapped: note.wordClicked(card.modelData) }
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: note.page.removeLookupWord(card.modelData)
                }
                ColumnLayout {
                    id: details;x: 10;y: 11;width: parent.width-20;spacing: 7
                    RowLayout {
                        Layout.fillWidth: true;spacing: 5
                        Text { text: card.modelData.text;font.family: "Cambria";font.pixelSize: 19;font.weight: Font.DemiBold;color: "#3C4A38";wrapMode: Text.Wrap;Layout.fillWidth: true }
                        Text { text: card.modelData.pos || "";color: "#7C806B";font.pixelSize: 12 }
                        Button {
                            objectName: "englishSaveWord_"+card.modelData.id
                            visible: !!card.modelData.meaning && !card.modelData.busy
                            property bool saved: note.page.isSaved("word",note.paragraphIndex,card.modelData.start,card.modelData.end)
                            text: saved ? "★" : "☆";implicitWidth: 28;implicitHeight: 28;hoverEnabled: true
                            Accessible.name: saved ? "取消收藏词汇" : "收藏词汇"
                            ToolTip.visible: hovered;ToolTip.text: saved ? "取消收藏" : "收藏词汇与原句"
                            contentItem: Text {text: parent.text;font.pixelSize: 20;color: settings.palette.accent;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter}
                            background: Rectangle {radius: 5;color: parent.hovered ? "#ECE7CE" : "transparent"}
                            onClicked: note.page.assistant.toggleWordFavorite(card.modelData.id)
                        }
                    }
                    Text { visible: !!card.modelData.lemma && card.modelData.lemma.toLowerCase()!==card.modelData.text.toLowerCase();
                        text: card.modelData.lemma || "";font.family: "Cambria";font.pixelSize: 12;color: "#86816B";Layout.fillWidth: true;wrapMode: Text.Wrap }
                    Row {spacing: 5;visible: (card.modelData.tags || []).length>0
                        Repeater {model: card.modelData.tags || []
                            Rectangle {required property string modelData;width: tagLabel.implicitWidth+12;height: 21;radius: 5;color: settings.palette.selection
                                Text {id: tagLabel;anchors.centerIn: parent;text: modelData==='toefl' ? "托福词汇" : "高级词汇";font.pixelSize: 10;color: settings.palette.accent}
                            }
                        }
                    }
                    Text { visible: !!card.modelData.meaning;text: card.modelData.meaning || "";textFormat: Text.PlainText;
                        font.pixelSize: 14;color: "#4F6049";wrapMode: Text.Wrap;Layout.fillWidth: true;lineHeight: 1.4 }
                    Text { visible: !!card.modelData.quote;text: card.modelData.quote || "";textFormat: Text.PlainText;
                        font.family: "Cambria";font.italic: true;font.pixelSize: 15;color: "#706C53";wrapMode: Text.Wrap;Layout.fillWidth: true;lineHeight: 1.3 }
                    Text { visible: !!card.modelData.usage;text: card.modelData.usage || "";textFormat: Text.PlainText;
                        font.pixelSize: 13;color: "#817C66";wrapMode: Text.Wrap;Layout.fillWidth: true;lineHeight: 1.4 }
                    Text { visible: !!card.modelData.busy || (!card.modelData.meaning && !!card.modelData.status) || (card.modelData.status || "").indexOf("失败")>=0;
                        text: card.modelData.busy ? "查询中…" : card.modelData.status || "";font.pixelSize: 11;color: "#9A7754";wrapMode: Text.Wrap;Layout.fillWidth: true }
                    AppButton { visible: !card.modelData.busy && !card.modelData.meaning;text: "重试";flat: true;implicitHeight: 25;
                        onClicked: note.page.queryWord(card.modelData) }
                }
                    }
                }
            }
        }
        ColumnLayout {
            visible: !note.words.length;Layout.fillWidth: true;Layout.fillHeight: true;spacing: 6
            Text { text: note.status==="已标注" ? "本段暂无重点词汇\n点击正文单词即可查询" : note.status;
                color: "#998967";font.pixelSize: 12;Layout.fillWidth: true;wrapMode: Text.Wrap }
            AppButton { visible: !note.page.vocabulary.busy && note.status!=="已标注";text: note.status==="未标注" ? "标注词汇" : "重试";flat: true;
                onClicked: note.page.vocabularyBridge.analyze(false) }
            Item { Layout.fillHeight: true }
        }
        Text { visible: note.words.length>0 && note.status!=="已标注" && note.status!=="正在标注…";
            text: note.status;font.pixelSize: 11;color: "#9A7754";wrapMode: Text.Wrap;Layout.fillWidth: true }
    }
}
