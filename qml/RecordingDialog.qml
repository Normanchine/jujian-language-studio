import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

Popup {
    id: dialog
    objectName: "recordingDialog"
    property var service
    signal settingsRequested()
    signal previewRequested()
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(760, parent.width - 48)
    height: Math.min(hasReview ? 660 : service.active ? 460 : service.pending.length > 0
                     ? Math.min(650, 430 + service.pending.length * 42) : 430, parent.height - 48)
    modal: true; focus: true; padding: 24
    closePolicy: Popup.CloseOnEscape
    property bool hasReview: !!service.review.duration
    property string languageCode: languageChoice.currentIndex === 1 ? "ja" : "en"
    property string selectedFolderId: ""
    property var folderOptions: [{id: "", name: "未分类"}].concat(study.libraryFolders.filter(function(f) { return f.language === dialog.languageCode }))
    property real startSeconds: Math.max(0, Number(startField.text) || 0)
    property real endSeconds: Math.max(0, Number(endField.text) || 0)
    property real keepSeconds: service.preferences.padding
    property int thresholdDb: service.preferences.thresholdDb
    background: Rectangle { radius: 16; color: settings.palette.surface; border.color: "#DCE4DE" }
    Overlay.modal: Rectangle { color: "#660F1C16" }

    function clock(seconds) {
        seconds = Math.max(0, Math.floor(seconds))
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
    }
    function saveDetails() {
        if (hasReview) service.saveDetails(nameField.text, languageCode, selectedFolderId,startSeconds,endSeconds)
    }
    function loadReview() {
        nameField.text = service.draft.name || "电脑录音"
        languageChoice.currentIndex = service.draft.language === "ja" ? 1 : 0
        var selection=service.draft.selection || service.review
        startField.text = selection.start.toFixed(2)
        endField.text = selection.end.toFixed(2)
        transcribeChoice.checked=service.preferences.transcribe
        selectedFolderId=service.draft.folder || ""
        waveCanvas.requestPaint()
    }
    function reprocess() {
        saveDetails(); audition.stop(); audition.source = ""
        service.analyze(keepSeconds, thresholdDb)
    }
    function revealNewFolder() {
        Qt.callLater(function() {
            var flick=bodyScroll.contentItem
            if (flick && flick.contentItem && flick.contentY!==undefined) {
                var bottom=newFolderRow.mapToItem(flick.contentItem,0,newFolderRow.height).y+12
                flick.contentY=Math.max(0,Math.min(bottom-flick.height,flick.contentHeight-flick.height))
            }
            newFolderName.forceActiveFocus()
        })
    }
    onOpened: {
        if (hasReview) loadReview()
        service.refreshPending()
    }
    onClosed: { audition.stop(); audition.source = ""; saveDetails() }
    onStartSecondsChanged: waveCanvas.requestPaint()
    onEndSecondsChanged: waveCanvas.requestPaint()

    Connections {
        target: dialog.service
        function onReviewReady() { dialog.loadReview(); dialog.open(); Qt.callLater(function() {nameField.forceActiveFocus()}) }
        function onImported(path, transcribe) { dialog.close() }
    }
    MediaPlayer {
        id: audition; objectName: "recordingAudition"
        property bool pendingStart: false
        audioOutput: AudioOutput { volume: 0.8 }
        onMediaStatusChanged: function(status) {
            if (pendingStart && (audition.mediaStatus === MediaPlayer.LoadedMedia || audition.mediaStatus === MediaPlayer.BufferedMedia)) {
                pendingStart=false; position=Math.round(dialog.startSeconds*1000); play()
            }
        }
        onErrorOccurred: function(error, message) { auditionError.text="试听失败："+message; pendingStart=false }
        onPositionChanged: function(position) {
            if (audition.position >= dialog.endSeconds * 1000 && audition.playbackState === MediaPlayer.PlayingState) pause()
        }
    }
    component Entry: AppField { }
    component Caption: Text {
        color: "#748178"; font.pixelSize: 12; wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Text { text: service.active ? "录制电脑声音" : dialog.hasReview ? "试听并导入录音" : "录制导入"
                font.pixelSize: 21; font.weight: Font.DemiBold; color: "#26342C"; Layout.fillWidth: true }
            AppButton { objectName: "recordingCollapse"; text: "×"; font.pixelSize: 20; implicitWidth: 34; implicitHeight: 34; flat: true
                ToolTip.visible: hovered; ToolTip.text: service.active ? "收起录制窗口" : "暂存并关闭"; onClicked: dialog.close() }
        }
        Caption { text: service.active ? "切换到刷题系统播放音频。录制会在后台继续，播放结束后再停止。"
                                      : dialog.hasReview ? "试听并调整范围，再选择名称、语言和文件夹。" : "暂存录音可继续导入；从首页可以开始新的录制。" }
        ScrollView {
            id: bodyScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded; width: 6
                background: Item { }
                contentItem: Rectangle { implicitWidth: 5; radius: 2.5; color: "#B8C7BC" }
            }
            ColumnLayout {
                width: bodyScroll.availableWidth; spacing: 16
                Rectangle {
                    visible: service.active; Layout.fillWidth: true; implicitHeight: 152; radius: 12
                    color: settings.palette.selection
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 18; spacing: 10
                        RowLayout {
                            Rectangle { width: 10; height: 10; radius: 5; color: "#C94859" }
                            Text { text: service.state === "recording" ? "正在录制  " + dialog.clock(service.seconds) : service.state === "starting" ? "正在准备…" : "正在保存…"
                                color: "#26342C"; font.pixelSize: 24; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        }
                        Rectangle {
                            Layout.fillWidth: true; implicitHeight: 8; radius: 4; color: "#FFFFFF"
                            Rectangle { width: parent.width * Math.min(1, Math.sqrt(service.level)); height: parent.height; radius: 4; color: settings.palette.accent }
                        }
                        Caption { text: service.shortcutAvailable ? "停止快捷键：Ctrl + Shift + R（切换到其他软件后仍可使用）"
                                           : "停止方式：点击首页或底栏的停止按钮，也可使用托盘菜单。" }
                        Caption { text: "静音时也会继续录制，讲座中间的停顿会完整保留。" }
                    }
                }
                RowLayout {
                    visible: dialog.hasReview; Layout.fillWidth: true
                    Caption { text: "首尾各留 " + (service.review.padding || .5) + " 秒 · 保留中间停顿" }
                    AppButton { text: "录制设置"; flat: true; height: 28; enabled: !service.busy; onClicked: dialog.settingsRequested() }
                }
                ColumnLayout {
                    visible: dialog.hasReview; Layout.fillWidth: true; spacing: 12
                    Caption { text: "原录音 " + dialog.clock(service.review.duration || 0) + "  →  导入 " + dialog.clock(dialog.endSeconds - dialog.startSeconds) }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 90; radius: 10; color: settings.palette.page; clip: true
                        Canvas {
                            id: waveCanvas; objectName: "recordingWaveform"; anchors.fill: parent; anchors.margins: 8
                            onWidthChanged: requestPaint()
                            onPaint: {
                                var ctx = getContext("2d"); ctx.clearRect(0, 0, width, height)
                                var peaks = service.review.peaks || []; var duration = service.review.duration || 1
                                var start = dialog.startSeconds / duration * width, end = dialog.endSeconds / duration * width
                                ctx.fillStyle = "#DCE3DE"; ctx.fillRect(0,0,start,height); ctx.fillRect(end,0,width-end,height)
                                ctx.fillStyle = settings.palette.accent
                                for (var i=0;i<peaks.length;i++) {
                                    var h=Math.max(2,Math.sqrt(peaks[i])*height*0.9)
                                    ctx.fillRect(i/peaks.length*width,(height-h)/2,Math.max(1,width/peaks.length-1),h)
                                }
                                ctx.fillStyle="#B34E43"; ctx.fillRect(start,0,2,height); ctx.fillRect(end-2,0,2,height)
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Text { text: "起点（秒）"; color: "#748178"; font.pixelSize: 12 }
                        Entry { id: startField; objectName: "recordingTrimStart"; text: "0.00"; Layout.preferredWidth: 85
                            inputMethodHints: Qt.ImhFormattedNumbersOnly; validator: DoubleValidator { bottom: 0; decimals: 2; locale: "C" } }
                        Text { text: "终点（秒）"; color: "#748178"; font.pixelSize: 12 }
                        Entry { id: endField; objectName: "recordingTrimEnd"; text: "0.00"; Layout.preferredWidth: 85
                            inputMethodHints: Qt.ImhFormattedNumbersOnly; validator: DoubleValidator { bottom: 0; decimals: 2; locale: "C" } }
                        Item { Layout.fillWidth: true }
                        AppButton { objectName: "recordingPreviewPlay"; text: audition.playbackState === MediaPlayer.PlayingState ? "停止试听" : "试听裁剪结果"
                            enabled: !service.busy && dialog.endSeconds > dialog.startSeconds
                            onClicked: {
                                if (audition.playbackState === MediaPlayer.PlayingState) { audition.stop(); return }
                                dialog.previewRequested(); auditionError.text=""
                                if (audition.source.toString() !== service.previewUrl) {
                                    audition.pendingStart=true; audition.source=service.previewUrl
                                } else { audition.position = Math.round(dialog.startSeconds * 1000); audition.play() }
                            } }
                    }
                    Caption { visible: audition.playbackState === MediaPlayer.PlayingState
                        text: "试听位置 " + dialog.clock(audition.position/1000) }
                    Caption { id: auditionError; visible: text.length>0; color: "#B64050" }
                    Caption { text: "名称" }
                    Entry { id: nameField; objectName: "recordingName"; Layout.fillWidth: true; maximumLength: 120
                        placeholderText: "例如：TPO 01 · Lecture 1 · 生物学"; onEditingFinished: dialog.saveDetails() }
                    Caption { text: "语言与资料库文件夹" }
                    RowLayout {
                        Layout.fillWidth: true
                        AppCombo { id: languageChoice; objectName: "recordingLanguage"; model: ["英语", "日语"]; Layout.preferredWidth: 100; implicitHeight: 40
                            enabled: !service.busy; onActivated: { dialog.selectedFolderId = ""; dialog.saveDetails() } }
                        AppCombo { id: folderChoice; objectName: "recordingFolder"; model: dialog.folderOptions; textRole: "name"; Layout.fillWidth: true; implicitHeight: 40
                            currentIndex: Math.max(0,dialog.folderOptions.findIndex(function(f) {return f.id===dialog.selectedFolderId}))
                            enabled: !service.busy; onActivated: {dialog.selectedFolderId=(dialog.folderOptions[currentIndex] || {}).id || "";dialog.saveDetails()} }
                        AppButton { objectName: "recordingNewFolder"; text: "+ 新建文件夹"; implicitHeight: 40; enabled: !service.busy
                            onClicked: {newFolderRow.visible=!newFolderRow.visible;if(newFolderRow.visible)dialog.revealNewFolder()} }
                    }
                    RowLayout {
                        id: newFolderRow; visible: false; Layout.fillWidth: true
                        Entry { id: newFolderName; objectName: "recordingNewFolderName"; Layout.fillWidth: true; maximumLength: 40
                            placeholderText: "例如：学术听力、日常对话听力" }
                        AppButton { objectName: "recordingCreateFolder"; text: "创建"; primary: true; implicitHeight: 40; enabled: newFolderName.text.trim().length > 0 && !service.busy
                            onClicked: {
                                var key=study.createLibraryFolder(dialog.languageCode,newFolderName.text)
                                if (key) {
                                    dialog.selectedFolderId=key
                                    newFolderName.clear(); newFolderRow.visible=false; dialog.saveDetails()
                                } else folderError.text=study.status
                            } }
                        AppButton { text: "取消"; flat: true; implicitHeight: 40; onClicked: newFolderRow.visible = false }
                    }
                    Caption { id: folderError; visible: text.length>0; color: "#B64050" }
                }
                Caption { text: service.status; visible: !dialog.hasReview || service.state!=="review" }
                Caption { objectName: "recordingError"; text: service.error; visible: text.length>0; color: "#B64050" }
                AppButton { visible: service.state === "error" && !!service.draft.id && service.draft.status !== "imported"
                    text: "重新处理暂存录音"; enabled: !service.busy; onClicked: dialog.reprocess() }
                ColumnLayout {
                    visible: !service.active && !service.busy && !dialog.hasReview && service.pending.length > 0
                    Layout.fillWidth: true; spacing: 6
                    Caption { text: "暂存录音 · " + service.pending.length + " 条（关闭窗口或重启后可继续导入）" }
                    Repeater {
                        model: service.pending
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Text { text: modelData.name; elide: Text.ElideRight; Layout.fillWidth: true; color: "#344239"; font.pixelSize: 13 }
                            AppButton { text: "继续导入"; onClicked: service.recover(modelData.id) }
                        }
                    }
                }
            }
        }
        AppCheck { id: transcribeChoice; objectName: "recordingTranscribe"; text: "导入后立即开始本地转写"; checked: service.preferences.transcribe
            visible: dialog.hasReview; enabled: !service.busy }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: "#E1E7E2" }
        RowLayout {
            Layout.fillWidth: true
            Caption { text: dialog.hasReview ? "原始录音保留，可稍后继续导入。" : service.active ? "录制中可以收起此窗口。" : "从首页点击“开始录制”即可录音。" }
            AppButton { objectName: "recordingLater"; text: "稍后导入"; flat: true; visible: dialog.hasReview; enabled: !service.busy; onClicked: dialog.close() }
            AppButton { text: "录制设置"; visible: !dialog.hasReview && !service.active; flat: true; onClicked: dialog.settingsRequested() }
            AppButton { objectName: "recordingStop"; visible: service.active; text: "停止并整理"; primary: true
                enabled: service.state !== "stopping"; onClicked: service.stop() }
            AppButton { objectName: "recordingImport"; visible: dialog.hasReview; text: service.state === "importing" ? "正在导入…" : "导入资料库"; primary: true
                enabled: !service.busy && !study.busy && !study.enriching && nameField.text.trim().length>0
                         && dialog.endSeconds>dialog.startSeconds && dialog.endSeconds <= (service.review.duration || 0)+0.002
                onClicked: {
                    audition.stop(); audition.source=""
                    service.importRecording(nameField.text,dialog.languageCode,dialog.selectedFolderId,
                                            dialog.startSeconds,dialog.endSeconds,transcribeChoice.checked)
                } }
        }
    }
}
