import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: picker
    objectName: "writingTaskPicker"
    signal selected(string taskId, bool fresh)
    property string query: ""
    property string month: "all"
    property string status: "all"
    property string selectedSetId: ""
    property bool showQuestions: false
    property bool wide: width >= 930
    property var tasks: writer.writingTasks
    property bool importedBank: tasks.some(function(t) { return t.bank_schema === 1 })
    property var sets: groupSets()
    property var months: {
        var values = {}
        for (var i = 0; i < sets.length; ++i) values[sets[i].month] = true
        return [{key:"all", label:"全部月份"}].concat(Object.keys(values).sort().reverse().map(function(m) {
            return {key:m, label:m === "undated" ? "未标日期" : m.indexOf("month-") === 0 ? Number(m.slice(6)) + " 月" : m.slice(0, 4) + " · " + Number(m.slice(5)) + " 月"}
        }))
    }
    property var matches: sets.filter(function(s) {
        var key = picker.query.trim().toLowerCase().replace(/[\s.\-/月日]/g, "")
        return (picker.month === "all" || s.month === picker.month)
            && (picker.status === "all" || s.state === picker.status)
            && s.search.toLowerCase().replace(/[\s.\-/月日]/g, "").indexOf(key) >= 0
    })
    property var currentSet: {
        for (var i = 0; i < matches.length; ++i) if (matches[i].id === selectedSetId) return matches[i]
        return null
    }
    onMatchesChanged: { reconcile(); Qt.callLater(positionSelection) }
    onSelectedSetIdChanged: Qt.callLater(positionSelection)
    function positionSelection() {
        for (var i = 0; i < matches.length; ++i)
            if (matches[i].id === selectedSetId) { setList.positionViewAtIndex(i, ListView.Contain); return }
    }
    function groupSets() {
        var groups = {}
        for (var i = 0; i < tasks.length; ++i) {
            var task = tasks[i]
            if (!groups[task.set_id]) groups[task.set_id] = {id:task.set_id, title:task.set_title,
                month:task.source_month ? "month-" + String(task.source_month).padStart(2,"0") : task.set_date ? task.set_date.slice(0, 7) : "undated", date:task.set_date || "", order:task.source_order || 0,
                tasks:[], completed:0, started:0, pending:0, recent:"", search:task.set_title + " " + (task.set_date || "")}
            var group = groups[task.set_id]
            group.tasks.push(task)
            group.completed += task.completed ? 1 : 0
            group.started += task.state !== "not_started" ? 1 : 0
            group.pending += task.state === "in_progress" ? 1 : 0
            if (task.latest_activity > group.recent) group.recent = task.latest_activity
            group.search += " " + task.title
        }
        return Object.keys(groups).map(function(id) {
            var s = groups[id]
            s.state = s.pending ? "in_progress" : s.completed === s.tasks.length ? "completed" : s.started ? "in_progress" : "not_started"
            return s
        }).sort(function(a, b) { return b.order-a.order || b.date.localeCompare(a.date) || a.title.localeCompare(b.title) || a.id.localeCompare(b.id) })
    }
    function reconcile() {
        if (matches.some(function(s) { return s.id === picker.selectedSetId })) return
        var recent = matches.slice().sort(function(a, b) { return b.recent.localeCompare(a.recent) })
        selectedSetId = recent.length ? recent[0].id : ""
    }
    function choose(taskId, fresh) {
        close()
        Qt.callLater(function() { picker.selected(taskId, fresh) })
    }
    onOpened: {
        var recent = matches.slice().sort(function(a, b) { return b.recent.localeCompare(a.recent) })
        if (recent.length && recent[0].recent) selectedSetId = recent[0].id
        reconcile(); showQuestions = false; search.forceActiveFocus(); Qt.callLater(positionSelection)
    }
    modal: true; focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(1080, parent.width - 40)
    height: Math.min(680, parent.height - 48)
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: "#650F1C16" }
    background: Rectangle { radius: 15; color: settings.palette.surface; border.color: "#DCE4DE" }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        RowLayout { Layout.fillWidth: true
            Text { text: "托福专项"; color: "#26342C"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
            AppButton { text: "关闭"; flat: true; onClicked: picker.close() }
        }
        RowLayout { Layout.fillWidth: true; spacing: 8
            TextField { id: search; objectName: "writingTaskSearch"; Layout.fillWidth: true; Layout.preferredHeight: 36
                placeholderText: "搜索日期、来源或作文题目"; font.pixelSize: 13; onTextChanged: picker.query = text
                background: Rectangle { radius: 8; color: settings.palette.page; border.color: "#DCE4DE" } }
            AppCombo { visible: !picker.wide; Layout.preferredWidth: 145
                model: picker.months.map(function(m) { return m.label })
                currentIndex: { for (var i = 0; i < picker.months.length; i++) if (picker.months[i].key === picker.month) return i; return 0 }
                onActivated: { picker.month = picker.months[currentIndex].key; picker.showQuestions = false } }
            AppCombo { objectName: "writingTaskStatus"; Layout.preferredWidth: 112
                model: ["全部状态", "未开始", "进行中", "已完成"]
                currentIndex: ["all", "not_started", "in_progress", "completed"].indexOf(picker.status)
                onActivated: { picker.status = ["all", "not_started", "in_progress", "completed"][currentIndex]; picker.showQuestions = false } }
        }
        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#78877D"; font.pixelSize: 12
            text: picker.tasks.some(function(t) { return t.review_status === "demo" })
                ? "演示材料，非真题；题面与时限仅作功能预览。" : picker.importedBank ? "个人资料 · 含回忆整理版本；按来源选题，完成后可用 AI 修改。" : "按套选题，完成后继续使用原有 AI 修改。" }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
            Rectangle {
                visible: picker.wide; Layout.preferredWidth: 120; Layout.fillHeight: true
                radius: 10; color: settings.palette.page
                ListView { anchors.fill: parent; anchors.margins: 7; clip: true; spacing: 4
                    model: picker.months
                    delegate: AppButton { required property var modelData; width: ListView.view.width
                        text: modelData.label; flat: picker.month !== modelData.key; primary: picker.month === modelData.key
                        onClicked: picker.month = modelData.key }
                    ScrollBar.vertical: ScrollBar {}
                }
            }
            Rectangle {
                visible: picker.wide || !picker.showQuestions
                Layout.fillWidth: !picker.wide; Layout.preferredWidth: picker.wide ? 280 : -1; Layout.fillHeight: true
                radius: 10; color: settings.palette.page; border.color: "#E0E7E1"
                ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 8
                    Text { text: picker.importedBank ? "来源 · " + picker.matches.length + " 组" : "套卷 · " + picker.matches.length + " 套"; color: "#718077"; font.pixelSize: 12 }
                    ListView {
                        id: setList; objectName: "writingSetList"
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 7
                        model: picker.matches
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: Rectangle {
                            required property var modelData
                            objectName: "writingSet_" + modelData.id
                            width: setList.width; height: 86; radius: 8
                            color: picker.selectedSetId === modelData.id ? settings.palette.selection : settings.palette.surface
                            border.color: picker.selectedSetId === modelData.id ? settings.palette.accent : "#E0E7E1"
                            Column { x: 12; y: 12; width: parent.width - 24; spacing: 8
                                Text { width: parent.width; text: modelData.title; color: "#26342C"; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Text { text: "作文完成 " + modelData.completed + " / " + modelData.tasks.length; color: settings.palette.accent; font.pixelSize: 12 }
                                Text { text: modelData.state === "completed" ? "已完成" : modelData.state === "in_progress" ? "进行中" : "未开始"; color: "#78877D"; font.pixelSize: 11 }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: { picker.selectedSetId = parent.modelData.id; picker.showQuestions = true } }
                        }
                        Text { anchors.centerIn: parent; visible: picker.matches.length === 0; text: picker.importedBank ? "没有符合条件的来源" : "没有符合条件的套卷"; color: "#78877D"; font.pixelSize: 13 }
                    }
                }
            }
            Rectangle {
                visible: picker.wide || picker.showQuestions
                Layout.fillWidth: true; Layout.fillHeight: true
                radius: 10; color: settings.palette.page; border.color: "#E0E7E1"
                ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 12
                    RowLayout { Layout.fillWidth: true
                        AppButton { objectName: "writingTaskBackToSets"; visible: !picker.wide; text: picker.importedBank ? "← 来源" : "← 套卷"; flat: true; onClicked: picker.showQuestions = false }
                        Text { Layout.fillWidth: true; text: picker.currentSet ? picker.currentSet.title : picker.importedBank ? "选择来源" : "选择套卷"; elide: Text.ElideRight; font.pixelSize: 16; font.weight: Font.DemiBold; color: "#26342C" }
                    }
                    ListView {
                        id: taskList
                        objectName: "writingTaskList"
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 12
                        model: picker.currentSet ? picker.currentSet.tasks : []
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            required property var modelData
                            width: taskList.width; height: 170; radius: 10; color: settings.palette.surface; border.color: "#DCE4DE"
                            ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 8
                                Text { Layout.fillWidth: true; text: modelData.title; elide: Text.ElideRight; color: "#26342C"; font.pixelSize: 16; font.weight: Font.DemiBold }
                                Text { text: modelData.progress + " · " + Math.floor(modelData.limit_seconds / 60) + " 分钟" + (modelData.has_review ? " · 已有批改" : ""); color: settings.palette.accent; font.pixelSize: 12 }
                                Text { Layout.fillWidth: true; elide: Text.ElideRight; color: "#78877D"; font.pixelSize: 11
                                    text: modelData.completed ? "完成于 " + modelData.completed_at.slice(0, 10) + (modelData.state === "in_progress" ? " · 本次重做进行中" : "")
                                        : modelData.state === "in_progress" ? "正文与计时已保存，可继续作答" : "尚未作答，空草稿不计进度" }
                                Item { Layout.fillHeight: true }
                                RowLayout { Layout.fillWidth: true
                                    AppButton { visible: modelData.attempts > 0; text: "重新练习"; flat: true; onClicked: picker.choose(modelData.id, true) }
                                    Item { Layout.fillWidth: true }
                                    AppButton { objectName: "openTask_" + modelData.id; primary: true
                                        text: modelData.state === "not_started" ? "开始写作" : modelData.state === "in_progress" ? "继续写作" : "查看作文"
                                        onClicked: picker.choose(modelData.id, false) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
