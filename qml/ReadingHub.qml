import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: hub
    objectName: "readingHub"
    property string language: "en"
    property var resumeArticle: ({})
    property var nextArticle: ({})
    property var favoriteItems: []
    property var materialItems: []
    property int favoriteCount: 0
    property int grammarFavoriteCount: 0
    property int studyFavoriteCount: 0
    property int materialCount: 0
    property bool practiceComplete: false
    property bool compact: width < 850
    property color ink: "#293B32"
    property color muted: "#7B8981"
    property var featured: resumeArticle.id ? resumeArticle : nextArticle
    signal languageChosen(string value)
    signal openLibrary()
    signal openFavorites()
    signal openGrammarFavorites()
    signal openStudyFavorites()
    signal openReview()
    signal openArticle(var article, string mode)
    ColumnLayout {
        anchors.fill: parent; spacing: 16
        ReadingPageHeader { Layout.fillWidth: true; language: hub.language
            onLanguageChosen: function(value) { hub.languageChosen(value) } }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: hub.compact ? 120 : 128
            radius: 14; color: settings.palette.surface; border.color: "#DCE6DE"
            RowLayout {
                anchors.fill: parent; anchors.margins: hub.compact ? 18 : 24; spacing: 20
                ColumnLayout { Layout.fillWidth: true; spacing: 8
                    Text { text: hub.resumeArticle.id ? "上次未完成" : hub.practiceComplete ? "练习进度" : hub.featured.hasQuestions === false ? "开始一篇阅读" : "接着做下一篇"; color: settings.palette.accent; font.pixelSize: 11 }
                    Text { text: hub.practiceComplete ? "全部练习已完成" : hub.featured.title || "还没有阅读材料"; color: hub.ink; font.pixelSize: hub.compact ? 18 : 21
                        font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                    RowLayout { Layout.fillWidth: true; spacing: 14
                        Text { text: hub.featured.setTitle || ""; color: hub.muted; font.pixelSize: 11; elide: Text.ElideRight; Layout.maximumWidth: 180 }
                        ReadingProgress { visible: !!hub.resumeArticle.id; Layout.preferredWidth: 210; Layout.maximumWidth: 230
                            label: ""; value: (hub.featured.answered || 0)/(hub.featured.questionCount || 5)
                            detail: (hub.featured.answered || 0)+"/"+(hub.featured.questionCount || 5)+" 题" }
                    }
                }
                AppButton { objectName: "readingHubResume"; enabled: !!hub.featured.id || hub.practiceComplete; primary: true
                    text: hub.practiceComplete ? "查看复盘  ›" : hub.resumeArticle.id ? "继续答题  ›" : hub.featured.hasQuestions === false ? "开始精读  ›" : "开始下一篇  ›"
                    onClicked: hub.practiceComplete ? hub.openReview() : hub.openArticle(hub.featured, hub.featured.hasQuestions === false ? "intensive" : "practice") }
            }
        }
        GridLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; columns: hub.compact ? 1 : 2; columnSpacing: 16; rowSpacing: 14
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 530; Layout.preferredHeight: hub.compact ? 1 : 420
                radius: 14; color: settings.palette.surface; border.color: "#DFE7E1"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: hub.compact ? 16 : 20; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "材料库"; color: hub.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                        Text { text: hub.materialCount + " 篇"; color: hub.muted; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        AppButton { objectName: "readingHubLibrary"; text: "查看全部  ›"; flat: true; onClicked: hub.openLibrary() }
                    }
                    ListView {
                        id: materials; objectName: "readingHubMaterialPreview"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        model: hub.materialItems; interactive: false; spacing: 0
                        delegate: Button {
                            id: row; required property var modelData; width: materials.width; height: hub.compact ? 60 : 84; hoverEnabled: true
                            objectName: "readingHubMaterial_" + modelData.id
                            background: Rectangle { radius: 8; color: row.hovered ? settings.palette.selection : "transparent"
                                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#E7EDE8" } }
                            contentItem: ColumnLayout { spacing: 7
                                Text { text: row.modelData.title; font.pixelSize: 14; font.weight: Font.DemiBold; color: hub.ink
                                    Layout.fillWidth: true; elide: Text.ElideRight }
                                RowLayout { Layout.fillWidth: true
                                    Text { text: row.modelData.setTitle; font.pixelSize: 11; color: hub.muted; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: row.modelData.hasQuestions === false ? "精读  ›" : row.modelData.practice === "done" ? "复盘  ›" : row.modelData.practice === "progress" ? "未完成  ›" : "未做  ›"
                                        font.pixelSize: 11; color: row.modelData.practice === "done" ? settings.palette.accent : hub.muted }
                                }
                            }
                            leftPadding: 2; rightPadding: 8; topPadding: hub.compact ? 8 : 15; bottomPadding: hub.compact ? 8 : 15
                            onClicked: hub.openArticle(modelData, modelData.hasQuestions === false ? "intensive" : "practice")
                        }
                        Text { visible: !hub.materialItems.length; anchors.centerIn: parent; text: "还没有材料"; color: hub.muted; font.pixelSize: 12 }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 350; Layout.preferredHeight: hub.compact ? 1 : 420
                radius: 14; color: settings.palette.surface; border.color: "#DFE7E1"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: hub.compact ? 16 : 20; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        Text { text: "我的收藏"; color: hub.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                        Text { text: hub.favoriteCount; color: hub.muted; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        AppButton { objectName: "readingHubGrammarFavorites";visible: hub.language==="ja"; text: "语法 · "+hub.grammarFavoriteCount; flat: true; onClicked: hub.openGrammarFavorites() }
                        AppButton { objectName: "readingHubStudyFavorites";visible: hub.language==="en";text: "词句 · "+hub.studyFavoriteCount;flat: true;onClicked: hub.openStudyFavorites() }
                        AppButton { objectName: "readingHubFavorites"; text: "查看全部  ›"; flat: true; onClicked: hub.openFavorites() }
                    }
                    ListView {
                        id: favorites; objectName: "readingHubFavoritePreview"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        model: hub.favoriteItems; interactive: false
                        delegate: Button {
                            id: favorite; required property var modelData; width: favorites.width; height: hub.compact ? 60 : 84; hoverEnabled: true
                            objectName: "readingHubFavorite_" + modelData.id
                            background: Rectangle { radius: 8; color: favorite.hovered ? settings.palette.selection : "transparent"
                                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#E7EDE8" } }
                            contentItem: ColumnLayout { spacing: 7
                                Text { text: favorite.modelData.title; font.pixelSize: 14; font.weight: Font.DemiBold; color: hub.ink
                                    Layout.fillWidth: true; elide: Text.ElideRight }
                                Text { text: "★  " + favorite.modelData.setTitle; color: hub.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                            leftPadding: 2; rightPadding: 8; topPadding: hub.compact ? 8 : 15; bottomPadding: hub.compact ? 8 : 15
                            onClicked: hub.openArticle(modelData, "intensive")
                        }
                        Text { visible: !hub.favoriteItems.length; anchors.centerIn: parent; text: "还没有收藏"; color: hub.muted; font.pixelSize: 12 }
                    }
                }
            }
        }
    }
}
