import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia

ApplicationWindow {
    id: root
    width: 1180
    height: 820
    minimumWidth: 900
    minimumHeight: 640
    visible: true
    title: study.hasMedia ? "句间 — " + study.title : "句间"
    color: "#F4F5F4"

    property bool showList: true
    property bool textHidden: false
    property bool scrubbing: false
    property string page: "home"
    property bool sidebarCollapsed: false
    property int pendingResumeMs: 0
    onClosing: {
        if (study.hasMedia) study.savePlayback(player.position)
        writingView.saveNow()
    }
    property var rates: [0.75, 1.0, 1.25, 1.5]
    property int rateIndex: 1

    function timeText(ms) {
        var secs = Math.max(0, Math.floor(ms / 1000))
        return Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0")
    }
    function categoryColor(category) {
        if (category === "noun") return "#E99AAA"
        if (category === "verb") return "#9BCC65"
        if (category === "adjective") return "#E9C966"
        if (category === "adverb") return "#8BC9D2"
        if (category === "particle") return "#B8C6D4"
        if (category === "auxiliary") return "#C8BDDC"
        return "transparent"
    }

    component ActionButton: Rectangle {
        id: control
        property string label: ""
        property bool primary: false
        property bool selected: false
        signal clicked()
        implicitWidth: Math.max(68, caption.implicitWidth + 26)
        implicitHeight: 36
        radius: 8
        color: !enabled ? "#EFF0EF"
             : primary ? (pointer.containsMouse ? "#B4394B" : "#C94859")
             : selected ? (pointer.containsMouse ? "#F6DDE2" : "#FAE9ED")
             : pointer.containsMouse ? "#E9ECEA" : "#FFFFFF"
        border.color: !enabled ? "#E6E8E6" : primary ? "#C94859" : selected ? "#E7B3BD" : "#DDE2DF"
        border.width: 1
        Text {
            id: caption
            anchors.centerIn: parent
            text: control.label
            color: !control.enabled ? "#9DA49F" : control.primary ? "#FFFFFF" : control.selected ? "#A83A4C" : "#26332D"
            font.family: "Microsoft YaHei UI"
            font.pixelSize: 13
            font.weight: Font.DemiBold
            renderType: Text.NativeRendering
        }
        MouseArea {
            id: pointer
            anchors.fill: parent
            enabled: control.enabled
            hoverEnabled: true
            cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: control.clicked()
        }
    }

    component NavButton: Rectangle {
        id: nav
        property string label: ""
        property string iconName: "home"
        property bool selected: false
        signal clicked()
        height: 48
        radius: 8
        color: selected ? "#F2F3F1" : navHover.containsMouse ? "#F5F6F4" : "transparent"
        Rectangle { x: 0; y: 10; width: 3; height: 28; radius: 2
            color: nav.selected ? "#C94859" : "transparent" }
        Row {
            anchors.left: parent.left; anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter; spacing: 16
            NavGlyph { width: 22; height: 22; kind: nav.iconName; active: nav.selected }
            Text { visible: !root.sidebarCollapsed; text: nav.label
                color: nav.selected ? "#2A3B31" : "#536158"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 14
                font.weight: nav.selected ? Font.DemiBold : Font.Normal
                anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: navHover; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; onClicked: nav.clicked() }
    }

    MediaPlayer {
        id: player
        objectName: "mediaPlayer"
        source: study.mediaUrl
        audioOutput: AudioOutput { id: sound; volume: 0.85 }
        videoOutput: videoView
        onMediaStatusChanged: {
            if (root.pendingResumeMs > 0 && (mediaStatus === MediaPlayer.LoadedMedia
                    || mediaStatus === MediaPlayer.BufferedMedia)) {
                position = root.pendingResumeMs
                root.pendingResumeMs = 0
            }
        }
        onPlaybackStateChanged: {
            if (playbackState !== MediaPlayer.PlayingState && study.hasMedia
                    && root.pendingResumeMs === 0
                    && (mediaStatus === MediaPlayer.LoadedMedia || mediaStatus === MediaPlayer.BufferedMedia))
                study.savePlayback(position)
        }
        onPositionChanged: {
            if (!root.scrubbing && study.loopSentence && study.sentenceCount > 0
                    && playbackState === MediaPlayer.PlayingState) {
                var current = study.currentSentence
                var end = Math.round(current.end * 1000)
                if (position >= end && position < end + 400) {
                    position = Math.round(current.start * 1000)
                    return
                }
            }
            study.updatePlayback(position)
        }
    }
    Connections {
        target: study
        function onMediaChanged() {
            root.pendingResumeMs = study.resumeMs
            if (study.hasMedia) root.page = "listen"
            else { player.stop(); root.page = "library" }
        }
        function onSeekRequested(ms) {
            player.position = ms
            player.play()
        }
    }
    Connections {
        target: downloads
        function onCompleted(path, title, url, cover) { study.registerDownloaded(path, title, url, cover) }
    }
    Timer { interval: 5000; repeat: true
        running: player.playbackState === MediaPlayer.PlayingState
        onTriggered: study.savePlayback(player.position) }

    FileDialog {
        id: mediaPicker
        title: "打开本地音频或视频"
        nameFilters: ["媒体文件 (*.mp3 *.m4a *.m4s *.mp4 *.wav *.flac *.mov *.mkv *.webm)", "所有文件 (*)"]
        onAccepted: {
            if (study.hasMedia) study.savePlayback(player.position)
            player.pause()
            study.openMedia(selectedFile.toString())
        }
    }
    FileDialog {
        id: transcriptPicker
        title: "导入 JSON 字幕"
        nameFilters: ["JSON 字幕 (*.json)"]
        onAccepted: study.importTranscript(selectedFile.toString())
    }

    Rectangle {
        id: sidebar
        anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
        width: root.sidebarCollapsed ? 64 : 216; color: "#FAFBF9"
        Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: "#E1E5E2" }
        Row {
            x: 15; y: 15; spacing: 11
            Image { width: 34; height: 34; source: "../assets/jujian.png"
                fillMode: Image.PreserveAspectFit; smooth: true }
            Column { visible: !root.sidebarCollapsed; spacing: 1
                Text { text: "句间"; color: "#26372F"
                    font.family: "Microsoft YaHei UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                Text { text: "听读与写作"; color: "#8A968D"
                    font.family: "Microsoft YaHei UI"; font.pixelSize: 10 }
            }
        }
        Column {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 8; anchors.rightMargin: 8; y: 89; spacing: 4
            NavButton { width: parent.width; label: "首页"; iconName: "home"; selected: root.page === "home"
                onClicked: { player.pause(); study.savePlayback(player.position); study.refreshProjects(); root.page = "home" } }
            NavButton { width: parent.width; label: "精听"; iconName: "listen"; selected: root.page === "listen"
                onClicked: { if (!study.hasMedia) study.refreshProjects(); root.page = study.hasMedia ? "listen" : "library" } }
            NavButton { width: parent.width; label: "写作"; iconName: "writing"; selected: root.page === "writing"
                onClicked: { writingView.showLibrary(); root.page = "writing" } }
            NavButton { width: parent.width; label: "资料库"; iconName: "library"; selected: root.page === "library"
                onClicked: { study.refreshProjects(); root.page = "library" } }
            NavButton { width: parent.width; label: "笔记"; iconName: "notes"; selected: root.page === "notes"
                onClicked: root.page = "notes" }
            NavButton { width: parent.width; label: "设置"; iconName: "settings"; selected: root.page === "settings"
                onClicked: root.page = "settings" }
        }
        Rectangle { x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
            width: parent.width - 16; height: 40; radius: 8
            color: collapseHover.containsMouse ? "#F0F2EF" : "transparent"
            Text { anchors.centerIn: parent; text: root.sidebarCollapsed ? "›" : "‹   收起侧栏"
                color: "#718077"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
            MouseArea { id: collapseHover; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.sidebarCollapsed = !root.sidebarCollapsed }
        }
    }

    Rectangle {
        id: toolbar
        anchors.left: sidebar.right; anchors.right: parent.right; anchors.top: parent.top
        height: 62; color: "#FFFFFF"
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#E1E5E2" }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 18; spacing: 7
            Text { Layout.fillWidth: true; Layout.minimumWidth: 70
                text: root.page === "listen" ? study.title : ({home:"首页", writing:"写作", library:"资料库", notes:"笔记", settings:"设置"}[root.page] || "首页")
                elide: Text.ElideMiddle; color: "#27362D"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 15; font.weight: Font.DemiBold }
            ComboBox {
                id: languageChoice; visible: root.page === "listen"
                Layout.preferredWidth: 112; Layout.preferredHeight: 36
                enabled: study.hasMedia && !study.busy && !study.enriching
                model: ["自动识别", "日语转写", "英语转写"]
                currentIndex: study.transcriptionLanguage === "en" ? 2 : (study.transcriptionLanguage === "ja" ? 1 : 0)
                onActivated: study.setTranscriptionLanguage(["auto", "ja", "en"][currentIndex])
                contentItem: Text { text: languageChoice.displayText; leftPadding: 10; rightPadding: 20
                    verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                    color: languageChoice.enabled ? "#26332D" : "#9DA49F"
                    font.family: "Microsoft YaHei UI"; font.pixelSize: 13 }
                indicator: Text { x: parent.width - 21; anchors.verticalCenter: parent.verticalCenter
                    text: "⌄"; color: "#69776F"; font.pixelSize: 16 }
                background: Rectangle { radius: 8; color: languageChoice.pressed ? "#F6DDE2" : "#FFFFFF"
                    border.color: languageChoice.activeFocus ? "#C94859" : "#DDE2DF" }
                delegate: ItemDelegate { width: languageChoice.width; text: modelData
                    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
                    highlighted: languageChoice.highlightedIndex === index }
                popup: Popup { y: languageChoice.height + 4; width: languageChoice.width
                    implicitHeight: contentItem.implicitHeight + 8; padding: 4
                    contentItem: ListView { clip: true; implicitHeight: contentHeight
                        model: languageChoice.popup.visible ? languageChoice.delegateModel : null
                        currentIndex: languageChoice.highlightedIndex }
                    background: Rectangle { radius: 8; color: "#FFFFFF"; border.color: "#DDE2DF" } }
            }
            ActionButton { visible: root.page === "listen"; label: study.busy ? "正在转写…" : "转写整段"
                enabled: study.hasMedia && !study.busy && !study.enriching; onClicked: study.transcribe() }
            ActionButton { visible: root.page === "listen" && root.width >= 1160; label: "导入字幕"
                enabled: study.hasMedia && !study.busy && !study.enriching; onClicked: transcriptPicker.open() }
            ActionButton { visible: root.page === "listen" && root.width >= 1160; label: "中文翻译"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onClicked: study.startTranslation(true) }
            ActionButton { visible: root.page === "listen" && root.width >= 1160
                label: study.contentLanguage === "en" ? "句子解释" : "语法解析"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onClicked: study.startEnrichment(true) }
            ActionButton { visible: root.page === "listen" && root.width >= 1160
                label: root.showList ? "收起字幕" : "显示字幕"; enabled: study.hasMedia
                onClicked: root.showList = !root.showList }
            ActionButton { visible: root.page === "listen" && root.width < 1160; label: "更多"
                onClicked: moreMenu.open() }
            ActionButton { visible: study.enriching && root.page === "listen"; label: "停止处理"
                onClicked: study.stopEnrichment() }
            ActionButton { visible: root.page === "listen"; label: "打开文件"
                enabled: !study.busy && !study.enriching
                onClicked: mediaPicker.open() }
        }
        Menu { id: moreMenu; x: toolbar.width - width - 18; y: toolbar.height - 2
            MenuItem { text: "导入字幕"; enabled: study.hasMedia && !study.busy && !study.enriching; onTriggered: transcriptPicker.open() }
            MenuItem { text: "中文翻译"; enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onTriggered: study.startTranslation(true) }
            MenuItem { text: study.contentLanguage === "en" ? "句子解释" : "语法解析"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onTriggered: study.startEnrichment(true) }
            MenuItem { text: root.showList ? "收起字幕" : "显示字幕"; onTriggered: root.showList = !root.showList }
        }
    }

    Rectangle {
        id: statusBar
        anchors.left: sidebar.right; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 29; color: "#FFFFFF"
        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: "#E1E5E2" }
        Text {
            x: 20; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 40
            text: player.errorString && root.page === "listen" ? "播放错误：" + player.errorString
                  : root.page === "listen" && study.currentSentence.suggestion ? study.currentSentence.suggestion
                  : root.page === "writing" || root.page === "notes" ? writer.status
                  : root.page === "settings" ? settings.status
                  : root.page === "home" && downloads.status ? downloads.status : study.status
            elide: Text.ElideRight
            color: player.errorString ? "#B63C4D" : "#68766D"
            font.family: "Microsoft YaHei UI"; font.pixelSize: 11
        }
    }

    Item {
        id: workspace
        anchors.left: sidebar.right; anchors.right: parent.right
        anchors.top: toolbar.bottom; anchors.bottom: statusBar.top
        anchors.margins: 16

        HomeView {
            anchors.fill: parent; visible: root.page === "home"
            onOpenLocal: mediaPicker.open()
            onNewDraft: { writer.newDraft("ja"); writingView.libraryMode = false; root.page = "writing" }
            onOpenProject: { study.savePlayback(player.position); study.openProject(path) }
            onOpenDraft: { writer.openDraft(path); writingView.libraryMode = false; root.page = "writing" }
            onOpenLibrary: { study.refreshProjects(); root.page = "library" }
            onOpenWriting: { writer.refresh(); writingView.showLibrary(); root.page = "writing" }
        }
        LibraryView { anchors.fill: parent; visible: root.page === "library"
            onOpenProject: { study.savePlayback(player.position); study.openProject(path) } }
        WritingView { id: writingView; anchors.fill: parent; visible: root.page === "writing"
            onOpenNotes: { writer.refresh(); root.page = "notes" } }
        NotesView { anchors.fill: parent; visible: root.page === "notes" }
        SettingsView { anchors.fill: parent; visible: root.page === "settings" }

        Item {
            id: leftPane
            visible: root.page === "listen"
            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
            width: parent.width - (root.showList && study.hasMedia ? 312 : 0)

            Rectangle {
                id: mediaFrame
                x: 0; y: 0; width: parent.width
                height: !study.hasMedia ? leftPane.height
                     : study.hasVideo ? Math.min(320, Math.max(220, leftPane.height * 0.43))
                     : 96
                radius: 10
                color: study.hasVideo ? "#1D2320" : study.hasMedia ? "#E7DFDE" : "#E9ECE9"
                border.color: study.hasMedia && !study.hasVideo ? "#D8CFCE" : "transparent"
                clip: true
                VideoOutput {
                    id: videoView
                    anchors.fill: parent
                    visible: study.hasVideo
                    fillMode: VideoOutput.PreserveAspectFit
                }
                Row {
                    x: 24; anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 48; spacing: 17
                    visible: study.hasMedia && !study.hasVideo
                    Text {
                        text: "♫"; color: "#B9495A"; font.pixelSize: 32
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Column {
                        width: parent.width - 65; spacing: 5
                        Text {
                            width: parent.width; text: study.title; elide: Text.ElideMiddle
                            color: "#2A302C"; font.family: "Microsoft YaHei UI"; font.pixelSize: 17
                        }
                        Text {
                            text: "音频  ·  " + root.timeText(study.durationMs)
                            color: "#6D756F"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                        }
                    }
                }
                Column {
                    anchors.centerIn: parent; spacing: 15
                    visible: !study.hasMedia
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "打开本地音频或视频"; color: "#35433A"
                        font.family: "Microsoft YaHei UI"; font.pixelSize: 20; font.weight: Font.DemiBold
                    }
                    ActionButton { anchors.horizontalCenter: parent.horizontalCenter; label: "选择文件"; primary: true; onClicked: mediaPicker.open() }
                }
            }

            Rectangle {
                id: transport
                x: 0; y: parent.height - height; width: parent.width; height: 112
                visible: study.hasMedia
                radius: 10; color: "#FFFFFF"; border.color: "#DFE4E0"
                Slider {
                    id: progress
                    x: 19; y: 10; width: parent.width - 38; height: 26
                    from: 0; to: Math.max(1, player.duration); value: player.position
                    enabled: study.hasMedia
                    background: Rectangle {
                        x: progress.leftPadding
                        y: progress.topPadding + progress.availableHeight / 2 - height / 2
                        width: progress.availableWidth; height: 4; radius: 2; color: "#E1E6E2"
                        Rectangle { width: progress.visualPosition * parent.width; height: parent.height; radius: 2; color: "#C94859" }
                    }
                    handle: Rectangle {
                        x: progress.leftPadding + progress.visualPosition * (progress.availableWidth - width)
                        y: progress.topPadding + progress.availableHeight / 2 - height / 2
                        width: 15; height: 15; radius: 8; color: "#C94859"; border.color: "white"; border.width: 2
                    }
                    onPressedChanged: root.scrubbing = pressed
                    onMoved: player.position = Math.round(value)
                }
                Text { x: 20; y: 36; text: root.timeText(player.position); color: "#69766D"; font.family: "Segoe UI"; font.pixelSize: 12 }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: 20; y: 36
                    text: root.timeText(player.duration || study.durationMs)
                    color: "#69766D"; font.family: "Segoe UI"; font.pixelSize: 12
                }
                Row {
                    x: 18; y: 70; spacing: 7
                    ActionButton { label: "上一句"; enabled: study.activeIndex > 0; onClicked: study.chooseSentence(study.activeIndex - 1) }
                    ActionButton {
                        width: 80; label: player.playbackState === MediaPlayer.PlayingState ? "暂停" : "播放"
                        primary: true; enabled: study.hasMedia
                        onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
                    }
                    ActionButton { label: "下一句"; enabled: study.activeIndex + 1 < study.sentenceCount; onClicked: study.chooseSentence(study.activeIndex + 1) }
                    ActionButton { label: "循环本句"; selected: study.loopSentence; enabled: study.sentenceCount > 0; onClicked: study.toggleLoop() }
                    ActionButton { label: root.textHidden ? "显示原文" : "隐藏原文"; enabled: study.sentenceCount > 0; onClicked: root.textHidden = !root.textHidden }
                    ActionButton { label: root.rates[root.rateIndex].toFixed(2).replace(/0$/, "") + "×"; onClicked: { root.rateIndex = (root.rateIndex + 1) % root.rates.length; player.playbackRate = root.rates[root.rateIndex] } }
                    ActionButton {
                        label: "校对本句"; enabled: study.sentenceCount > 0
                        onClicked: {
                            originalEdit.text = study.currentSentence.text
                            translationEdit.text = study.currentSentence.translation || study.currentSentence.analysis.translation || ""
                            startEdit.text = String(study.currentSentence.start)
                            endEdit.text = String(study.currentSentence.end)
                            editPopup.open()
                        }
                    }
                }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 20; y: 76; spacing: 5
                    Text { text: "音量"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Slider { id: volumeSlider; width: 94; height: 24; from: 0; to: 1
                        value: sound.volume; onMoved: sound.volume = value
                        background: Rectangle { x: volumeSlider.leftPadding
                            y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                            width: volumeSlider.availableWidth; height: 4; radius: 2; color: "#E2E8E3"
                            Rectangle { width: volumeSlider.visualPosition * parent.width; height: parent.height
                                radius: 2; color: "#C94859" } }
                        handle: Rectangle { x: volumeSlider.leftPadding + volumeSlider.visualPosition * (volumeSlider.availableWidth - width)
                            y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                            width: 14; height: 14; radius: 7; color: "#C94859"; border.color: "#FFFFFF"; border.width: 2 }
                    }
                    Text { anchors.verticalCenter: parent.verticalCenter; width: 28
                        text: Math.round(sound.volume * 100) + "%"; color: "#69766D"; font.pixelSize: 11 }
                }
            }

            Rectangle {
                id: readingPane
                x: 0; y: mediaFrame.height + 12
                width: parent.width; height: Math.max(0, transport.y - y - 12)
                visible: study.hasMedia
                radius: 10; color: "#FFFFFF"; border.color: "#DFE4E0"
                clip: true
                Text {
                    anchors.centerIn: parent
                    visible: study.sentenceCount === 0
                    text: "转写整段或导入字幕后，在这里逐句阅读。"
                    color: "#8B978E"; font.family: "Microsoft YaHei UI"; font.pixelSize: 15
                }
                ListView {
                    id: readingList
                    objectName: "readingList"
                    anchors.fill: parent; anchors.margins: 1
                    clip: true; model: study.segments
                    property int trackedIndex: -1
                    boundsBehavior: Flickable.StopAtBounds
                    spacing: 6
                    onCountChanged: Qt.callLater(scrollToActive)
                    Connections {
                        target: study
                        function onStateChanged() { Qt.callLater(readingList.scrollToActive) }
                        function onSegmentsChanged() {
                            readingList.trackedIndex = -1
                            Qt.callLater(readingList.scrollToActive)
                        }
                    }
                    function scrollToActive() {
                        if (count === 0 || study.activeIndex < 0) { trackedIndex = -1; return }
                        trackedIndex = study.activeIndex
                        forceLayout()
                        positionViewAtIndex(trackedIndex, ListView.Beginning)
                    }
                    delegate: Rectangle {
                        id: readingCard
                        required property int index
                        required property var modelData
                        property bool active: index === study.activeIndex
                        property bool hasNotes: modelData.analysis.grammar.length > 0 || modelData.analysis.vocabulary.length > 0
                        width: readingList.width - 16
                        height: Math.max(105, (active && hasNotes ? analysisFooter.y + 16
                                      : translationLabel.y + translationLabel.height + 19))
                        x: 8; radius: 10
                        color: active ? "#F2F2F0" : "#FFFFFF"
                        border.color: active ? "#E6E8E5" : "#F1F2F0"
                        Behavior on color { ColorAnimation { duration: 240 } }
                        Rectangle {
                            width: 3; height: parent.height - 18; y: 9; radius: 2
                            color: readingCard.active ? "#C94859" : "transparent"
                            Behavior on color { ColorAnimation { duration: 240 } }
                        }
                        Text {
                            x: 18; y: 13
                            text: root.timeText(readingCard.modelData.start * 1000)
                            color: readingCard.active ? "#B63D50" : "#96A098"
                            font.family: "Segoe UI"; font.pixelSize: 11
                        }
                        Text {
                            anchors.right: parent.right; anchors.rightMargin: readingCard.active ? 104 : 18; y: 13
                            text: (readingCard.index + 1) + " / " + study.sentenceCount
                            color: "#A0A9A2"; font.family: "Segoe UI"; font.pixelSize: 11
                        }
                         Item {
                             id: textBlock
                             x: 18; y: readingCard.active ? 49 : 27
                             width: parent.width - 36
                             height: root.textHidden || readingCard.modelData.tokens.length === 0
                                     ? plainText.contentHeight : tokenFlow.childrenRect.height
                            Flow {
                                id: tokenFlow
                                width: parent.width; spacing: 2
                                visible: !root.textHidden && readingCard.modelData.tokens.length > 0
                                Repeater {
                                    model: readingCard.modelData.tokens
                                    delegate: Rectangle {
                                        property bool spoken: readingCard.active && modelData.start !== undefined
                                            && player.position / 1000 >= modelData.start
                                            && player.position / 1000 < modelData.end
                                        width: Math.max(wordText.implicitWidth, rubyText.implicitWidth) + 7
                                        height: 43; radius: 4
                                        color: spoken ? "#FBE0E5" : "transparent"
                                        Text {
                                            id: rubyText; anchors.horizontalCenter: parent.horizontalCenter; y: 0
                                            text: modelData.reading; color: "#68736C"
                                            font.family: "Yu Gothic UI"; font.pixelSize: 11
                                        }
                                        Text {
                                            id: wordText; anchors.horizontalCenter: parent.horizontalCenter; y: 13
                                            text: modelData.text
                                            color: parent.spoken ? "#B9384B" : "#202C25"
                                            font.family: "Yu Gothic UI"; font.pixelSize: 24; font.weight: Font.DemiBold
                                        }
                                        Rectangle {
                                            anchors.bottom: parent.bottom; width: parent.width - 2; height: 4; radius: 2
                                            color: root.categoryColor(modelData.category)
                                        }
                                    }
                                }
                            }
                             Text {
                                 id: plainText
                                width: parent.width
                                visible: readingCard.modelData.tokens.length === 0 || root.textHidden
                                text: root.textHidden ? "原文已隐藏" : readingCard.modelData.text
                                 wrapMode: Text.Wrap
                                color: root.textHidden ? "#89948D" : "#202C25"
                                font.family: "Yu Gothic UI"; font.pixelSize: 24; font.weight: Font.DemiBold
                            }
                        }
                         Text {
                             id: translationLabel
                             x: 18; y: textBlock.y + textBlock.height + 9
                             width: parent.width - 36; height: contentHeight
                            text: readingCard.modelData.translation || (readingCard.modelData.analysis.translation
                                  ? "机译 · " + readingCard.modelData.analysis.translation
                                  : (readingCard.active ? "未添加中文释义" : ""))
                             wrapMode: Text.Wrap
                            color: readingCard.modelData.translation || readingCard.modelData.analysis.translation ? "#536056" : "#A0AAA1"
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 14
                        }
                         Text {
                             id: grammarLabel
                             x: 18; y: translationLabel.y + translationLabel.height + 9
                             width: parent.width - 36; height: visible ? contentHeight : 0
                            visible: readingCard.active && readingCard.hasNotes
                            text: readingCard.modelData.analysis.grammar || "本句没有单独标出的句型。"
                             color: "#435148"; wrapMode: Text.Wrap
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 13
                        }
                         Text {
                             id: vocabularyLabel
                             x: 18; y: grammarLabel.y + grammarLabel.height + 7; width: parent.width - 36
                             height: visible ? contentHeight : 0
                            visible: readingCard.active && readingCard.hasNotes
                            text: readingCard.modelData.analysis.vocabulary.map(function(item) {
                                return item.surface + "：" + item.meaning
                            }).join("   ·   ")
                             color: "#69766D"; wrapMode: Text.Wrap
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                        }
                         Text {
                             id: analysisFooter
                            anchors.right: parent.right; anchors.rightMargin: 18
                             y: vocabularyLabel.y + vocabularyLabel.height + 7
                            visible: readingCard.active && readingCard.hasNotes
                            text: readingCard.modelData.analysis.model === "manual" ? "已手动校对" : "本地模型生成 · 待校对"
                            color: "#9AA49D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 10
                        }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: study.chooseSentence(readingCard.index)
                        }
                        Row {
                            z: 1; anchors.right: parent.right; anchors.rightMargin: 12; y: 7
                            spacing: 5; visible: readingCard.active && !study.enriching
                            ActionButton {
                                visible: readingCard.hasNotes
                                label: "校对解析"; enabled: !study.busy
                                onClicked: {
                                    analysisGrammarEdit.text = readingCard.modelData.analysis.grammar
                                    analysisVocabularyEdit.text = readingCard.modelData.analysis.vocabulary.map(function(item) {
                                        return item.surface + "：" + item.meaning
                                    }).join("\n")
                                    analysisPopup.open()
                                }
                            }
                            ActionButton {
                                label: "翻译本句"; enabled: !study.busy
                                onClicked: study.startTranslation(false)
                            }
                            ActionButton {
                                label: study.contentLanguage === "en" ? "解释本句" : "解析本句"; enabled: !study.busy
                                onClicked: study.startEnrichment(false)
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: transcriptPane
            visible: root.page === "listen" && root.showList && study.hasMedia
            anchors.top: parent.top; anchors.right: parent.right; anchors.bottom: parent.bottom
            width: 296; radius: 10; color: "#FFFFFF"; border.color: "#DFE4E0"
            Text {
                x: 18; y: 17; text: "字幕"; color: "#27372C"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 15; font.weight: Font.DemiBold
            }
            Text {
                anchors.right: parent.right; anchors.rightMargin: 18; y: 20
                text: study.sentenceCount + " 句"; color: "#8A968D"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 11
            }
            Rectangle { x: 0; y: 53; width: parent.width; height: 1; color: "#EEF0EE" }
            Text {
                x: 20; y: 80; width: parent.width - 40; visible: study.sentenceCount === 0
                text: study.hasMedia ? "转写整段或导入已有字幕。" : "打开文件后显示字幕。"
                color: "#8A968D"; wrapMode: Text.Wrap
                font.family: "Microsoft YaHei UI"; font.pixelSize: 13
            }
            ListView {
                id: sentenceList
                x: 1; y: 54; width: parent.width - 2; height: parent.height - 55
                clip: true; model: study.segments
                currentIndex: study.activeIndex
                onCurrentIndexChanged: if (count > 0) positionViewAtIndex(currentIndex, ListView.Contain)
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    width: sentenceList.width; height: 75
                    color: index === study.activeIndex ? "#FBECEF" : itemHover.containsMouse ? "#F7F8F7" : "#FFFFFF"
                    Rectangle { width: 3; height: parent.height; color: index === study.activeIndex ? "#C94859" : "transparent" }
                    Text {
                        x: 16; y: 11; text: root.timeText(modelData.start * 1000)
                        color: index === study.activeIndex ? "#B53D50" : "#8A968D"
                        font.family: "Segoe UI"; font.pixelSize: 11
                    }
                    Text {
                        x: 16; y: 31; width: parent.width - 32; height: 34
                        text: modelData.text; elide: Text.ElideRight; wrapMode: Text.NoWrap
                        color: "#26332A"; font.family: "Yu Gothic UI"; font.pixelSize: 14
                    }
                    Rectangle { anchors.bottom: parent.bottom; x: 15; width: parent.width - 30; height: 1; color: "#F0F2F0" }
                    MouseArea {
                        id: itemHover; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: study.chooseSentence(index)
                    }
                }
            }
        }
    }

    Popup {
        id: editPopup
        width: 610; height: 445
        x: Math.round((root.width - width) / 2); y: Math.round((root.height - height) / 2)
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        background: Rectangle { color: "#FFFFFF"; radius: 12; border.color: "#DDE2DE" }
        contentItem: ColumnLayout {
            spacing: 9
            Text { text: "校对当前句"; color: "#27372C"; font.family: "Microsoft YaHei UI"; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { text: "日文原文"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
            TextArea {
                id: originalEdit; Layout.fillWidth: true; Layout.preferredHeight: 91
                wrapMode: TextEdit.Wrap; font.family: "Yu Gothic UI"; font.pixelSize: 18
                background: Rectangle { radius: 7; color: "#F7F8F7"; border.color: "#DDE2DE" }
            }
            Text { text: "中文释义"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
            TextArea {
                id: translationEdit; Layout.fillWidth: true; Layout.preferredHeight: 69
                wrapMode: TextEdit.Wrap; font.family: "Microsoft YaHei UI"; font.pixelSize: 15
                background: Rectangle { radius: 7; color: "#F7F8F7"; border.color: "#DDE2DE" }
            }
            RowLayout {
                Text { text: "起点（秒）"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
                TextField { id: startEdit; Layout.preferredWidth: 130; validator: DoubleValidator { bottom: 0 } }
                Item { Layout.preferredWidth: 25 }
                Text { text: "终点（秒）"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
                TextField { id: endEdit; Layout.preferredWidth: 130; validator: DoubleValidator { bottom: 0 } }
            }
            Text { text: study.status.startsWith("无法保存") ? study.status : "修改原文或时间后，会清除旧的逐词对齐。"; color: study.status.startsWith("无法保存") ? "#B53D50" : "#8A968D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 11 }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.alignment: Qt.AlignRight; spacing: 8
                ActionButton { label: "取消"; onClicked: editPopup.close() }
                ActionButton {
                    label: "保存"; primary: true
                    onClicked: if (study.saveSentence(originalEdit.text, translationEdit.text, startEdit.text, endEdit.text)) editPopup.close()
                }
            }
        }
    }

    Popup {
        id: analysisPopup
        width: 610; height: 400
        x: Math.round((root.width - width) / 2); y: Math.round((root.height - height) / 2)
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        background: Rectangle { color: "#FFFFFF"; radius: 12; border.color: "#DDE2DE" }
        contentItem: ColumnLayout {
            spacing: 9
            Text { text: "校对本句解析"; color: "#27372C"; font.family: "Microsoft YaHei UI"; font.pixelSize: 18; font.weight: Font.DemiBold }
            Text { text: "句型 / 用法"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
            TextArea {
                id: analysisGrammarEdit; Layout.fillWidth: true; Layout.preferredHeight: 90
                wrapMode: TextEdit.Wrap; font.family: "Microsoft YaHei UI"; font.pixelSize: 15
                background: Rectangle { radius: 7; color: "#F7F8F7"; border.color: "#DDE2DE" }
            }
            Text { text: "值得记的词（每行：原文词：中文意思）"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
            TextArea {
                id: analysisVocabularyEdit; Layout.fillWidth: true; Layout.preferredHeight: 120
                wrapMode: TextEdit.Wrap; font.family: "Microsoft YaHei UI"; font.pixelSize: 15
                background: Rectangle { radius: 7; color: "#F7F8F7"; border.color: "#DDE2DE" }
            }
            Text {
                text: study.status.startsWith("词汇") ? study.status : "模型结果可修改；清空两栏并保存可删除本句解析。"
                color: study.status.startsWith("词汇") ? "#B53D50" : "#8A968D"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 11
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.alignment: Qt.AlignRight; spacing: 8
                ActionButton { label: "取消"; onClicked: analysisPopup.close() }
                ActionButton {
                    label: "保存"; primary: true
                    onClicked: if (study.saveAnalysis(analysisGrammarEdit.text, analysisVocabularyEdit.text)) analysisPopup.close()
                }
            }
        }
    }

    Shortcut { sequence: "Space"; enabled: !editPopup.visible && !analysisPopup.visible && study.hasMedia; onActivated: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play() }
    Shortcut { sequence: "Ctrl+Left"; enabled: !editPopup.visible && !analysisPopup.visible; onActivated: study.chooseSentence(study.activeIndex - 1) }
    Shortcut { sequence: "Ctrl+Right"; enabled: !editPopup.visible && !analysisPopup.visible; onActivated: study.chooseSentence(study.activeIndex + 1) }
}
