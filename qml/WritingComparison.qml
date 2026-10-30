import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: comparison
    objectName: "writingComparison"
    property string title: ""
    property var review: ({})
    property string currentText: ""
    readonly property bool stacked: width < 900
    readonly property bool draftChanged: currentText.trim() !== String(review.text || "").trim()
    signal backRequested()
    signal noteRequested(var source)
    signal selectionCleared(var source)

    function prose(value) {
        var escaped=String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
        return '<p style="line-height:170%;margin:0">'+escaped.replace(/\n/g,"<br>")+'</p>';
    }
    onVisibleChanged: if (visible) { originalScroll.contentY=0; modelScroll.contentY=0; }

    ColumnLayout {
        anchors.fill: parent; spacing: 12
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            AppButton { objectName: "writingComparisonBack"; text: "‹ 返回作文"; onClicked: comparison.backRequested() }
            Text { text: "原稿与范文"; color: "#26342C"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Text { text: comparison.stacked ? "上下对照" : "左右对照"; color: "#78877D"; font.pixelSize: 11 }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 5
            Text { text: comparison.title; Layout.fillWidth: true; elide: Text.ElideRight; color: "#26342C"; font.pixelSize: 16; font.weight: Font.DemiBold }
            Text {
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#78877D"; font.pixelSize: 11
                text: (comparison.review.created ? String(comparison.review.created).replace("T"," ").slice(0,16)+" · " : "")
                    + (comparison.draftChanged ? "草稿已继续修改；这里保留当次批改的原稿与范文。" : "原稿与 AI 范文已随作文保存，可分别滚动、选字和摘录。")
            }
        }
        GridLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            columns: comparison.stacked ? 1 : 2; rowSpacing: 12; columnSpacing: 14
            Rectangle {
                objectName: "writingComparisonOriginalCard"
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.preferredHeight: 1; Layout.minimumHeight: 160
                radius: 12; color: settings.palette.surface; border.color: "#DFE6DF"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: comparison.stacked ? 16 : 22; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "我的原稿"; color: "#26342C"; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Text { text: "批改时保存"; color: "#78877D"; font.pixelSize: 11 }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#E5EBE5" }
                    Flickable {
                        id: originalScroll; objectName: "writingComparisonOriginalScroll"
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: width; contentHeight: originalText.height+16; boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        WritingSelectableText {
                            id: originalText; objectName: "writingComparisonOriginalText"; width: parent.width-12; height: implicitHeight
                            text: comparison.prose(comparison.review.text); textFormat: TextEdit.RichText
                            font.family: "Georgia"; font.pixelSize: 18; color: "#293B32"
                            onNoteRequested: function(source) {comparison.noteRequested(source)}
                            onSelectionCleared: function(source) {comparison.selectionCleared(source)}
                        }
                    }
                }
            }
            Rectangle {
                objectName: "writingComparisonModelCard"
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.preferredHeight: 1; Layout.minimumHeight: 160
                radius: 12; color: settings.palette.surface; border.color: settings.palette.accent
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: comparison.stacked ? 16 : 22; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "AI 修改后范文"; color: settings.palette.accent; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Text { text: "参考表达"; color: "#78877D"; font.pixelSize: 11 }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: settings.palette.selection }
                    Flickable {
                        id: modelScroll; objectName: "writingComparisonModelScroll"
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: width; contentHeight: modelText.height+16; boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        WritingSelectableText {
                            id: modelText; objectName: "writingComparisonModelText"; width: parent.width-12; height: implicitHeight
                            text: comparison.prose(comparison.review.revisedText); textFormat: TextEdit.RichText
                            font.family: "Georgia"; font.pixelSize: 18; color: "#293B32"
                            onNoteRequested: function(source) {comparison.noteRequested(source)}
                            onSelectionCleared: function(source) {comparison.selectionCleared(source)}
                        }
                    }
                }
            }
        }
    }
}
