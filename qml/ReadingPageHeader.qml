import QtQuick
import QtQuick.Layouts

RowLayout {
    id: header
    property string title: "阅读"
    property string language: "en"
    property bool showBack: false
    signal backRequested()
    signal languageChosen(string value)
    implicitHeight: 40
    spacing: 10
    AppButton { objectName: "readingReturnHub"; visible: header.showBack; text: "‹ 阅读"; flat: true; onClicked: header.backRequested() }
    Text { text: header.title; color: "#293B32"; font.pixelSize: 25; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
    ReadingLanguageSwitch { objectName: "readingHeaderLanguage"; language: header.language; onChosen: function(value) { header.languageChosen(value) } }
}
