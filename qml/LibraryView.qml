import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: library
    objectName: "mediaLibrary"
    signal openProject(string path)
    property color themeAccent: "#C94859"
    property string folder: "all"
    property string kind: "全部"
    property string progressFilter: "全部"
    property string pendingDelete: ""
    property string pendingDeleteTitle: ""
    property var pendingDeleteOptions: ({})
    property string deleteError: ""

    function confirmDelete(path, title) {
        pendingDelete = path
        pendingDeleteTitle = title
        pendingDeleteOptions = study.deletionOptions(path)
        deleteError = ""
        recycleMedia.checked = !!pendingDeleteOptions.defaultRecycle
        keepMedia.checked = !recycleMedia.checked
        deleteConfirm.open()
    }

    function filtered() {
        var result = []
        for (var i = 0; i < study.projects.length; i++) {
            var item = study.projects[i]
            if (folder === "ja" && item.libraryLanguage !== "日语") continue
            if (folder === "en" && item.libraryLanguage !== "英语") continue
            if (folder === "favorites" && !item.favorite) continue
            if (kind !== "全部" && (item.video ? "视频" : "音频") !== kind) continue
            if (progressFilter !== "全部" && item.state !== progressFilter) continue
            result.push(item)
        }
        return result
    }

    function folderCount(key) {
        if (key === "all") return study.projects.length
        var count = 0
        for (var i = 0; i < study.projects.length; i++) {
            var item = study.projects[i]
            if ((key === "ja" && item.libraryLanguage === "日语")
                    || (key === "en" && item.libraryLanguage === "英语")
                    || (key === "favorites" && item.favorite)) count++
        }
        return count
    }

    Column {
        anchors.fill: parent; spacing: 13
        RowLayout { width: parent.width; height: 41
            Text { text: "媒体资料库"; color: "#26342C"; font.pixelSize: 19
                font.weight: Font.DemiBold; Layout.fillWidth: true }
            AppButton { text: "刷新"; onClicked: study.refreshProjects() }
        }
        Rectangle {
            width: parent.width; height: parent.height - 54
            radius: 10; color: "#FFFFFF"; border.color: "#DFE4E0"
            Row {
                anchors.fill: parent; anchors.margins: 12; spacing: 14
                Rectangle {
                    width: 178; height: parent.height; radius: 9
                    color: "#F8FAF8"; border.color: "#EBEFEB"
                    Column {
                        anchors.fill: parent; anchors.margins: 9; spacing: 5
                        Text { text: "文件夹"; color: "#88958B"; font.pixelSize: 11
                            leftPadding: 10; bottomPadding: 6 }
                        Repeater {
                            model: [{key:"all", label:"全部媒体", icon:"▦"},
                                    {key:"ja", label:"日语", icon:"日"},
                                    {key:"en", label:"英语", icon:"英"},
                                    {key:"favorites", label:"收藏夹", icon:"★"}]
                            delegate: Rectangle {
                                required property var modelData
                                objectName: "libraryFolder_" + modelData.key
                                width: parent.width; height: 42; radius: 7
                                color: library.folder === modelData.key ? settings.palette.selection
                                     : folderHover.containsMouse ? settings.palette.page : "transparent"
                                Text { x: 10; anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon; color: library.themeAccent; font.pixelSize: 15 }
                                Text { x: 35; anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label; color: "#344239"; font.pixelSize: 13
                                    font.weight: library.folder === modelData.key ? Font.DemiBold : Font.Normal }
                                Text { anchors.right: parent.right; anchors.rightMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: library.folderCount(modelData.key); color: "#86948A"; font.pixelSize: 11 }
                                MouseArea { id: folderHover; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: library.folder = modelData.key }
                            }
                        }
                    }
                }
                Item {
                    width: parent.width - 192; height: parent.height
                    Row {
                        spacing: 8; height: 39
                        AppCombo { width: 100; model: ["全部", "视频", "音频"]
                            onActivated: library.kind = currentText }
                        AppCombo { width: 122; model: ["全部", "未开始", "未听完", "已听完", "未记录进度"]
                            onActivated: library.progressFilter = currentText }
                    }
                    ListView {
                        id: mediaList
                        y: 45; width: parent.width; height: parent.height - 78
                        clip: true; spacing: 7
                        model: library.filtered()
                        delegate: Rectangle {
                            required property var modelData
                            width: mediaList.width - 10; height: 88; radius: 8
                            color: rowHover.containsMouse ? "#F6F8F6" : "#FAFBFA"
                            border.color: "#EDF0ED"
                            Rectangle { x: 10; y: 11; width: 62; height: 58; radius: 5
                                color: modelData.video ? "#E4E9E6" : settings.palette.selection; clip: true
                                Image { id: cover; anchors.fill: parent; source: modelData.coverUrl
                                    fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready }
                                Text { anchors.centerIn: parent; text: modelData.video ? "▶" : "♫"
                                    color: library.themeAccent; font.pixelSize: 20; visible: cover.status !== Image.Ready }
                            }
                            Text { x: 84; y: 9; width: Math.max(80, parent.width - 320)
                                text: modelData.title; elide: Text.ElideRight
                                color: "#29362E"; font.pixelSize: 13; font.weight: Font.DemiBold }
                            Text { id: languageLabel; x: 84; y: 34; z: 2
                                text: modelData.libraryLanguage + " ⌄"
                                color: languageHover.containsMouse ? "#405F4B" : "#77857B"
                                font.pixelSize: 11
                                MouseArea { id: languageHover; anchors.fill: parent; z: 2
                                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: languageMenu.popup() }
                                ToolTip.visible: languageHover.containsMouse
                                ToolTip.text: "点击修改资料库分类"
                            }
                            Text { x: languageLabel.x + languageLabel.width + 5; y: 34
                                width: Math.max(40, parent.width - x - 96)
                                text: "· " + (modelData.video ? "视频" : "音频") + " · " + modelData.state
                                      + (modelData.available ? "" : " · 源文件已丢失")
                                elide: Text.ElideRight; color: "#77857B"; font.pixelSize: 11 }
                            Menu { id: languageMenu; x: 84; y: 54; z: 3
                                MenuItem { text: "归入日语"; enabled: modelData.libraryLanguage !== "日语"
                                    onTriggered: study.setProjectLibraryLanguage(modelData.path, "ja") }
                                MenuItem { text: "归入英语"; enabled: modelData.libraryLanguage !== "英语"
                                    onTriggered: study.setProjectLibraryLanguage(modelData.path, "en") }
                            }
                            Rectangle { x: 84; y: 70; width: Math.max(40, parent.width - 101)
                                height: 3; radius: 2; color: "#E9EDE9"
                                Rectangle { width: parent.width * modelData.progress; height: parent.height
                                    radius: 2; color: library.themeAccent } }
                            MouseArea { id: rowHover; anchors.fill: parent; hoverEnabled: true
                                enabled: modelData.available; cursorShape: Qt.PointingHandCursor
                                onClicked: library.openProject(modelData.path) }
                            AppButton { x: parent.width - 228; y: 8; width: 68; height: 31; z: 2
                                text: modelData.favorite ? "★ 已收藏" : "☆ 收藏"; flat: true
                                onClicked: study.toggleProjectFavorite(modelData.path) }
                            AppButton { x: parent.width - 154; y: 8; width: 58; height: 31; z: 2
                                text: "删除"; flat: true
                                onClicked: {
                                    library.confirmDelete(modelData.path, modelData.title)
                                } }
                            Text { x: parent.width - 86; y: 34; width: 75
                                text: modelData.available ? "打开 ›" : "不可打开"
                                color: modelData.available ? library.themeAccent : "#A06970"
                                font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                        }
                    }
                    Text { anchors.centerIn: mediaList; visible: mediaList.count === 0
                        text: library.folder === "favorites" ? "还没有收藏的媒体。" : "这个文件夹还没有媒体。"
                        color: "#87938A"; font.pixelSize: 13 }
                    Text { y: parent.height - 26; width: parent.width; height: 24
                        text: study.status; color: "#7C8980"; font.pixelSize: 11
                        elide: Text.ElideRight }
                }
            }
        }
    }

    Popup {
        id: deleteConfirm
        objectName: "mediaDeleteConfirm"
        modal: true; focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(560, library.width - 32); padding: 24
        height: deleteContent.implicitHeight + topPadding + bottomPadding
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#660F1C16" }
        background: Rectangle { radius: 14; color: "#FFFFFF"; border.color: "#E2E7E2" }
        contentItem: Column {
            id: deleteContent
            spacing: 10
            Text { text: "删除媒体"; color: "#26342C"; font.pixelSize: 18
                font.weight: Font.DemiBold }
            Text { width: parent.width; text: "「" + library.pendingDeleteTitle + "」"
                color: "#35443A"; font.pixelSize: 13; elide: Text.ElideRight }
            Text { width: parent.width; wrapMode: Text.Wrap
                text: library.pendingDeleteOptions.mediaPath || ""
                color: "#77857A"; font.pixelSize: 11; maximumLineCount: 3; elide: Text.ElideMiddle }
            RadioButton {
                id: keepMedia; objectName: "mediaDeleteKeepFile"
                text: "仅从资料库移除"; checked: true
            }
            Text { width: parent.width; text: "保留本地音视频文件。"; leftPadding: 30
                color: "#77857A"; font.pixelSize: 12 }
            RadioButton {
                id: recycleMedia; objectName: "mediaDeleteRecycleFile"
                text: "同时将音视频移入系统回收站"
                enabled: !!library.pendingDeleteOptions.canRecycle
            }
            Text { width: parent.width; wrapMode: Text.Wrap; leftPadding: 30
                text: library.pendingDeleteOptions.reason || "可在 Windows 回收站中恢复文件。"
                color: "#77857A"; font.pixelSize: 12 }
            Text { width: parent.width; wrapMode: Text.Wrap
                text: "两种方式都会将字幕和学习记录保留在恢复目录。"
                color: "#77857A"; font.pixelSize: 12 }
            Text { width: parent.width; wrapMode: Text.Wrap; visible: text.length > 0
                text: library.deleteError; color: "#B64050"; font.pixelSize: 12 }
            Row { spacing: 9; anchors.right: parent.right
                AppButton { text: "取消"; width: 82; onClicked: deleteConfirm.close() }
                AppButton { objectName: "mediaDeleteApply"
                    text: recycleMedia.checked ? "移入回收站并移出" : "移出资料库"
                    width: recycleMedia.checked ? 166 : 108; primary: true; destructive: true
                    onClicked: {
                        if (study.deleteProject(library.pendingDelete, recycleMedia.checked)) deleteConfirm.close()
                        else library.deleteError = study.status
                    } }
            }
        }
    }
}
