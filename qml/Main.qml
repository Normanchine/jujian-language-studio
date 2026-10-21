import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia
import QtQuick.Effects

ApplicationWindow {
    id: root
    property string appVersion: "0.2.0"
    property var readingPreviewItems: []
    property var readingHomeState: reading.homeState
    width: 1180
    height: 820
    minimumWidth: 900
    minimumHeight: 640
    visible: true
    opacity: uiAnimationsEnabled ? 0 : 1
    flags: Qt.Window | Qt.FramelessWindowHint
    title: study.hasMedia ? "句间 — " + study.title : "句间"
    color: "transparent"
    background: Rectangle {
        color: root.pageColor; radius: root.maximized ? 0 : 16
        antialiasing: true
    }
    contentItem.layer.enabled: !root.maximized
    contentItem.transformOrigin: Item.Center
    contentItem.scale: uiAnimationsEnabled ? 0.965 : 1
    Component.onCompleted: if (uiAnimationsEnabled) startupAnimation.start()
    ParallelAnimation {
        id: startupAnimation
        NumberAnimation { target: root; property: "opacity"; from: 0; to: 1
            duration: 190; easing.type: Easing.OutCubic }
        NumberAnimation { target: root.contentItem; property: "scale"; from: 0.965; to: 1
            duration: 210; easing.type: Easing.OutCubic }
    }
    contentItem.layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: cornerMask
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }
    Rectangle {
        id: cornerMask
        width: root.width; height: root.height
        radius: root.maximized ? 0 : 16
        antialiasing: true
        color: "white"; visible: false
        layer.enabled: true
        layer.smooth: true
        layer.samples: 4
    }

    property string themeKey: settings.values.theme || "sage"
    property color sidebarColor: settings.palette.side
    property color pageColor: settings.palette.page
    property color surfaceColor: settings.palette.surface
    property color accentColor: themeKey === "classic" ? "#4E8068" : settings.palette.accent
    property color selectionColor: settings.palette.selection

    property real videoHeight: settings.values.listening_video_height || 360
    property int highlightDelayMs: settings.values.highlight_delay_ms === undefined ? 200 : settings.values.highlight_delay_ms
    // An explicit sentence jump must not highlight the preceding sentence while
    // the calibrated playback delay catches up to the new start position.
    property real highlightSeekFloor: -1
    property real highlightSeconds: {
        var seconds = Math.max(0, player.position - highlightDelayMs,
                               highlightSeekFloor * 1000) / 1000
        if (study.loopSentence && study.sentenceCount > 0) {
            var current = study.currentSentence
            seconds = Math.min(seconds, Math.max(current.start, current.end - 0.001))
        }
        return seconds
    }
    property int highlightedSentenceIndex: {
        var segments = study.segments
        var selected = 0
        for (var i = 0; i < segments.length; i++) {
            if (segments[i].start > highlightSeconds) break
            selected = i
        }
        return selected
    }
    onHighlightedSentenceIndexChanged: if (readingList.followPlayback) Qt.callLater(readingList.scrollToActive)
    property bool listeningKeysEnabled: page === "listen" && study.hasMedia
        && !editPopup.visible && !analysisPopup.visible
        && !(activeFocusItem instanceof TextInput) && !(activeFocusItem instanceof TextEdit)
    property bool textHidden: false
    property bool scrubbing: false
    onScrubbingChanged: if (scrubbing) highlightSeekFloor = -1
    property string page: "home"
    onPageChanged: {
        if (page !== "reading") readingView.leavePractice()
    }
    property bool sidebarCollapsed: false
    property int pendingResumeMs: 0
    property bool playbackReady: false
    property string playbackUrl: ""
    function saveCurrentPlayback() {
        if (playbackReady && study.hasMedia && playbackUrl === study.mediaUrl
                && player.source.toString() === playbackUrl)
            study.savePlayback(player.position)
    }
    function restorePlayback() {
        if (!study.hasMedia || player.source.toString() !== playbackUrl) return
        if (player.mediaStatus !== MediaPlayer.LoadedMedia
                && player.mediaStatus !== MediaPlayer.BufferedMedia) return
        if (!playbackReady) {
            player.position = pendingResumeMs
            pendingResumeMs = 0
            playbackReady = true
            study.updatePlayback(player.position)
        }
    }
    property bool maximized: visibility === Window.Maximized
    onClosing: {
        root.saveCurrentPlayback()
        writingView.saveNow()
        writer.pauseTask()
        readingView.leavePractice()
    }
    property var rates: [0.75, 1.0, 1.25, 1.5]
    property int rateIndex: 1

    function timeText(ms) {
        var secs = Math.max(0, Math.floor(ms / 1000))
        return Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0")
    }
    function changeRate() {
        rateIndex = (rateIndex + 1) % rates.length
        player.playbackRate = rates[rateIndex]
    }
    function replayCurrentSentence() {
        if (study.sentenceCount > 0) study.chooseSentence(study.activeIndex)
    }
    function editCurrentSentence() {
        originalEdit.text = study.currentSentence.text
        translationEdit.text = study.currentSentence.translation || study.currentSentence.analysis.translation || ""
        startEdit.text = String(study.currentSentence.start)
        endEdit.text = String(study.currentSentence.end)
        editPopup.open()
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
             : primary ? (pointer.containsMouse ? Qt.darker(root.accentColor, 1.12) : root.accentColor)
             : selected ? (pointer.containsMouse ? Qt.darker(root.selectionColor, 1.06) : root.selectionColor)
             : pointer.containsMouse ? "#E9ECEA" : "#FFFFFF"
        border.color: !enabled ? "#E6E8E6" : primary ? root.accentColor : selected ? root.accentColor : "#DDE2DF"
        border.width: 1
        Text {
            id: caption
            anchors.centerIn: parent
            text: control.label
            color: !control.enabled ? "#9DA49F" : control.primary ? "#FFFFFF" : control.selected ? root.accentColor : "#26332D"
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
        property color accent: root.accentColor
        property color tint: root.selectionColor
        signal clicked()
        height: 48
        radius: 10
        color: selected ? tint : navHover.containsMouse ? Qt.lighter(root.sidebarColor, 1.07) : "transparent"
        Rectangle { x: 0; y: 10; width: 3; height: 28; radius: 2
            color: nav.selected ? nav.accent : "transparent" }
        Row {
            anchors.left: parent.left; anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter; spacing: 16
            NavGlyph { width: 22; height: 22; kind: nav.iconName
                active: nav.selected; activeColor: nav.accent }
            Text { visible: !root.sidebarCollapsed; text: nav.label
                color: nav.selected ? "#2A3B31" : "#536158"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 14
                font.weight: nav.selected ? Font.DemiBold : Font.Normal
                anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: navHover; anchors.fill: parent; hoverEnabled: true; enabled: nav.enabled
            cursorShape: Qt.PointingHandCursor; onClicked: nav.clicked() }
    }

    component WindowButton: Rectangle {
        id: windowButton
        property string kind: ""
        property string hint: ""
        property bool destructive: false
        signal clicked()
        width: 34; height: 32; radius: 8
        color: buttonMouse.pressed ? (destructive ? "#F3D9DE" : Qt.darker(root.selectionColor, 1.06))
             : buttonMouse.containsMouse ? (destructive ? "#FBEDEF" : root.selectionColor) : "transparent"
        property color glyphColor: destructive && buttonMouse.containsMouse ? "#B83E50" : "#536158"
        Rectangle { visible: kind === "minimize"; width: 11; height: 1
            anchors.centerIn: parent; color: windowButton.glyphColor }
        Rectangle { visible: kind === "maximize"
            width: 11; height: 10; anchors.centerIn: parent; color: "transparent"
            border.width: 1; border.color: windowButton.glyphColor }
        Rectangle { visible: kind === "restore"; x: 15; y: 8; width: 10; height: 9
            color: "transparent"; border.width: 1; border.color: windowButton.glyphColor }
        Rectangle { visible: kind === "restore"; x: 11; y: 12; width: 10; height: 9
            color: windowButton.color; border.width: 1; border.color: windowButton.glyphColor }
        Rectangle { visible: kind === "close"; anchors.centerIn: parent; width: 14; height: 1
            rotation: 45; color: windowButton.glyphColor }
        Rectangle { visible: kind === "close"; anchors.centerIn: parent; width: 14; height: 1
            rotation: -45; color: windowButton.glyphColor }
        MouseArea {
            id: buttonMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: windowButton.clicked()
        }
        ToolTip.visible: buttonMouse.containsMouse
        ToolTip.delay: 650
        ToolTip.text: hint
    }

    MediaPlayer {
        id: player
        objectName: "mediaPlayer"
        audioOutput: AudioOutput { id: sound; volume: 0.85 }
        videoOutput: videoView
        onMediaStatusChanged: {
            if (root.playbackReady && root.playbackUrl === study.mediaUrl
                    && mediaStatus === MediaPlayer.EndOfMedia) study.finishPlayback()
            root.restorePlayback()
        }
        onPlaybackStateChanged: {
            if (playbackState !== MediaPlayer.PlayingState) root.saveCurrentPlayback()
        }
        onPositionChanged: {
            if (!root.playbackReady) return
            if (root.highlightSeekFloor >= 0
                    && position - root.highlightDelayMs >= root.highlightSeekFloor * 1000)
                root.highlightSeekFloor = -1
            if (!root.scrubbing && study.loopSentence && study.sentenceCount > 0
                    && playbackState === MediaPlayer.PlayingState) {
                var current = study.currentSentence
                var end = Math.round(current.end * 1000)
                if (position >= end && position < end + 400) {
                    root.highlightSeekFloor = current.start
                    player.position = Math.round(current.start * 1000)
                    return
                }
            }
            study.updatePlayback(position)
        }
    }
    Connections {
        target: study
        function onMediaChanged() {
            // Stop/source replacement can synchronously emit position/state changes.
            // Disable saving first, and capture the new resume point before either.
            root.playbackReady = false
            root.pendingResumeMs = study.resumeMs
            root.playbackUrl = ""
            root.highlightSeekFloor = -1
            player.stop()
            player.source = ""
            root.playbackUrl = study.mediaUrl
            player.source = root.playbackUrl
            root.restorePlayback()
            if (study.hasMedia) root.page = "listen"
            else { player.stop(); root.page = "library" }
        }
        function onSeekRequested(ms) {
            root.highlightSeekFloor = study.currentSentence.start
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
        onTriggered: root.saveCurrentPlayback() }

    FileDialog {
        id: mediaPicker
        title: "打开本地音频或视频"
        nameFilters: ["媒体文件 (*.mp3 *.m4a *.m4s *.mp4 *.wav *.flac *.mov *.mkv *.webm)", "所有文件 (*)"]
        onAccepted: {
            root.saveCurrentPlayback()
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
        width: root.sidebarCollapsed ? 64 : 216; color: root.sidebarColor
        Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: Qt.darker(root.sidebarColor, 1.08) }
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
        MouseArea {
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            height: 64
            onPressed: root.startSystemMove()
            onDoubleClicked: root.maximized ? root.showNormal() : root.showMaximized()
        }
        Column {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 8; anchors.rightMargin: 8; y: 89; spacing: 4
            NavButton { width: parent.width; label: "首页"; iconName: "home"; selected: root.page === "home"
                onClicked: { player.pause(); root.saveCurrentPlayback(); study.refreshProjects(); root.page = "home" } }
            NavButton { width: parent.width; label: "精听"; iconName: "listen"; selected: root.page === "listen"
                onClicked: { if (!study.hasMedia) study.refreshProjects(); root.page = study.hasMedia ? "listen" : "library" } }
            NavButton { width: parent.width; label: "写作"; iconName: "writing"; selected: root.page === "writing"
                onClicked: { writingView.showLibrary(); root.page = "writing" } }
            NavButton { width: parent.width; label: "阅读"; iconName: "reading"; selected: root.page === "reading"
                onClicked: { player.pause(); readingView.showHome(); root.page = "reading" } }
            NavButton { width: parent.width; label: "资料库"; iconName: "library"; selected: root.page === "library"
                onClicked: { study.refreshProjects(); root.page = "library" } }
            NavButton { width: parent.width; label: "设置"; iconName: "settings"; selected: root.page === "settings"
                onClicked: root.page = "settings" }
        }
        Rectangle { x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
            width: parent.width - 16; height: 40; radius: 8
            color: collapseHover.containsMouse ? root.selectionColor : "transparent"
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
        height: 62; color: root.surfaceColor
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Qt.darker(root.pageColor, 1.06) }
        MouseArea {
            anchors.fill: parent
            onPressed: root.startSystemMove()
            onDoubleClicked: root.maximized ? root.showNormal() : root.showMaximized()
        }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 132; spacing: 7
            Text { Layout.fillWidth: true; Layout.minimumWidth: 70
                text: root.page === "listen" ? study.title : ({home:"首页", writing:"写作", reading:"阅读", library:"资料库", settings:"设置"}[root.page] || "首页")
                elide: Text.ElideMiddle; color: "#27362D"
                font.family: "Microsoft YaHei UI"; font.pixelSize: 15; font.weight: Font.DemiBold
                MouseArea {
                    anchors.fill: parent
                    onPressed: root.startSystemMove()
                    onDoubleClicked: root.maximized ? root.showNormal() : root.showMaximized()
                }
            }
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
                background: Rectangle { radius: 8; color: languageChoice.pressed ? root.selectionColor : "#FFFFFF"
                    border.color: languageChoice.activeFocus ? root.accentColor : "#DDE2DF" }
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
            ActionButton { visible: root.page === "listen"; label: study.busy && !study.splitting ? "正在转写…" : "转写整段"
                enabled: study.hasMedia && !study.busy && !study.enriching; onClicked: study.transcribe() }
            ActionButton { visible: root.page === "listen" && root.width >= 1160; label: "导入字幕"
                enabled: study.hasMedia && !study.busy && !study.enriching; onClicked: transcriptPicker.open() }
            ActionButton { visible: root.page === "listen" && root.width >= 1160; label: "中文翻译"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onClicked: study.startTranslation(true) }
            ActionButton { visible: root.page === "listen" && root.width >= 1160
                label: study.contentLanguage === "en" ? "句子解释" : "语法解析"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onClicked: study.startEnrichment(true) }
            ActionButton { visible: root.page === "listen" && root.width < 1160; label: "更多"
                onClicked: moreMenu.open() }
            ActionButton { visible: study.enriching && root.page === "listen"; label: "停止处理"
                onClicked: study.stopEnrichment() }
            ActionButton { visible: root.page === "listen" && root.width >= 1160; label: study.splitting ? "整理中…" : "整理字幕"
                enabled: (study.contentLanguage === "en" || study.contentLanguage === "ja") && study.sentenceCount > 0 && !study.busy && !study.enriching
                onClicked: study.organizeSubtitles() }
            ActionButton { visible: root.page === "listen"; label: "打开文件"
                enabled: !study.busy && !study.enriching
                onClicked: mediaPicker.open() }
        }
        Menu { id: moreMenu; x: toolbar.width - width - 18; y: toolbar.height - 2
            MenuItem { text: "整理字幕"; enabled: (study.contentLanguage === "en" || study.contentLanguage === "ja") && study.sentenceCount > 0 && !study.busy && !study.enriching; onTriggered: study.organizeSubtitles() }
            MenuItem { text: "导入字幕"; enabled: study.hasMedia && !study.busy && !study.enriching; onTriggered: transcriptPicker.open() }
            MenuItem { text: "中文翻译"; enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onTriggered: study.startTranslation(true) }
            MenuItem { text: study.contentLanguage === "en" ? "句子解释" : "语法解析"
                enabled: study.sentenceCount > 0 && !study.busy && !study.enriching; onTriggered: study.startEnrichment(true) }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            WindowButton { objectName: "minimizeButton"; kind: "minimize"; hint: "最小化"; onClicked: root.showMinimized() }
            WindowButton { objectName: "maximizeButton"; kind: root.maximized ? "restore" : "maximize"
                hint: root.maximized ? "还原" : "最大化"
                onClicked: root.maximized ? root.showNormal() : root.showMaximized() }
            WindowButton { objectName: "closeButton"; kind: "close"; hint: "关闭"; destructive: true; onClicked: root.close() }
        }
    }

    // Frameless windows need explicit resize handles around their outer edge.
    Item {
        anchors.fill: parent; z: 100
        visible: !root.maximized
        MouseArea { anchors.left: parent.left; anchors.top: parent.top; width: 7; height: 7
            cursorShape: Qt.SizeFDiagCursor; onPressed: root.startSystemResize(Qt.TopEdge | Qt.LeftEdge) }
        MouseArea { anchors.right: parent.right; anchors.top: parent.top; width: 7; height: 7
            cursorShape: Qt.SizeBDiagCursor; onPressed: root.startSystemResize(Qt.TopEdge | Qt.RightEdge) }
        MouseArea { anchors.left: parent.left; anchors.bottom: parent.bottom; width: 7; height: 7
            cursorShape: Qt.SizeBDiagCursor; onPressed: root.startSystemResize(Qt.BottomEdge | Qt.LeftEdge) }
        Item {
            id: bottomRightResize
            objectName: "bottomRightResize"
            anchors.right: parent.right; anchors.bottom: parent.bottom
            width: 24; height: 24; z: 1
            Rectangle { x: 7; y: 15; width: 13; height: 1; rotation: -45
                color: gripMouse.containsMouse ? "#718077" : "#AAB5AD" }
            Rectangle { x: 13; y: 17; width: 7; height: 1; rotation: -45
                color: gripMouse.containsMouse ? "#718077" : "#AAB5AD" }
            MouseArea {
                id: gripMouse; objectName: "bottomRightGripMouse"
                anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.SizeFDiagCursor
                onPressed: root.startSystemResize(Qt.BottomEdge | Qt.RightEdge)
            }
        }
        MouseArea { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.topMargin: 7; anchors.bottomMargin: 7; width: 5
            cursorShape: Qt.SizeHorCursor; onPressed: root.startSystemResize(Qt.LeftEdge) }
        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.topMargin: 7; anchors.bottomMargin: 7; width: 5
            cursorShape: Qt.SizeHorCursor; onPressed: root.startSystemResize(Qt.RightEdge) }
        MouseArea { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            anchors.leftMargin: 7; anchors.rightMargin: 7; height: 5
            cursorShape: Qt.SizeVerCursor; onPressed: root.startSystemResize(Qt.TopEdge) }
        MouseArea { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            anchors.leftMargin: 7; anchors.rightMargin: 7; height: 5
            cursorShape: Qt.SizeVerCursor; onPressed: root.startSystemResize(Qt.BottomEdge) }
    }

    Rectangle {
        id: statusBar
        anchors.left: sidebar.right; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 27; color: "transparent"
        Text {
            x: 16; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 48
            text: root.page === "reading" ? ""
                  : player.errorString && root.page === "listen" ? "播放错误：" + player.errorString
                  : root.page === "listen" && study.currentSentence.suggestion ? study.currentSentence.suggestion
                  : root.page === "writing" ? writer.status
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
        property real studyWidth: Math.min(width, 1100)

        HomeView {
            anchors.fill: parent; visible: root.page === "home"
            themeAccent: root.accentColor
            onOpenLocal: mediaPicker.open()
            onNewDraft: { writer.newDraft("ja"); writingView.libraryMode = false; root.page = "writing" }
            onOpenProject: { root.saveCurrentPlayback(); study.openProject(path) }
            onOpenDraft: { writer.openDraft(path); writingView.libraryMode = false; root.page = "writing" }
            onOpenLibrary: { study.refreshProjects(); root.page = "library" }
            onOpenWriting: { writer.refresh(); writingView.showLibrary(); root.page = "writing" }
        }
        LibraryView { anchors.fill: parent; visible: root.page === "library"
            themeAccent: root.accentColor
            onOpenProject: { root.saveCurrentPlayback(); study.openProject(path) } }
        WritingView { id: writingView; anchors.fill: parent; visible: root.page === "writing"
            themeAccent: root.accentColor }
        ReadingHome { id: readingView; anchors.fill: parent; visible: root.page === "reading"
            materials: root.readingPreviewItems.length ? root.readingPreviewItems.filter(function(a) {
                return a.sourceKind !== "personal_import" && a.sourceKind !== "user_paste";
            }).concat(reading.importedCatalogue) : reading.catalogue; savedState: root.readingHomeState
            onStateEdited: function(state) { root.readingHomeState = state; reading.saveHomeState(state) } }
        SettingsView { anchors.fill: parent; visible: root.page === "settings"
            appVersion: root.appVersion }

        Item {
            id: leftPane
            visible: root.page === "listen"
            x: (workspace.width - workspace.studyWidth) / 2
            anchors.top: parent.top; anchors.bottom: parent.bottom
            width: workspace.studyWidth

            Rectangle {
                id: mediaFrame
                objectName: "mediaFrame"
                x: (parent.width - width) / 2; y: 0
                width: study.hasVideo ? Math.min(parent.width, height * (videoView.sourceRect.height > 0 ? videoView.sourceRect.width / videoView.sourceRect.height : 16 / 9)) : parent.width
                height: !study.hasMedia ? leftPane.height : study.hasVideo
                    ? Math.max(96, Math.min(root.videoHeight, leftPane.height - 240)) : 96
                radius: 10
                color: study.hasVideo ? "#1D2320" : study.hasMedia
                    ? Qt.tint(root.surfaceColor, Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.08))
                    : root.pageColor
                border.color: study.hasMedia && !study.hasVideo
                    ? Qt.tint(root.surfaceColor, Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.18))
                    : "transparent"
                clip: true
                layer.enabled: study.hasVideo
                layer.effect: MultiEffect {
                    maskEnabled: true; maskSource: videoMask
                    maskThresholdMin: 0.5; maskSpreadAtMin: 1.0
                }
                Rectangle {
                    id: videoMask
                    width: mediaFrame.width; height: mediaFrame.height
                    radius: 10; antialiasing: true; color: "white"; visible: false
                    layer.enabled: true; layer.samples: 4; layer.smooth: true
                }
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
                        text: "♫"; color: root.accentColor; font.pixelSize: 32
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
                x: 0; y: parent.height - height; width: parent.width; height: 78
                visible: study.hasMedia
                radius: 12; color: "#FFFFFF"; border.color: "#DFE4E0"
                Slider {
                    id: progress
                    x: 16; y: 4; width: parent.width - 32; height: 22
                    from: 0; to: Math.max(1, player.duration); value: player.position
                    onPressedChanged: root.scrubbing = pressed
                    onMoved: player.position = Math.round(value)
                    background: Rectangle {
                        x: progress.leftPadding; y: progress.height / 2 - 2
                        width: progress.availableWidth; height: 4; radius: 2; color: "#E1E6E2"
                        Rectangle { width: parent.width * progress.visualPosition; height: 4; radius: 2; color: root.accentColor }
                    }
                    handle: Rectangle {
                        x: progress.leftPadding + progress.visualPosition * (progress.availableWidth - width)
                        y: progress.height / 2 - 6; width: 12; height: 12; radius: 6; color: root.accentColor
                    }
                }
                Text { x: 16; y: 27; text: root.timeText(player.position); color: "#748178"; font.pixelSize: 11 }
                Text { anchors.right: parent.right; anchors.rightMargin: 16; y: 27
                    text: root.timeText(player.duration); color: "#748178"; font.pixelSize: 11 }
                Row {
                    x: 16; y: 42; spacing: 8
                    ActionButton { label: "上一句"; height: 28; implicitHeight: 28
                        enabled: study.activeIndex > 0; onClicked: study.navigateSentence(-1) }
                    ActionButton { label: player.playbackState === MediaPlayer.PlayingState ? "暂停" : "播放"
                        height: 28; implicitHeight: 28; primary: true
                        onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play() }
                    ActionButton { label: "下一句"; height: 28; implicitHeight: 28
                        enabled: study.activeIndex + 1 < study.sentenceCount; onClicked: study.navigateSentence(1) }
                    ActionButton { label: "重播本句"; height: 28; implicitHeight: 28
                        enabled: study.sentenceCount > 0; onClicked: root.replayCurrentSentence() }
                    ActionButton { label: "循环本句"; height: 28; implicitHeight: 28; selected: study.loopSentence; onClicked: study.toggleLoop() }
                    ActionButton { visible: transport.width >= 790; label: root.textHidden ? "显示原文" : "隐藏原文"; height: 28; implicitHeight: 28; onClicked: root.textHidden = !root.textHidden }
                    ActionButton { label: root.rates[root.rateIndex] + "×"; height: 28; implicitHeight: 28; onClicked: root.changeRate() }
                    ActionButton { visible: transport.width >= 790; label: "校对本句"; height: 28; implicitHeight: 28; onClicked: root.editCurrentSentence() }
                }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 16; y: 42; spacing: 8
                    Text { visible: transport.width >= 790; text: "音量"; color: "#748178"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Slider { width: transport.width >= 790 ? 100 : 65; height: 28; value: sound.volume; onMoved: sound.volume = value }
                    Text { text: Math.round(sound.volume * 100) + "%"; color: "#748178"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                }
            }
            Item {
                objectName: "videoDivider"
                x: 0; y: mediaFrame.height; width: parent.width; height: 16
                Rectangle { anchors.centerIn: parent; width: 44; height: 4; radius: 2; color: "#BDC6BF" }
                MouseArea { anchors.fill: parent; cursorShape: Qt.SplitVCursor
                    onReleased: settings.savePlayerPreferences(root.highlightDelayMs, Math.round(root.videoHeight))
                    onPositionChanged: function(mouse) {
                        if (pressed) root.videoHeight = Math.max(120, Math.min(leftPane.height - 240, mapToItem(leftPane, mouse.x, mouse.y).y))
                    }
                }
            }

            Rectangle {
                id: readingPane
                objectName: "readingPane"
                x: 0; y: mediaFrame.height + 16
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
                RowLayout {
                    x: 16; y: 5; width: parent.width - 32; height: 30
                    Text { text: "字幕  ·  " + study.sentenceCount + " 句"; color: "#26342C"; font.pixelSize: 13; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    AppButton { text: readingList.followPlayback ? "跟随播放" : "回到当前句"; flat: readingList.followPlayback; implicitHeight: 26; onClicked: readingList.returnToCurrent() }
                    Text { visible: readingPane.width >= 790; text: "高亮延迟"; color: "#8C9790"; font.pixelSize: 11 }
                    AppCombo {
                        objectName: "highlightDelayChoice"
                        implicitWidth: 104; implicitHeight: 26
                        model: ["0 毫秒", "100 毫秒", "200 毫秒", "300 毫秒", "400 毫秒", "600 毫秒"]
                        currentIndex: [0, 100, 200, 300, 400, 600].indexOf(root.highlightDelayMs)
                        onActivated: settings.savePlayerPreferences([0, 100, 200, 300, 400, 600][currentIndex], Math.round(root.videoHeight))
                    }
                    AppButton { text: "翻译本句"; implicitHeight: 26
                        enabled: !study.busy && !study.enriching && study.sentenceCount > 0
                        onClicked: study.startTranslation(false) }
                    AppButton { text: study.contentLanguage === "en" ? "解释本句" : "解析本句"; implicitHeight: 26
                        enabled: !study.busy && !study.enriching && study.sentenceCount > 0
                        onClicked: study.startEnrichment(false) }
                }
                ListView {
                    id: readingList
                    objectName: "readingList"
                    x: 1; y: 38; width: parent.width - 2; height: parent.height - 39
                    clip: true; model: study.segments
                    property int trackedIndex: -1
                    property bool followPlayback: true
                    onMovementStarted: { followScroll.stop(); followPlayback = false }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 8; onPressedChanged: if (pressed) { followScroll.stop(); readingList.followPlayback = false } }
                    boundsBehavior: Flickable.StopAtBounds
                    spacing: 6
                    NumberAnimation { id: followScroll; target: readingList; property: "contentY"; duration: 260; easing.type: Easing.OutCubic }
                    onCountChanged: if (followPlayback) Qt.callLater(scrollToActive)
                    Connections {
                        target: study
                        function onStateChanged() { if (readingList.followPlayback && readingList.trackedIndex !== root.highlightedSentenceIndex) Qt.callLater(readingList.scrollToActive) }
                        function onSegmentsChanged() {
                            readingList.trackedIndex = -1
                            if (readingList.followPlayback) Qt.callLater(readingList.scrollToActive)
                        }
                        function onMediaChanged() { readingList.returnToCurrent() }
                    }
                    function returnToCurrent() { followPlayback = true; Qt.callLater(scrollToActive) }
                    MouseArea { anchors.fill: parent; acceptedButtons: Qt.NoButton; onWheel: function(wheel) { followScroll.stop(); readingList.followPlayback = false; wheel.accepted = false } }
                    function scrollToActive() {
                        if (!followPlayback || count === 0 || study.activeIndex < 0) { trackedIndex = -1; return }
                        trackedIndex = root.highlightedSentenceIndex
                        followScroll.stop()
                        var previousY = contentY
                        forceLayout()
                        positionViewAtIndex(trackedIndex, ListView.Center)
                        var centeredY = contentY
                        if (Math.abs(centeredY - previousY) > 1) {
                            contentY = previousY
                            followScroll.from = previousY
                            followScroll.to = centeredY
                            followScroll.start()
                        }
                    }
                    delegate: Rectangle {
                        id: readingCard
                        required property int index
                        required property var modelData
                        property bool active: index === root.highlightedSentenceIndex
                        property bool hasNotes: (modelData.analysis.grammar || "").length > 0 || (modelData.analysis.vocabulary || []).length > 0
                        width: readingList.width - 16
                        height: Math.max(105, (active && hasNotes ? analysisFooter.y + 16
                                      : translationLabel.y + translationLabel.height + 14))
                        x: 8; radius: 10
                        color: active ? Qt.tint(root.surfaceColor, Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.045)) : root.surfaceColor
                        border.color: active ? Qt.tint(root.surfaceColor, Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.22)) : "#F1F2F0"
                        Behavior on color { ColorAnimation { duration: 240 } }
                        Rectangle {
                            width: 3; height: parent.height - 18; y: 9; radius: 2
                            color: readingCard.active ? root.accentColor : "transparent"
                            Behavior on color { ColorAnimation { duration: 240 } }
                        }
                        Text {
                            x: 18; y: 13
                            text: root.timeText(readingCard.modelData.start * 1000)
                            color: readingCard.active ? root.accentColor : "#96A098"
                            font.family: "Segoe UI"; font.pixelSize: 11
                        }
                        Text {
                            anchors.right: parent.right; anchors.rightMargin: 18; y: 13
                            text: (readingCard.index + 1) + " / " + study.sentenceCount
                            color: "#A0A9A2"; font.family: "Segoe UI"; font.pixelSize: 11
                        }
                         Item {
                             id: textBlock
                             x: 18; y: 31
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
                                            && root.highlightSeconds >= modelData.start
                                            && root.highlightSeconds < modelData.end
                                        width: Math.max(wordText.implicitWidth, rubyText.implicitWidth) + 7
                                        height: study.contentLanguage === "en" ? 31 : 43; radius: 4
                                        color: "transparent"
                                        border.width: spoken ? 1.5 : 0
                                        border.color: root.accentColor
                                        Text {
                                            id: rubyText; anchors.horizontalCenter: parent.horizontalCenter; y: 0
                                            text: modelData.reading; color: "#68736C"
                                            font.family: "Yu Gothic UI"; font.pixelSize: 11
                                        }
                                        Text {
                                            id: wordText; anchors.horizontalCenter: parent.horizontalCenter; y: study.contentLanguage === "en" ? 2 : 13
                                            text: modelData.text
                                            color: "#202C25"
                                            font.family: "Yu Gothic UI"; font.pixelSize: 21; font.weight: Font.Bold
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
                                font.family: "Yu Gothic UI"; font.pixelSize: 21; font.weight: Font.Bold
                            }
                        }
                         Text {
                             id: translationLabel
                             x: 18; y: textBlock.y + textBlock.height + 5
                             width: parent.width - 36; height: contentHeight
                            text: readingCard.modelData.translation || (readingCard.modelData.analysis.translation
                                  ? "机译 · " + readingCard.modelData.analysis.translation
                                  : (readingCard.active ? "未添加中文释义" : ""))
                             wrapMode: Text.Wrap
                            color: readingCard.modelData.translation || readingCard.modelData.analysis.translation ? "#536056" : "#A0AAA1"
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 13
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
                            text: (readingCard.modelData.analysis.vocabulary || []).map(function(item) {
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
                            text: readingCard.modelData.analysis.model === "manual" ? "已手动校对" : "AI 生成 · 待校对"
                            color: "#9AA49D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 10
                        }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: { readingList.followPlayback = true; study.chooseSentence(readingCard.index); Qt.callLater(readingList.scrollToActive) }
                        }
                        Row {
                            z: 1; anchors.right: parent.right; anchors.rightMargin: 12; y: 7
                            spacing: 5; visible: false
                            ActionButton {
                                visible: readingCard.hasNotes
                                label: "校对解析"; enabled: !study.busy
                                onClicked: {
                                    analysisGrammarEdit.text = readingCard.modelData.analysis.grammar
                                    analysisVocabularyEdit.text = (readingCard.modelData.analysis.vocabulary || []).map(function(item) {
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
            Text { text: study.contentLanguage === "en" ? "英语原文" : "日文原文"; color: "#69766D"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12 }
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

    Shortcut { sequence: settings.values.shortcut_play; enabled: root.listeningKeysEnabled; onActivated: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play() }
    Shortcut { sequence: settings.values.shortcut_previous; enabled: root.listeningKeysEnabled && study.activeIndex > 0; onActivated: study.navigateSentence(-1) }
    Shortcut { sequence: settings.values.shortcut_next; enabled: root.listeningKeysEnabled && study.activeIndex + 1 < study.sentenceCount; onActivated: study.navigateSentence(1) }
    Shortcut { sequence: settings.values.shortcut_loop; enabled: root.listeningKeysEnabled && study.sentenceCount > 0; onActivated: study.toggleLoop() }
    Shortcut { sequence: settings.values.shortcut_replay; enabled: root.listeningKeysEnabled && study.sentenceCount > 0; onActivated: root.replayCurrentSentence() }
}
