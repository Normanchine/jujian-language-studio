import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: home
    objectName: "homeView"
    Connections { target: downloads; function onCompleted(path, title, url, cover) { linkField.clear() } }
    signal openLocal()
    signal recordAudio()
    signal reviewRecording()
    signal recordingSettings()
    signal newDraft()
    signal openProject(string path)
    signal openDraft(string path)
    signal openLibrary()
    signal openWriting()
    signal openSettings()
    property color ink: "#26342C"
    property color muted: "#748178"
    property color themeAccent: "#C94859"
    readonly property int cardGap: height < 720 ? 12 : 16
    readonly property real recentHeight: Math.max(260, Math.min(520,
        height - 16 - mediaImport.height - recordingCard.height - 2 * cardGap))
    readonly property bool compact: recentHeight < 360
    readonly property int videoHeight: Math.floor((recentHeight - cardGap) / 2)
    readonly property int audioHeight: recentHeight - videoHeight - cardGap
    readonly property int audioRowHeight: compact ? 36 : 48
    readonly property int audioLimit: Math.max(1, Math.min(3, Math.floor((audioHeight - 46) / (audioRowHeight + 6))))
    readonly property int draftRowHeight: compact ? 62 : 79
    readonly property int draftLimit: Math.max(1, Math.min(4, Math.floor((recentHeight - 58) / (draftRowHeight + 8))))

    function recentMedia(video) {
        var result = []
        var projects = study.projects
        for (var i = 0; i < projects.length && result.length < (video ? 3 : audioLimit); i++)
            if (projects[i].video === video) result.push(projects[i])
        return result
    }
    function recentDrafts() {
        var result = []
        var drafts = writer.drafts
        for (var i = 0; i < drafts.length && result.length < draftLimit; i++)
            result.push(drafts[i])
        return result
    }
    function clock(ms) {
        var seconds = Math.max(0, Math.floor(ms / 1000))
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
    }

    Flickable {
        id: homeFlick; objectName: "homeFlick"
        anchors.fill: parent; clip: true
        contentWidth: width; contentHeight: contentColumn.height + 16
        interactive: contentHeight > height + 1
        onContentHeightChanged: if (contentHeight <= height + 1) contentY = 0
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            id: homeScroll
            policy: homeFlick.interactive ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff; width: 8
            background: Item { }
            contentItem: Rectangle { implicitWidth: 6; radius: 3
                color: homeScroll.pressed ? "#87998C" : "#B8C7BC" }
        }
        Column {
            id: contentColumn
            x: 10; y: 8; width: parent.width - 20; spacing: home.cardGap

            Rectangle {
                id: mediaImport; objectName: "homeMediaImport"
                width: parent.width; height: Math.max(home.height < 600 ? 112 : 128, heroContent.y + heroContent.height + 12)
                radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                HomeAmbience { anchors.fill: parent; area: "hero" }
                Image {
                    id: heroImage; x: 8; y: 8; width: home.height < 600 ? 96 : 104; height: width
                    source: "../assets/doraemon-reading.png"
                    fillMode: Image.PreserveAspectFit; smooth: true
                }
                Column {
                    id: heroContent
                    x: heroImage.x + heroImage.width + 18; y: home.height < 600 ? 10 : 14
                    width: parent.width - x - 20; spacing: home.height < 600 ? 6 : 8
                    Text { text: "添加音视频"; color: home.ink; font.pixelSize: 18
                        font.family: "Microsoft YaHei UI"; font.weight: Font.DemiBold }
                    RowLayout {
                        width: parent.width; height: 39; spacing: 9
                        TextField {
                            id: linkField; objectName: "mediaLinkField"; Layout.fillWidth: true; Layout.preferredHeight: 39
                            placeholderText: "粘贴 YouTube、B 站或小宇宙单集链接"
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 13
                            selectionColor: settings.palette.selection; selectedTextColor: home.ink
                            background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: linkField.activeFocus ? home.themeAccent : "#DDE2DF" }
                            onTextEdited: downloads.clearPreview()
                            onAccepted: downloads.inspect(text)
                            ContextMenu.menu: AppTextMenu { objectName: "mediaLinkContextMenu"; editor: linkField }
                        }
                        AppButton { text: downloads.inspecting ? "解析中…" : "解析链接"
                            enabled: !downloads.busy && !downloads.network.busy && linkField.text.trim().length > 0
                            onClicked: downloads.inspect(linkField.text) }
                        AppButton { text: "本地文件"; onClicked: home.openLocal() }
                        AppButton { text: "新建作文"; onClicked: home.newDraft() }
                    }
                    Row { spacing: 10
                        AppButton { text: "代理与节点设置"; flat: true; height: home.height < 600 ? 21 : 23; onClicked: home.openSettings() }
                        Text { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 11; color: home.muted
                            text: settings.values.youtube_auto_node ? "YouTube 自动选节点 · 国内来源直连" : "YouTube 使用代理 · 国内来源直连" }
                    }
                    Text { text: downloads.status; visible: downloads.status.length > 0
                        color: downloads.error ? "#B64052" : home.muted
                        width: parent.width; elide: Text.ElideRight; font.pixelSize: 11
                        ToolTip.visible: statusHover.hovered && downloads.status.length > 0
                        ToolTip.text: downloads.status
                        HoverHandler { id: statusHover } }
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
                            RowLayout { width: parent.width; spacing: 10
                                AppCombo { id: downloadFormat; Layout.fillWidth: true; height: 34
                                    model: downloads.formats; textRole: "label" }
                                Text { Layout.maximumWidth: 90; elide: Text.ElideRight
                                    text: downloadFormat.currentIndex >= 0 && downloads.formats.length > downloadFormat.currentIndex
                                          ? downloads.formats[downloadFormat.currentIndex].sizeLabel : ""
                                    color: home.muted; font.pixelSize: 12 }
                            }
                            RowLayout { width: parent.width; height: 36
                                TextField { id: downloadName; objectName: "mediaDownloadName"; Layout.fillWidth: true
                                    text: downloads.title; placeholderText: "保存文件名"
                                    selectionColor: settings.palette.selection; selectedTextColor: home.ink
                                    ContextMenu.menu: AppTextMenu { editor: downloadName }
                                    background: Rectangle { radius: 7; color: "#FAFBFA"; border.color: "#DDE2DF" } }
                                AppButton { text: downloads.downloading ? "下载中…" : "下载并加入资料库"
                                    enabled: !downloads.busy && !downloads.network.busy && downloadFormat.currentIndex >= 0
                                    onClicked: downloads.start(downloadFormat.currentIndex, downloadName.text) }
                                AppButton { visible: downloads.downloading; text: "取消"; onClicked: downloads.cancel() }
                            }
                        }
                    }
                }
                Rectangle { visible: downloads.downloading; anchors.bottom: parent.bottom
                    width: parent.width * downloads.progress; height: 3; color: home.themeAccent }
            }

            Rectangle {
                id: recordingCard; objectName: "homeRecordingCard"
                width: parent.width; height: home.height < 600 ? 92 : 96; radius: 12; color: settings.palette.surface
                border.color: study.recorder.active ? home.themeAccent : "#DFE7E1"
                RowLayout {
                    anchors.fill: parent; anchors.margins: home.height < 600 ? 12 : 14; spacing: 16
                    Rectangle { width: 44; height: 44; radius: 12; color: settings.palette.selection
                        Row { anchors.centerIn: parent; spacing: 3
                            Repeater { model: [10,22,15,28,12]
                                delegate: Rectangle { required property int modelData; width: 3; radius: 1.5
                                    height: study.recorder.active ? Math.max(6,modelData*(.3+Math.sqrt(study.recorder.level))) : modelData
                                    color: home.themeAccent; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        Text { text: study.recorder.active ? "正在录制  " + home.clock(study.recorder.seconds*1000) : "录制电脑声音"
                            color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: study.recorder.active ? "播放结束后停止，也可按 Ctrl + Shift + R。"
                                         : study.recorder.busy ? study.recorder.status : "把正在播放的听力带进句间，停止后试听并归档。"
                            color: home.muted; font.pixelSize: 12
                            Layout.fillWidth: true; elide: Text.ElideRight }
                        RowLayout { spacing: 8
                            AppButton { objectName: "homeRecordingSettings"; text: "录制设置"; flat: true; height: 25
                                onClicked: home.recordingSettings() }
                            AppButton { objectName: "homeRecordingPending"; visible: study.recorder.pending.length>0 || !!study.recorder.review.duration
                                text: "暂存录音 · " + study.recorder.pending.length; flat: true; height: 25
                                enabled: !study.recorder.busy; onClicked: home.reviewRecording() }
                        }
                    }
                    AppButton { objectName: "homeRecordAudio"; text: study.recorder.state==="stopping" ? "保存中…" : study.recorder.active ? "停止录制"
                                                : study.recorder.busy ? "处理中…" : "开始录制"; primary: true; implicitHeight: 40
                        enabled: study.recorder.active ? study.recorder.state!=="stopping" : !study.recorder.busy && !study.busy && !study.enriching
                        onClicked: home.recordAudio() }
                }
            }
            Flow {
                id: recentFlow
                property bool sideBySide: width >= 560
                width: parent.width; spacing: home.cardGap
                Column {
                    width: recentFlow.sideBySide ? Math.floor((parent.width - home.cardGap) * 0.63) : parent.width
                    spacing: home.cardGap
                    Rectangle {
                        id: videoCard; objectName: "homeVideoCard"
                        width: parent.width; height: home.videoHeight; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                        HomeAmbience { anchors.fill: parent; area: "video" }
                        Text { x: 18; y: 15; text: "最近视频"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                            objectName: "homeAllVideos"
                            text: "查看全部"; flat: true; onClicked: home.openLibrary() }
                        Row {
                            id: videoRow
                            x: 18; y: 44; width: parent.width - 36; height: parent.height - 54; spacing: 12
                            Repeater {
                                model: home.recentMedia(true)
                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    objectName: "homeRecentVideo_" + index
                                    width: Math.min(175, (videoRow.width - 24) / 3)
                                    height: videoRow.height; color: "transparent"
                                    Rectangle {
                                        id: thumbnail
                                        width: parent.width; height: Math.max(40,Math.min(112,width*.64,videoRow.height-(home.compact ? 38 : 60)))
                                        radius: 7; color: "#E8EDE9"; clip: true
                                        Image { anchors.fill: parent; source: modelData.coverUrl
                                            fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready }
                                        Text { anchors.centerIn: parent; text: "▶"; color: "#A6B1A9"
                                            font.pixelSize: 27; visible: parent.children[0].status !== Image.Ready }
                                    }
                                    Text { y: thumbnail.height+5; width: parent.width; text: modelData.title; elide: Text.ElideRight
                                        color: home.ink; font.pixelSize: 12 }
                                    Text { visible: !home.compact; y: thumbnail.height+25; text: modelData.available ? modelData.state : "源文件已丢失"
                                        color: modelData.available ? home.muted : "#B64052"; font.pixelSize: 11 }
                                    Rectangle { y: thumbnail.height+(home.compact ? 28 : 48); width: parent.width; height: 3; radius: 2; color: "#E8ECE9"
                                        Rectangle { width: parent.width * modelData.progress; height: parent.height
                                            radius: 2; color: home.themeAccent } }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        ToolTip.visible: containsMouse
                                        ToolTip.text: modelData.title+" · "+(modelData.available ? modelData.state : "源文件已丢失")
                                        enabled: modelData.available; onClicked: home.openProject(modelData.path) }
                                }
                            }
                        }
                        Text { anchors.centerIn: parent; visible: home.recentMedia(true).length === 0
                            text: "还没有视频项目"; color: home.muted; font.pixelSize: 13 }
                    }
                    Rectangle {
                        objectName: "homeAudioCard"
                        width: parent.width; height: home.audioHeight; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                        HomeAmbience { anchors.fill: parent; area: "audio" }
                        Text { x: 18; y: 15; text: "最近音频"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                        AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                            objectName: "homeAllAudio"
                            text: "查看全部"; flat: true; onClicked: home.openLibrary() }
                        Column {
                            x: 18; y: 44; width: parent.width - 36; spacing: 6
                            Repeater {
                                model: home.recentMedia(false)
                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    objectName: "homeRecentAudio_" + index
                                    width: parent.width; height: home.audioRowHeight; radius: 7
                                    color: audioHover.containsMouse ? "#F5F7F5" : "#FAFBFA"
                                    Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "♫"
                                        color: home.themeAccent; font.pixelSize: 19 }
                                    Text { x: 40; y: home.compact ? 3 : 6; width: parent.width - 140; text: modelData.title
                                        elide: Text.ElideRight; color: home.ink; font.pixelSize: 12 }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 10; y: home.compact ? 3 : 6
                                        text: modelData.available ? modelData.state : "文件缺失"
                                        color: modelData.available ? home.muted : "#B64052"; font.pixelSize: 11 }
                                    Rectangle { x: 40; y: parent.height-11; width: parent.width - 50; height: 3; radius: 2; color: "#E8ECE9"
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
                    objectName: "homeWritingCard"
                    width: recentFlow.sideBySide ? parent.width - Math.floor((parent.width - home.cardGap) * 0.63) - home.cardGap : parent.width
                    height: home.recentHeight; radius: 12; color: "#FFFFFF"; border.color: "#E2E6E2"
                    HomeAmbience { anchors.fill: parent; area: "writing" }
                    Text { x: 18; y: 15; text: "最近作文"; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                    AppButton { anchors.right: parent.right; anchors.rightMargin: 16; y: 8
                        objectName: "homeAllWriting"
                        text: "查看全部"; flat: true; onClicked: home.openWriting() }
                    Column {
                        x: 14; y: 53; width: parent.width - 28; spacing: 8
                        Repeater {
                            model: home.recentDrafts()
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                objectName: "homeRecentDraft_" + index
                                width: parent.width; height: home.draftRowHeight; radius: 8
                                color: draftHover.containsMouse ? "#F6F7F6" : "#FAFBFA"
                                border.color: "#EDF0ED"
                                Text { x: 12; y: home.compact ? 9 : 12; width: parent.width - 24; text: modelData.title
                                    elide: Text.ElideRight; color: home.ink; font.pixelSize: 13; font.weight: Font.DemiBold }
                                Text { x: 12; y: home.compact ? 32 : 38; text: modelData.language === "en" ? "英语" : "日语"
                                    color: home.muted; font.pixelSize: 11 }
                                Text { anchors.right: parent.right; anchors.rightMargin: 12; y: home.compact ? 32 : 38
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
