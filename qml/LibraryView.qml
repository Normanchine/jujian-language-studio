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
    property string movePath: ""
    property var moveFolderOptions: [{id:"",name:"未分类"}].concat(study.libraryFolders.filter(function(f) {
        return f.language === (moveLanguage.currentIndex === 1 ? "ja" : "en")
    }))

    function matches(item, key) {
        if (key === "ja") return item.libraryLanguage === "日语"
        if (key === "en") return item.libraryLanguage === "英语"
        if (key === "favorites") return item.favorite
        if (key.indexOf("child:") === 0) return item.folderId === key.substring(6)
        if (key === "unfiled:ja") return item.libraryLanguage === "日语" && !item.folderId
        if (key === "unfiled:en") return item.libraryLanguage === "英语" && !item.folderId
        return true
    }
    function folderEntries() {
        var rows = [{key:"all",label:"全部媒体",icon:"▦",child:false}]
        var folders=study.libraryFolders
        for (var language of ["ja","en"]) {
            rows.push({key:language,label:language==="ja" ? "日语" : "英语",icon:language==="ja" ? "日" : "英",child:false})
            rows.push({key:"unfiled:"+language,label:"未分类",icon:"",child:true})
            for (var f of folders) if (f.language===language) rows.push({key:"child:"+f.id,label:f.name,icon:"",child:true})
        }
        rows.push({key:"favorites",label:"收藏夹",icon:"★",child:false})
        return rows
    }
    function moveProject(item) {
        movePath=item.path
        moveLanguage.currentIndex=item.libraryLanguage==="日语" ? 1 : 0
        moveFolder.currentIndex=Math.max(0,moveFolderOptions.findIndex(function(f) {return f.id===item.folderId}))
        movePopup.open()
    }

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
            if (!matches(item, folder)) continue
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
            if (matches(item,key)) count++
        }
        return count
    }

    Column {
        anchors.fill: parent; spacing: 13
        RowLayout { width: parent.width; height: 41
            Text { text: "媒体资料库"; color: "#26342C"; font.pixelSize: 19
                font.weight: Font.DemiBold; Layout.fillWidth: true }
            AppButton { objectName: "libraryCreateFolder"; text: "新建子文件夹"; onClicked: {
                createLanguage.currentIndex=library.folder==="ja" || library.folder==="unfiled:ja" ? 1 : 0
                folderName.clear(); createError.text=""; createFolderPopup.open()
            } }
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
                    Flickable {
                        anchors.fill: parent; clip: true; contentWidth: width; contentHeight: folderColumn.height+18
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    Column {
                        id: folderColumn; x: 9; y: 9; width: parent.width-18; spacing: 5
                        Text { text: "文件夹"; color: "#88958B"; font.pixelSize: 11
                            leftPadding: 10; bottomPadding: 6 }
                        Repeater {
                            model: library.folderEntries()
                            delegate: Rectangle {
                                required property var modelData
                                objectName: "libraryFolder_" + modelData.key
                                width: parent.width; height: 42; radius: 7
                                color: library.folder === modelData.key ? settings.palette.selection
                                     : folderHover.containsMouse ? settings.palette.page : "transparent"
                                Text { x: 10; anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon; color: library.themeAccent; font.pixelSize: 15 }
                                Text { x: 35; anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width-64; elide: Text.ElideRight
                                    text: modelData.label; color: modelData.child ? "#66776B" : "#344239"; font.pixelSize: modelData.child ? 12 : 13
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
                                text: modelData.libraryLanguage + " / " + modelData.folderName + " ⌄"
                                width: Math.min(170, implicitWidth); elide: Text.ElideRight
                                color: languageHover.containsMouse ? "#405F4B" : "#77857B"
                                font.pixelSize: 11
                                MouseArea { id: languageHover; anchors.fill: parent; z: 2
                                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: library.moveProject(modelData) }
                                ToolTip.visible: languageHover.containsMouse
                                ToolTip.text: "点击修改资料库分类"
                            }
                            Text { x: languageLabel.x + languageLabel.width + 5; y: 34
                                width: Math.max(40, parent.width - x - 96)
                                text: "· " + (modelData.video ? "视频" : "音频") + " · " + modelData.state
                                      + (modelData.available ? "" : " · 源文件已丢失")
                                elide: Text.ElideRight; color: "#77857B"; font.pixelSize: 11 }
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
        id: createFolderPopup; objectName: "libraryCreateFolderPopup"; modal: true; focus: true
        anchors.centerIn: Overlay.overlay; width: Math.min(440,library.width-32); padding: 24
        background: Rectangle { radius: 14; color: settings.palette.surface; border.color: "#DCE4DE" }
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: "新建语言子文件夹"; font.pixelSize: 18; font.weight: Font.DemiBold; color: "#26342C" }
            AppCombo { id: createLanguage; model: ["英语","日语"]; Layout.fillWidth: true }
            AppField { id: folderName; objectName: "libraryFolderName"; placeholderText: "例如：学术听力"; maximumLength: 40; Layout.fillWidth: true }
            Text { id: createError; visible: text.length>0; color: "#B64050"; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout {
                Item { Layout.fillWidth: true }
                AppButton { text: "取消"; onClicked: createFolderPopup.close() }
                AppButton { objectName: "libraryFolderApply"; text: "创建"; primary: true; enabled: folderName.text.trim().length>0
                    onClicked: {
                        var key=study.createLibraryFolder(createLanguage.currentIndex===1 ? "ja" : "en",folderName.text)
                        if (key) {library.folder="child:"+key;createFolderPopup.close()}
                        else createError.text=study.status
                    } }
            }
        }
    }
    Popup {
        id: movePopup; objectName: "libraryMovePopup"; modal: true; focus: true
        anchors.centerIn: Overlay.overlay; width: Math.min(440,library.width-32); padding: 24
        background: Rectangle { radius: 14; color: settings.palette.surface; border.color: "#DCE4DE" }
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: "整理到文件夹"; font.pixelSize: 18; font.weight: Font.DemiBold; color: "#26342C" }
            AppCombo { id: moveLanguage; model: ["英语","日语"]; Layout.fillWidth: true; onActivated: moveFolder.currentIndex=0 }
            AppCombo { id: moveFolder; model: library.moveFolderOptions; textRole: "name"; Layout.fillWidth: true }
            Text { text: "移动分类会保留音频、字幕和学习进度。"; color: "#748178"; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Item { Layout.fillWidth: true }
                AppButton { text: "取消"; onClicked: movePopup.close() }
                AppButton { text: "保存"; primary: true; onClicked: {
                    if (study.setProjectLocation(library.movePath,moveLanguage.currentIndex===1 ? "ja" : "en",(library.moveFolderOptions[moveFolder.currentIndex] || {}).id || "")) movePopup.close()
                } }
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
