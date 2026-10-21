import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: home
    signal openLocal()
    signal newDraft()
    signal openProject(string path)
    signal openDraft(string path)
    signal openLibrary()
    signal openWriting()
    property color ink: "#26342C"
    property color muted: "#748178"
    property color themeAccent: "#C94859"

    function recentMedia(video) {
        var result = []
        for (var i = 0; i < study.projects.length && result.length < 3; i++)
            if (study.projects[i].video === video) result.push(study.projects[i])
        return result
    }
    function recentDrafts() {
        var result = []
        for (var i = 0; i < writer.drafts.length && result.length < 4; i++)
            result.push(writer.drafts[i])
        return result
    }
    function clock(ms) {
        var seconds = Math.max(0, Math.floor(ms / 1000))
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
    }

    Flickable {
        anchors.fill: parent; clip: true
        contentWidth: width; contentHeight: contentColumn.height + 32
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            id: homeScroll
            policy: ScrollBar.AsNeeded; width: 8
            background: Item { }
            contentItem: Rectangle { implicitWidth: 6; radius: 3
                color: homeScroll.pressed ? "#87998C" : "#B8C7BC" }
        }
        Column {
            id: contentColumn
            x: 10; y: 8; width: parent.width - 20; spacing: 18

            Rectangle {
                width: parent.width; height: downloads.ready ? 276 : 132
                radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                Image {
                    x: 8; y: 7; width: 116; height: 116
                    source: "../assets/doraemon-reading.png"
                    fillMode: Image.PreserveAspectFit; smooth: true
                }
                Column {
                    x: 133; y: 18; width: parent.width - 155; spacing: 10
                    Text { text: "添加音视频"; color: home.ink; font.pixelSize: 18
                        font.family: "Microsoft YaHei UI"; font.weight: Font.DemiBold }
                    RowLayout {
                        width: parent.width; height: 39; spacing: 9
                        TextField {
                            id: linkField; Layout.fillWidth: true; Layout.preferredHeight: 39
                            placeholderText: "粘贴 B 站或小宇宙单集链接"
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 13
                            background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: linkField.activeFocus ? home.themeAccent : "#DDE2DF" }
                            onTextEdited: downloads.clearPreview()
                            onAccepted: downloads.inspect(text)
                        }
                        AppButton { text: downloads.inspecting ? "解析中…" : "解析链接"
                            enabled: !downloads.busy && linkField.text.trim().length > 0
                            onClicked: downloads.inspect(linkField.text) }
                        AppButton { text: "本地文件"; onClicked: home.openLocal() }
                        AppButton { text: "新建作文"; onClicked: home.newDraft() }
                    }
                    Text { text: downloads.status; visible: downloads.status.length > 0
                        color: downloads.error ? "#B64052" : home.muted
                        width: parent.width; elide: Text.ElideRight; font.pixelSize: 11 }
                    Row {
                        visible: downloads.ready; width: parent.width; spacing: 16
                        Rectangle {
                            width: 116; height: 112; radius: 7; color: "#E6E9E7"; clip: true
                            Image { anchors.fill: parent; source: downloads.thumbnailUrl
                                fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready }
                            Text { anchors.centerIn: parent; text: "▶"; font.pixelSize: 25
                                color: "#8E9A91"; visible: parent.children[0].status !== Image.Ready }
                        }
                        Column {
                            width: parent.width - 132; spacing: 6
                            Text { text: downloads.title; width: parent.width; elide: Text.ElideRight
                                color: home.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                            Row { spacing: 10
                                AppCombo { id: downloadFormat; width: 280; height: 34
                                    model: downloads.formats; textRole: "label" }
                                Text { anchors.verticalCenter: parent.verticalCenter
                                    text: downloadFormat.currentIndex >= 0 && downloads.formats.length > downloadFormat.currentIndex
                                          ? downloads.formats[downloadFormat.currentIndex].sizeLabel : ""
                                    color: home.muted; font.pixelSize: 12 }
                            }
                            RowLayout { width: parent.width; height: 36
                                TextField { id: downloadName; Layout.fillWidth: true
                                    text: downloads.title; placeholderText: "保存文件名"
                                    background: Rectangle { radius: 7; color: "#FAFBFA"; border.color: "#DDE2DF" } }
                                AppButton { text: downloads.downloading ? "下载中…" : "下载并加入资料库"
                                    enabled: !downloads.busy && downloadFormat.currentIndex >= 0
                                    onClicked: downloads.start(downloadFormat.currentIndex, downloadName.text) }
                                AppButton { visible: downloads.downloading; text: "取消"; onClicked: downloads.cancel() }
                            }
                        }
                    }
                }
                Rectangle { visible: downloads.downloading; anchors.bottom: parent.bottom
                    width: parent.width * downloads.progress; height: 3; color: home.themeAccent }
            }

            Flow {
                width: parent.width; spacing: 18
                Column {
                    width: parent.width >= 720 ? Math.floor((parent.width - 18) * 0.63) : parent.width
                    spacing: 18
                    Rectangle {
                        width: parent.width; height: 245; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                        Text { x: 18; y: 15; text: "最近视频"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                            text: "查看全部"; flat: true; onClicked: home.openLibrary() }
                        Row {
                            x: 18; y: 51; spacing: 12
                            Repeater {
                                model: home.recentMedia(true)
                                delegate: Rectangle {
                                    required property var modelData
                                    width: Math.min(175, (home.width >= 720 ? (home.width - 250) * 0.63 : home.width - 80) / 3)
                                    height: 174; color: "transparent"
                                    Rectangle {
                                        width: parent.width; height: 112; radius: 7; color: "#E8EDE9"; clip: true
                                        Image { anchors.fill: parent; source: modelData.coverUrl
                                            fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready }
                                        Text { anchors.centerIn: parent; text: "▶"; color: "#A6B1A9"
                                            font.pixelSize: 27; visible: parent.children[0].status !== Image.Ready }
                                    }
                                    Text { y: 117; width: parent.width; text: modelData.title; elide: Text.ElideRight
                                        color: home.ink; font.pixelSize: 12 }
                                    Text { y: 137; text: modelData.available ? modelData.state : "源文件已丢失"
                                        color: modelData.available ? home.muted : "#B64052"; font.pixelSize: 11 }
                                    Rectangle { y: 159; width: parent.width; height: 3; radius: 2; color: "#E8ECE9"
                                        Rectangle { width: parent.width * modelData.progress; height: parent.height
                                            radius: 2; color: home.themeAccent } }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        enabled: modelData.available; onClicked: home.openProject(modelData.path) }
                                }
                            }
                        }
                        Text { anchors.centerIn: parent; visible: home.recentMedia(true).length === 0
                            text: "还没有视频项目"; color: home.muted; font.pixelSize: 13 }
                    }
                    Rectangle {
                        width: parent.width; height: 226; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                        Text { x: 18; y: 15; text: "最近音频"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                            text: "查看全部"; flat: true; onClicked: home.openLibrary() }
                        Column {
                            x: 18; y: 50; width: parent.width - 36; spacing: 6
                            Repeater {
                                model: home.recentMedia(false)
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent.width; height: 48; radius: 7
                                    color: audioHover.containsMouse ? "#F5F7F5" : "#FAFBFA"
                                    Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "♫"
                                        color: home.themeAccent; font.pixelSize: 19 }
                                    Text { x: 40; y: 6; width: parent.width - 140; text: modelData.title
                                        elide: Text.ElideRight; color: home.ink; font.pixelSize: 12 }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 10; y: 6
                                        text: modelData.available ? modelData.state : "文件缺失"
                                        color: modelData.available ? home.muted : "#B64052"; font.pixelSize: 11 }
                                    Rectangle { x: 40; y: 37; width: parent.width - 50; height: 3; radius: 2; color: "#E8ECE9"
                                        Rectangle { width: parent.width * modelData.progress; height: parent.height
                                            radius: 2; color: home.themeAccent } }
                                    MouseArea { id: audioHover; anchors.fill: parent; hoverEnabled: true
                                        enabled: modelData.available; cursorShape: Qt.PointingHandCursor
                                        onClicked: home.openProject(modelData.path) }
                                }
                            }
                        }
                        Text { anchors.centerIn: parent; visible: home.recentMedia(false).length === 0
                            text: "还没有音频项目"; color: home.muted; font.pixelSize: 13 }
                    }
                }
                Rectangle {
                    width: parent.width >= 720 ? parent.width - Math.floor((parent.width - 18) * 0.63) - 18 : parent.width
                    height: 489; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                    Text { x: 18; y: 15; text: "最近作文"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                    AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                        text: "查看全部"; flat: true; onClicked: home.openWriting() }
                    Column {
                        x: 14; y: 53; width: parent.width - 28; spacing: 8
                        Repeater {
                            model: home.recentDrafts()
                            delegate: Rectangle {
                                required property var modelData
                                width: parent.width; height: 79; radius: 8
                                color: draftHover.containsMouse ? "#F6F7F6" : "#FAFBFA"
                                border.color: "#EDF0ED"
                                Text { x: 12; y: 12; width: parent.width - 24; text: modelData.title
                                    elide: Text.ElideRight; color: home.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                Text { x: 12; y: 38; text: modelData.language === "en" ? "英语" : "日语"
                                    color: home.muted; font.pixelSize: 11 }
                                Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 38
                                    text: modelData.updatedLabel; color: home.muted; font.pixelSize: 11 }
                                MouseArea { id: draftHover; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: home.openDraft(modelData.path) }
                            }
                        }
                    }
                    Text { anchors.centerIn: parent; visible: home.recentDrafts().length === 0
                        text: "还没有作文草稿"; color: home.muted; font.pixelSize: 13 }
                }
            }
        }
    }
}
