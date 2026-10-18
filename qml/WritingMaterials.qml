import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: libraryView
    property color themeAccent: settings.palette.accent
    property string languageFilter: "all"
    property string kindFilter: "all"
    property string searchText: ""
    property string editingId: ""
    property string expandedKey: ""
    property bool returnToDraft: false
    property bool compact: false
    property string sourceFilter: "library"
    property int dialogWidth: width
    property int dialogHeight: height
    signal backToDraft()
    signal backToEssays()
    signal generateAi()
    signal previewAi(var material)
    signal targetAi(string expression)
    signal collectAi(var material)

    function openAdd() { addPopup.open() }

    function briefMeaning(value) {
        var text = String(value || "").replace(/^核心含义[:：]\s*/, "").trim()
        return text.split(/[。·]/)[0].slice(0, 70) || "待补充释义"
    }
    function isPhrase(item) {
        return item.kind === "grammar" || String(item.expression || "").trim().split(/\s+/).length > 1
    }
    function guidance(item) {
        var raw = libraryView.isPhrase(item) ? String(item.related || "") : String(item.usage || "")
        raw = raw.trim()
        if (!raw || raw.length > 280 || /\d+[.、]|不及物动词|状语|直接这样用/.test(raw)) return []
        return raw.split(/\n+/).map(function(line) { return line.trim() })
                  .filter(function(line) { return line.length > 0 && line.length < 90 }).slice(0, 4)
    }
    function exampleText(value) {
        var text = String(value || "").trim()
        if (text.startsWith("[") && text.endsWith("]"))
            return text.replace(/^\[\s*['"]/, "").replace(/['"]\s*\]$/, "")
                       .replace(/['"]\s*,\s*['"]/g, "\n")
        return text
    }

    function entries() {
        var result = []
        var query = searchText.trim().toLowerCase()
        if (compact && sourceFilter !== "library" && sourceFilter !== "favorites") {
            for (var ai = 0; ai < writer.materials.length; ai++) {
                var generated = writer.materials[ai]
                if (sourceFilter === "both") {
                    var alreadySaved = false
                    for (var saved = 0; saved < writer.library.length; saved++) {
                        var libraryItem = writer.library[saved]
                        if (libraryItem.essay_id === writer.currentEssayId
                                && libraryItem.language === writer.current.language
                                && libraryItem.expression.toLowerCase() === generated.expression.toLowerCase()) {
                            alreadySaved = true; break
                        }
                    }
                    if (alreadySaved) continue
                }
                if (kindFilter !== "all" && generated.kind !== kindFilter) continue
                if (query && (generated.expression + " " + (generated.meaning || ""))
                        .toLowerCase().indexOf(query) < 0) continue
                result.push({source: "ai", expression: generated.expression,
                             kind: generated.kind, meaning: generated.meaning,
                             usage: generated.usage, related: generated.related, example: generated.example})
            }
        }
        if (sourceFilter === "ai") return result
        for (var i = 0; i < writer.library.length; i++) {
            var item = writer.library[i]
            if (sourceFilter === "favorites") {
                if (!item.favorite) continue
            } else if (item.essay_id !== writer.currentEssayId) continue
            if (languageFilter !== "all" && item.language !== languageFilter) continue
            if (kindFilter !== "all" && item.kind !== kindFilter) continue
            if (query && (item.expression + " " + (item.meaning || "") + " " + (item.note || ""))
                    .toLowerCase().indexOf(query) < 0) continue
            result.push({source: "mine", id: item.id, language: item.language,
                         kind: item.kind, expression: item.expression,
                         meaning: item.meaning, usage: item.usage, related: item.related,
                         example: item.example, favorite: item.favorite,
                         essay_id: item.essay_id, context: item.context, note: item.note})
        }
        return result
    }
    function currentItem() {
        for (var i = 0; i < writer.library.length; i++)
            if (writer.library[i].id === editingId) return writer.library[i]
        return null
    }
    function openDetail(itemId) {
        editingId = itemId
        writer.clearMaterialStatus()
        var item = currentItem()
        if (!item) return
        meaningField.text = item.meaning || ""
        usageField.text = item.usage || ""
        relatedField.text = item.related || ""
        exampleField.text = item.example || ""
        noteField.text = item.note || ""
        detailPopup.open()
    }
    function reloadDetail() {
        if (!detailPopup.opened) return
        var item = currentItem()
        if (!item) return
        meaningField.text = item.meaning || ""
        usageField.text = item.usage || ""
        relatedField.text = item.related || ""
        exampleField.text = item.example || ""
        noteField.text = item.note || ""
    }
    Connections { target: writer; function onMaterialsChanged() { libraryView.reloadDetail() } }

    ColumnLayout {
        anchors.fill: parent; spacing: 14
        RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 42; visible: !libraryView.compact
            ColumnLayout { Layout.fillWidth: true; spacing: 3
                Text { text: "我的素材"; color: "#26342C"; font.pixelSize: 21; font.weight: Font.DemiBold }
                Text { text: "把学到的表达收进来，写作时再挑选使用"; color: "#819087"; font.pixelSize: 11 }
            }
            AppButton { text: libraryView.returnToDraft ? "返回作文" : "作文列表"
                onClicked: {
                    if (libraryView.returnToDraft) libraryView.backToDraft()
                    else libraryView.backToEssays()
                } }
            AppButton { text: "＋ 添加素材"; primary: true; onClicked: addPopup.open() }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; radius: 14
            color: libraryView.compact ? "transparent" : settings.palette.surface
            border.color: libraryView.compact ? "transparent" : "#E3E8E2"
            ColumnLayout { anchors.fill: parent; anchors.margins: libraryView.compact ? 0 : 20
                spacing: libraryView.compact ? 8 : 15
                RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 38; spacing: 9
                    visible: !libraryView.compact
                    TextField { id: searchField; Layout.fillWidth: true; Layout.preferredHeight: 37
                        placeholderText: "搜索词语、语法或笔记"; font.pixelSize: 12; leftPadding: 12
                        onTextChanged: libraryView.searchText = text
                        background: Rectangle { radius: 9; color: "#FAFBFA"
                            border.color: searchField.activeFocus ? libraryView.themeAccent : "#DCE4DE" } }
                    AppCombo { Layout.preferredWidth: 94; model: ["全部语言", "日语", "英语"]
                        onActivated: libraryView.languageFilter = ["all", "ja", "en"][currentIndex] }
                    AppCombo { Layout.preferredWidth: 94; model: ["全部类型", "词语短语", "语法句型"]
                        onActivated: libraryView.kindFilter = ["all", "vocabulary", "grammar"][currentIndex] }
                }
                TextField { Layout.fillWidth: true; Layout.preferredHeight: 36; visible: libraryView.compact
                    placeholderText: "搜索素材"; font.pixelSize: 12; leftPadding: 10
                    onTextChanged: libraryView.searchText = text
                    background: Rectangle { radius: 8; color: "#FAFBFA"
                        border.color: parent.activeFocus ? libraryView.themeAccent : "#DCE4DE" } }
                Text { Layout.fillWidth: true; text: libraryView.entries().length + " 条素材"
                    color: "#87938A"; font.pixelSize: 11 }
                ListView { id: itemList; Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; spacing: 9; model: libraryView.entries()
                    delegate: Rectangle {
                        id: materialCard
                        objectName: "writingMaterialCard"
                        required property var modelData
                        property string cardKey: modelData.source === "ai"
                            ? "ai:" + modelData.expression : "mine:" + modelData.id
                        property bool expanded: libraryView.expandedKey === cardKey
                        width: itemList.width - 6
                        height: Math.max(106, cardContent.implicitHeight + 20)
                        Behavior on height { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
                        clip: true; radius: 11; color: "#FBFCFA"
                        border.color: modelData.source === "ai" ? "#DCE9DF" : "#E8E5DA"
                        Rectangle { width: 3; height: parent.height - 22; x: 0; y: 11; radius: 2
                            color: modelData.source === "ai" ? "#5B9276" : "#B28F65" }
                        ColumnLayout { id: cardContent; x: 12; y: 10; width: parent.width - 24; spacing: 5
                            RowLayout { Layout.fillWidth: true
                                Text { text: modelData.expression; Layout.fillWidth: true
                                    wrapMode: Text.Wrap; color: "#26342C"
                                    font.pixelSize: 14; font.weight: Font.DemiBold }
                                Text { text: modelData.source === "ai" ? "AI" : "我的"
                                    color: modelData.source === "ai" ? "#4E8068" : "#9B7851"
                                    font.pixelSize: 11; font.weight: Font.DemiBold }
                            }
                            Text { text: libraryView.briefMeaning(modelData.meaning)
                                visible: !!modelData.meaning && !materialCard.expanded
                                Layout.fillWidth: true; wrapMode: Text.Wrap
                                maximumLineCount: 1; elide: Text.ElideRight
                                color: "#637268"; font.pixelSize: 11 }
                            Row { spacing: 5; Layout.topMargin: 1
                                AppButton { objectName: "inlineMaterialUsageButton"
                                    text: materialCard.expanded ? "收起 ↑" : "用法 ↓"; flat: true
                                    onClicked: libraryView.expandedKey = materialCard.expanded
                                        ? "" : materialCard.cardKey }
                                AppButton { text: (writer.current.targets || []).indexOf(modelData.expression) >= 0
                                                    ? "移出" : "目标"; flat: true
                                    visible: libraryView.returnToDraft && writer.currentPath
                                        && (modelData.source === "ai" || modelData.language === writer.current.language)
                                    onClicked: libraryView.targetAi(modelData.expression) }
                                AppButton { text: "收录"; flat: true; visible: modelData.source === "ai"
                                    onClicked: libraryView.collectAi(modelData) }
                            }
                            ColumnLayout { Layout.fillWidth: true; spacing: 8
                                visible: materialCard.expanded
                                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1
                                    color: "#E5EAE4" }
                                Text { text: libraryView.isPhrase(modelData) ? "相近表达" : "常用搭配"
                                    color: "#526A59"; font.pixelSize: 11; font.weight: Font.DemiBold }
                                Repeater { model: libraryView.guidance(modelData)
                                    delegate: Rectangle {
                                        required property string modelData
                                        Layout.fillWidth: true
                                        implicitHeight: patternText.implicitHeight + 12
                                        radius: 6; color: "#F0F5EF"
                                        Text { id: patternText; x: 9; y: 6; width: parent.width - 18
                                            text: modelData; wrapMode: Text.Wrap
                                            color: "#335843"; font.pixelSize: 12 }
                                    }
                                }
                                Text { visible: libraryView.guidance(modelData).length === 0
                                    text: modelData.source === "ai"
                                        ? "暂无相近表达。收录后可点 AI 整理补充。"
                                        : libraryView.isPhrase(modelData)
                                          ? "暂无相近表达，可点 AI 整理补充。"
                                          : "暂无简短搭配，可点 AI 整理补充。"
                                    Layout.fillWidth: true; wrapMode: Text.Wrap
                                    color: "#718277"; font.pixelSize: 11 }
                                Text { text: modelData.note || ""; visible: modelData.source === "mine" && !!modelData.note
                                    Layout.fillWidth: true; wrapMode: Text.Wrap
                                    color: "#718277"; font.pixelSize: 11 }
                                Row { spacing: 7
                                    AppButton { text: writer.materialBusy ? "整理中…" : "AI 整理"
                                        flat: true; enabled: !writer.materialBusy
                                        visible: modelData.source === "mine"
                                        onClicked: writer.enrichMaterial(modelData.id) }
                                    AppButton { text: "编辑资料"; flat: true
                                        visible: modelData.source === "mine"
                                        onClicked: libraryView.openDetail(modelData.id) }
                                    AppButton { text: modelData.favorite ? "取消收藏" : "收藏"; flat: true
                                        visible: modelData.source === "mine" && !!modelData.essay_id
                                        onClicked: writer.toggleMaterialFavorite(modelData.id) }
                                    AppButton { text: "用于本篇"; flat: true
                                        visible: modelData.source === "mine" && libraryView.sourceFilter === "favorites"
                                            && !!writer.currentEssayId && modelData.essay_id !== writer.currentEssayId
                                            && modelData.language === writer.current.language
                                        onClicked: writer.copyMaterialToCurrentEssay(modelData.id) }
                                }
                            }
                        }
                    }
                }
                Text { visible: itemList.count === 0; Layout.fillWidth: true
                    text: libraryView.sourceFilter === "ai" ? "暂无 AI 素材，点击生成获取。"
                         : libraryView.sourceFilter === "favorites" ? "暂无收藏的素材。" : "暂无素材，点击添加或生成。"
                    color: "#87938A"; font.pixelSize: 13 }
            }
        }
    }

    Popup { id: addPopup; objectName: "addWritingMaterialPopup"; modal: true; focus: true; anchors.centerIn: Overlay.overlay
        width: Math.min(520, libraryView.dialogWidth - 36); height: 466; padding: 22
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#650F1C16" }
        background: Rectangle { radius: 15; color: settings.palette.surface; border.color: "#DFE6DF" }
        onOpened: {
            if (libraryView.returnToDraft && writer.currentPath)
                addLanguage.currentIndex = writer.current.language === "en" ? 1 : 0
            expressionField.forceActiveFocus()
        }
        ColumnLayout { anchors.fill: parent; spacing: 12
            Text { text: "收录新素材"; color: "#26342C"; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { text: "先记下学到的内容，再决定是否让 AI 补充用法。"; color: "#7A8980"; font.pixelSize: 12 }
            RowLayout { Layout.fillWidth: true; spacing: 9
                AppCombo { id: addLanguage; Layout.fillWidth: true; model: ["日语", "英语"] }
                AppCombo { id: addKind; Layout.fillWidth: true; model: ["词语／短语", "语法／句型"] }
            }
            TextField { id: expressionField; Layout.fillWidth: true; Layout.preferredHeight: 42
                placeholderText: "输入词语、短语或语法名称"; font.pixelSize: 14; leftPadding: 12
                background: Rectangle { radius: 9; color: "#FAFBFA"
                    border.color: expressionField.activeFocus ? libraryView.themeAccent : "#DCE4DE" } }
            TextArea { id: contextField; Layout.fillWidth: true; Layout.preferredHeight: 78
                placeholderText: "看到它的原句（可留空）"; wrapMode: TextEdit.Wrap; font.pixelSize: 12
                background: Rectangle { radius: 9; color: "#FAFBFA"; border.color: "#DCE4DE" } }
            TextArea { id: quickNoteField; Layout.fillWidth: true; Layout.preferredHeight: 78
                placeholderText: "自己的理解或想记住的用法（可留空）"; wrapMode: TextEdit.Wrap; font.pixelSize: 12
                background: Rectangle { radius: 9; color: "#FAFBFA"; border.color: "#DCE4DE" } }
            Item { Layout.fillHeight: true }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: "原句和笔记会原样保存"; color: "#89958B"; font.pixelSize: 11 }
                AppButton { text: "取消"; onClicked: addPopup.close() }
                AppButton { text: "保存素材"; primary: true; enabled: expressionField.text.trim().length > 0
                    onClicked: {
                        var id = writer.saveMaterial(addLanguage.currentIndex === 0 ? "ja" : "en",
                            addKind.currentIndex === 0 ? "vocabulary" : "grammar",
                            expressionField.text, contextField.text, quickNoteField.text)
                        if (!id) return
                        addPopup.close()
                        expressionField.clear(); contextField.clear(); quickNoteField.clear()
                        if (libraryView.compact) libraryView.expandedKey = "mine:" + id
                        else libraryView.openDetail(id)
                    } }
            }
        }
    }

    Popup { id: detailPopup; objectName: "writingMaterialDetailPopup"; modal: true; focus: true; anchors.centerIn: Overlay.overlay
        width: Math.min(640, libraryView.dialogWidth - 36); height: Math.min(680, libraryView.dialogHeight - 28)
        padding: 20; closePolicy: Popup.CloseOnEscape
        Overlay.modal: Rectangle { color: "#650F1C16" }
        background: Rectangle { radius: 15; color: settings.palette.surface; border.color: "#DFE6DF" }
        ColumnLayout { anchors.fill: parent; spacing: 10
            Text { text: libraryView.currentItem() ? libraryView.currentItem().expression : "素材"
                color: "#26342C"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Text { text: libraryView.currentItem() && libraryView.currentItem().context
                    ? "学习原句：" + libraryView.currentItem().context : "补充准确的含义、用法和例句"
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#6A796F"; font.pixelSize: 12 }
            ScrollView { id: detailScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                Column { width: Math.max(0, detailScroll.width - 16); spacing: 10
                    Text { text: "含义"; color: "#26342C"; font.pixelSize: 12; font.bold: true }
                    TextArea { id: meaningField; width: parent.width; height: 86; wrapMode: TextEdit.Wrap
                        placeholderText: "核心含义与常见其他含义"; font.pixelSize: 12
                        background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: "#DCE4DE" } }
                    Text { text: "用法与搭配"; color: "#26342C"; font.pixelSize: 12; font.bold: true }
                    TextArea { id: usageField; width: parent.width; height: 100; wrapMode: TextEdit.Wrap
                        placeholderText: "接续、搭配、语域或易混淆之处"; font.pixelSize: 12
                        background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: "#DCE4DE" } }
                    Text { text: "相近表达（每行一条）"; color: "#26342C"; font.pixelSize: 12; font.bold: true }
                    TextArea { id: relatedField; width: parent.width; height: 90; wrapMode: TextEdit.Wrap
                        placeholderText: "短语或语法结构的相近说法"; font.pixelSize: 12
                        background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: "#DCE4DE" } }
                    Text { text: "例句"; color: "#26342C"; font.pixelSize: 12; font.bold: true }
                    TextArea { id: exampleField; width: parent.width; height: 80; wrapMode: TextEdit.Wrap
                        placeholderText: "写一句自然的例句"; font.pixelSize: 12
                        background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: "#DCE4DE" } }
                    Text { text: "我的笔记"; color: "#26342C"; font.pixelSize: 12; font.bold: true }
                    TextArea { id: noteField; width: parent.width; height: 100; wrapMode: TextEdit.Wrap
                        placeholderText: "自己的理解、提醒或记忆线索"; font.pixelSize: 12
                        background: Rectangle { radius: 8; color: "#FAFBFA"; border.color: "#DCE4DE" } }
                }
            }
            Text { text: writer.materialStatus || "AI 补充内容可核对并编辑；手写内容优先保留。"
                color: "#7B897E"; font.pixelSize: 11; Layout.fillWidth: true }
            RowLayout { Layout.fillWidth: true; spacing: 7
                AppButton { text: "删除"; destructive: true; onClicked: {
                    writer.deleteMaterial(libraryView.editingId); detailPopup.close() } }
                Item { Layout.fillWidth: true }
                AppButton { objectName: "materialEnrichButton"
                    text: writer.materialBusy ? "补充中…" : "AI 补充用法"; enabled: !writer.materialBusy
                    onClicked: {
                        writer.updateMaterial(libraryView.editingId, meaningField.text, usageField.text,
                            exampleField.text, noteField.text)
                        writer.updateMaterialRelated(libraryView.editingId, relatedField.text)
                        writer.enrichMaterial(libraryView.editingId)
                    } }
                AppButton { text: "保存并关闭"; primary: true; onClicked: {
                    writer.updateMaterial(libraryView.editingId, meaningField.text, usageField.text,
                        exampleField.text, noteField.text)
                    writer.updateMaterialRelated(libraryView.editingId, relatedField.text)
                    detailPopup.close()
                } }
            }
        }
    }
}
