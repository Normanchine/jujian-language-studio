import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "readingStudyFavorites"
    property string language: "en"
    property string query: ""
    property string kind: "all"
    property string notice: ""
    property var saved: reading.intensive.saved.view
    property var rows: saved.items.filter(function(a) {
        var needle=page.query.trim().toLowerCase();
        return a.language===page.language && (page.kind==="all" || a.kind===page.kind) &&
            (!needle || [a.text,a.sentence,a.meaning,a.usage,a.article_title].join(" ").toLowerCase().indexOf(needle)>=0);
    })
    signal backRequested()
    signal languageChosen(string value)
    signal sourceRequested(var item)
    ColumnLayout {
        anchors.fill: parent;spacing: 14
        ReadingPageHeader {Layout.fillWidth: true;title: "词句收藏";showBack: true;language: page.language
            onBackRequested: page.backRequested();onLanguageChosen: function(value) {page.languageChosen(value);} }
        Flow {
            Layout.fillWidth: true;spacing: 8
            Repeater {
                model: [{key:"all",label:"全部"},{key:"word",label:"词汇"},{key:"sentence",label:"句子"}]
                AppButton {required property var modelData;objectName: "readingSavedFilter_"+modelData.key
                    text: modelData.label;primary: page.kind===modelData.key;onClicked: page.kind=modelData.key}
            }
            TextField {objectName: "readingSavedSearch";width: Math.min(330,page.width-20);implicitHeight: 36
                placeholderText: "搜索词句、释义或来源";selectByMouse: true;onTextEdited: page.query=text
                color: "#293B32";font.pixelSize: 12;leftPadding: 12;rightPadding: 12
                background: Rectangle {radius: 8;color: settings.palette.surface;border.color: "#DFE7E1"} }
        }
        Text {text: page.rows.length+" 条收藏";font.pixelSize: 12;color: "#7B8981"}
        Text {visible: !!page.notice || page.saved.status.indexOf("失败")>=0;text: page.notice || page.saved.status
            Layout.fillWidth: true;wrapMode: Text.Wrap;font.pixelSize: 12;color: "#9A753E"}
        ListView {
            id: list;objectName: "readingSavedList";Layout.fillWidth: true;Layout.fillHeight: true
            model: page.rows;clip: true;spacing: 12;boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {policy: ScrollBar.AsNeeded}
            delegate: Rectangle {
                id: card;required property var modelData
                objectName: "readingSavedCard_"+modelData.id
                width: list.width-10;height: content.implicitHeight+32;radius: 12
                color: settings.palette.surface;border.color: "#DFE7E1"
                ColumnLayout {
                    id: content;x: 20;y: 16;width: parent.width-40;spacing: 10
                    Text {text: card.modelData.kind==="word" ? "词汇" : "句子";font.pixelSize: 11;color: settings.palette.accent}
                    TextEdit {text: card.modelData.text;textFormat: TextEdit.PlainText;readOnly: true;selectByMouse: true
                        font.family: "Cambria";font.pixelSize: card.modelData.kind==="word" ? 23 : 21
                        color: "#293B32";wrapMode: TextEdit.Wrap;Layout.fillWidth: true;Layout.preferredHeight: contentHeight}
                    Text {visible: !!card.modelData.pos;text: card.modelData.pos || "";font.pixelSize: 12;color: "#7B8981"}
                    Text {visible: !!card.modelData.meaning;text: card.modelData.meaning;textFormat: Text.PlainText
                        font.pixelSize: 15;color: "#42564B";Layout.fillWidth: true;wrapMode: Text.Wrap;lineHeight: 1.45}
                    Text {visible: card.modelData.kind==="word";text: card.modelData.sentence;textFormat: Text.PlainText
                        font.family: "Cambria";font.pixelSize: 17;color: "#6F7C72";Layout.fillWidth: true;wrapMode: Text.Wrap;lineHeight: 1.45}
                    Text {visible: !!card.modelData.usage;text: card.modelData.usage;textFormat: Text.PlainText
                        font.pixelSize: 13;color: "#6F7C72";Layout.fillWidth: true;wrapMode: Text.Wrap;lineHeight: 1.45}
                    Text {text: (card.modelData.article_title || "来源文章")+" · 第 "+(card.modelData.paragraph+1)+" 段"
                        font.pixelSize: 11;color: "#7B8981";Layout.fillWidth: true;wrapMode: Text.Wrap}
                    Flow {
                        Layout.fillWidth: true;spacing: 8
                        AppButton {objectName: "readingSavedSource_"+card.modelData.id;text: "返回原文  ›";flat: true;onClicked: page.sourceRequested(card.modelData)}
                        AppButton {objectName: "readingSavedCopy_"+card.modelData.id;text: "复制";flat: true;onClicked: reading.intensive.copyText(card.modelData.text)}
                        AppButton {objectName: "readingSavedRemove_"+card.modelData.id;text: "取消收藏";flat: true;onClicked: reading.intensive.saved.remove(card.modelData.id)}
                    }
                }
            }
            Text {visible: !page.rows.length;anchors.centerIn: parent;width: Math.min(parent.width-40,420)
                text: page.query.trim() ? "没有匹配的收藏" : "还没有收藏\n点词卡的 ☆ 收藏词汇，划选原文收藏句子"
                font.pixelSize: 13;color: "#7B8981";wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter;lineHeight: 1.5}
        }
    }
}
