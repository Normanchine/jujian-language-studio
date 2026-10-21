import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "readingGrammarFavorites"
    property string language: "ja"
    property string query: ""
    property string notice: ""
    property var rows: reading.intensive.grammarFavorites.filter(function(a) {
        var needle=page.query.trim().toLowerCase();
        return a.language===page.language && (!needle || [a.text,a.sentence,a.meaning,a.article_title].join(" ").toLowerCase().indexOf(needle)>=0);
    })
    signal backRequested()
    signal languageChosen(string value)
    signal sourceRequested(var item)
    function escapeHtml(value) { return String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
    function sentenceHtml(item) {
        return '<p style="line-height:145%;margin:0">'+escapeHtml(item.sentence.slice(0,item.mark_start))+
            '<span style="color:#547FA3;text-decoration:underline">'+escapeHtml(item.sentence.slice(item.mark_start,item.mark_end))+'</span>'+
            escapeHtml(item.sentence.slice(item.mark_end))+'</p>';
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 14
        ReadingPageHeader { Layout.fillWidth: true; title: "语法收藏"; showBack: true; language: page.language
            onBackRequested: page.backRequested(); onLanguageChosen: function(value) { page.languageChosen(value); } }
        RowLayout {
            Layout.fillWidth: true
            Text { text: page.rows.length+" 条 · 保留原句与收藏时的解释"; color: "#7B8981"; font.pixelSize: 12; Layout.fillWidth: true }
            TextField { objectName: "readingGrammarSearch"; Layout.preferredWidth: Math.min(350,page.width*0.48); implicitHeight: 36;
                placeholderText: "搜索结构、原句或解释"; selectByMouse: true; onTextEdited: page.query=text; color: "#293B32";
                font.pixelSize: 12; leftPadding: 12; rightPadding: 12;
                background: Rectangle { radius: 8; color: settings.palette.surface; border.color: "#DFE7E1" } }
        }
        Text { visible: !!page.notice; text: page.notice; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#9A753E"; font.pixelSize: 12 }
        ListView {
            id: list; objectName: "readingGrammarFavoritesList"; Layout.fillWidth: true; Layout.fillHeight: true
            model: page.rows; clip: true; spacing: 12; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                required property var modelData
                width: list.width-10; height: content.implicitHeight+32; radius: 12
                color: settings.palette.surface; border.color: "#DFE7E1"
                ColumnLayout {
                    id: content; x: 20; y: 16; width: parent.width-40; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: modelData.text; color: "#547FA3"; font.pixelSize: 21; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        AppButton { objectName: "readingRemoveGrammar_"+modelData.id; text: "取消收藏"; flat: true;
                            onClicked: if (!reading.intensive.removeGrammarFavorite(modelData.id)) page.notice="取消收藏失败，请重试。" }
                    }
                    TextEdit { objectName: "readingGrammarSentence_"+modelData.id; text: page.sentenceHtml(modelData); textFormat: TextEdit.RichText;
                        readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; font.family: modelData.language==="ja" ? "Yu Gothic UI" : "Georgia";
                        font.pixelSize: 18; color: "#293B32"; Layout.fillWidth: true; Layout.preferredHeight: contentHeight }
                    TextEdit { text: modelData.meaning; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: true;
                        wrapMode: TextEdit.Wrap; font.pixelSize: 14; color: "#42564B"; Layout.fillWidth: true; Layout.preferredHeight: contentHeight }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: (modelData.article_title || "来源文章")+" · 第 "+(modelData.paragraph+1)+" 段"; color: "#7B8981"; font.pixelSize: 11;
                            Layout.fillWidth: true; wrapMode: Text.Wrap }
                        AppButton { objectName: "readingGrammarSource_"+modelData.id; text: "返回原文  ›"; flat: true; onClicked: page.sourceRequested(modelData) }
                    }
                }
            }
            Text { visible: !page.rows.length; anchors.centerIn: parent; text: page.query.trim() ? "没有匹配的收藏" : "还没有语法收藏，点击原文中的语法结构即可收藏";
                width: Math.min(parent.width-40,400); wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; color: "#7B8981"; font.pixelSize: 13 }
        }
    }
}
