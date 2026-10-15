import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: notesPage
    property string language: "全部"
    function filtered() {
        var result = []
        for (var i = 0; i < writer.notes.length; i++)
            if (language === "全部" || writer.notes[i].language === (language === "英语" ? "en" : "ja"))
                result.push(writer.notes[i])
        return result
    }
    Column {
        anchors.fill: parent; spacing: 13
        RowLayout { width: parent.width; height: 41
            Text { text: "学习笔记"; color: "#26342C"; font.pixelSize: 19; font.weight: Font.DemiBold
                Layout.fillWidth: true }
            AppCombo { width: 105; model: ["全部", "日语", "英语"]
                onActivated: notesPage.language = currentText }
        }
        Rectangle {
            width: parent.width; height: parent.height - 54; radius: 10
            color: "#FFFFFF"; border.color: "#DFE4E0"
            Flickable {
                anchors.fill: parent; anchors.margins: 18; clip: true
                contentWidth: width; contentHeight: list.height
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                Column { id: list; width: parent.width; spacing: 11
                    Repeater { model: notesPage.filtered()
                        delegate: Rectangle { required property var modelData
                            width: parent.width; height: noteBody.implicitHeight + 42; radius: 8
                            color: "#FFFEFB"; border.color: "#E8E1D8"
                            Text { x: 13; y: 10; text: (modelData.language === "en" ? "英语" : "日语")
                                + " · " + (modelData.essayTitle || "自由笔记") + " · " + String(modelData.updated).slice(0, 10)
                                color: "#8A7D6C"; font.pixelSize: 11 }
                            Text { id: noteBody; x: 13; y: 29; width: parent.width - 26
                                text: (modelData.sourceQuote ? "原句：" + modelData.sourceQuote + "\n" : "") + modelData.text
                                wrapMode: Text.Wrap; color: "#2C372F"; font.pixelSize: 13 }
                        }
                    }
                    Text { visible: notesPage.filtered().length === 0
                        text: "还没有笔记。作文批改后可在浮空笔记本里记录。"
                        color: "#8A958C"; font.pixelSize: 13 }
                }
            }
        }
    }
}
