import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: home
    objectName: "readingHome"
    property var materials: []
    property var savedState: ({})
    signal stateEdited(var state)
    property string language: "en"
    property string route: "hub"
    property string collection: "all"
    property string completionScope: "all"
    property string materialScope: "all"
    property var destinationMemory: ({})
    property string query: ""
    property int filterIndex: 0
    property int sortIndex: 0
    property var collapsed: ({})
    property var completedSections: ({})
    property var languageMemory: ({})
    property var favoriteIds: ({})
    property var readingRecords: ({})
    property var selectedArticle: ({})
    property var managedArticle: ({})
    property var managedFolder: ({})
    property bool articleOpen: false
    property string articleMode: "intensive"
    property string practiceError: ""
    property string reviewReturnId: ""
    property string grammarReturnRoute: "hub"
    property bool grammarReturnArticle: false
    property var grammarReturnSelection: ({})
    property string studyReturnRoute: "hub"
    property bool studyReturnArticle: false
    property var studyReturnSelection: ({})
    property int reviewReturnIndex: 0
    property bool compact: width < 850
    property bool restoring: false
    property color ink: "#293B32"
    property color muted: "#7B8981"
    property color accent: settings.palette.accent
    property color line: "#DFE7E1"
    property var languageItems: materials.filter(function(a) { return a.language === home.language }).map(function(a) {
        return Object.assign({}, a, home.readingRecords[a.id] || {}, reading.summaries[a.id] || {});
    })
    property int favoriteCount: languageItems.filter(function(a) { return home.isFavorite(a) }).length
    property int intensiveOnlyCount: languageItems.filter(function(a){return a.hasQuestions===false}).length
    property int personalArticleCount: languageItems.filter(function(a){return a.sourceKind==='personal_import' || a.sourceKind==='user_paste'}).length
    property bool personalScope: collection==='personal' || collection.indexOf('personal-folder-')===0
    property var personalFolders: reading.importer.folders.filter(function(f) {return f.language===home.language;}).map(function(f) {
        return Object.assign({},f,{count:home.languageItems.filter(function(a){return a.setId===f.id;}).length});
    })
    property bool hasReviewedMaterials: languageItems.some(function(a){return a.sourceKind==='toefl_personal_materials'})
    function matchesMaterial(a) {return materialScope==='all' || (materialScope==='practice' ? a.hasQuestions!==false : a.hasQuestions===false);}
    function chooseMaterial(value) {
        materialScope=value;completionScope='all';collection='all';filterIndex=0;query='';
        articles.positionViewAtBeginning();persist();
    }
    property var exercises: languageItems.filter(function(a) { return a.hasQuestions !== false }).sort(function(a,b) { return a.order-b.order })
    function practiceTime(a) { return Math.max(a.practiceCompletedAt || 0, a.lastPracticeAt || 0, a.lastMode !== "intensive" ? (a.visited || 0) : 0); }
    property var latestPractice: exercises.filter(function(a) { return a.lastPracticeAt || a.practiceCompletedAt || a.lastMode === "practice" || (!a.lastMode && (a.practice === "progress" || a.practice === "done")) }).sort(function(a,b) {
        return home.practiceTime(b) - home.practiceTime(a);
    })[0] || ({})
    property var resumeArticle: latestPractice.pending || latestPractice.practice === "progress" ? latestPractice : ({})
    property var nextArticle: {
        var pending = exercises.filter(function(a) { return a.practice !== "done" });
        if (pending.length) {
            var sameSet = pending.filter(function(a) { return a.setId === home.latestPractice.setId });
            var following = pending.filter(function(a) { return a.order > home.latestPractice.order });
            return sameSet[0] || following[0] || pending[0];
        }
        if (exercises.length) return ({});
        var plain = languageItems.slice().sort(function(a,b) { return a.order-b.order });
        return plain.filter(function(a) { return !a.visited })[0] || plain[0] || ({});
    }
    property bool practiceComplete: exercises.length > 0 && !nextArticle.id && !resumeArticle.id
    property var favoritePreview: languageItems.filter(function(a) { return home.isFavorite(a) }).slice(0, 4)
    property var materialPreview: {
        var ordered = languageItems.slice().sort(function(a,b) { return a.order-b.order });
        if (!exercises.length || practiceComplete) return ordered.slice(0,4);
        var cursor = ordered.findIndex(function(a) { return a.id === home.nextArticle.id });
        var remaining = ordered.filter(function(a) { return a.hasQuestions !== false && a.practice !== "done" });
        if (!remaining.length) return ordered.slice(0,4);
        var following = remaining.filter(function(a) { return cursor < 0 || a.order >= ordered[cursor].order });
        return following.concat(remaining.filter(function(a) { return following.indexOf(a)<0 })).slice(0,4);
    }
    function matchesCompletion(a) {
        return completionScope === "all" || (a.hasQuestions !== false && (completionScope === "done" ? a.practice === "done" : a.practice !== "done"));
    }
    function chooseCompletion(value) {
        completionScope = value; filterIndex = 0; collection = "all"; query = "";
        articles.positionViewAtBeginning(); persist();
    }
    function openCompleted() {
        rememberDestination(); route = "library"; applyState({collection:"all", completion:"done"});
        Qt.callLater(function() { articles.positionViewAtBeginning(); persist(); });
    }
    function rememberDestination() {
        if (route === "hub") return;
        var next = Object.assign({}, destinationMemory); next[language+":"+route] = snapshot(); destinationMemory = next;
    }
    function openDestination(value) {
        rememberDestination(); route = value;
        var state = destinationMemory[language+":"+value] || {collection:value === "favorites" ? "favorites" : "all"};
        applyState(state); Qt.callLater(function() { restoreList(state); persist(); });
    }
    function goHub() { rememberDestination(); route = "hub"; persist(); }
    function openGrammarFavorites() {
        if (route==="grammarFavorites") { if (articleOpen) articlePage.savePosition(); articleOpen=false; return; }
        grammarReturnRoute=route; grammarReturnArticle=articleOpen;
        grammarReturnSelection=selectedArticle;
        if (articleOpen) {
            articlePage.savePosition();
            if (selectedArticle.language!==language) changeLanguage(selectedArticle.language);
            articleOpen=false;
        }
        route="grammarFavorites";
    }
    function leavePractice() {
        if (articleOpen && articleMode === "practice") { practicePage.savePosition(); reading.leave(); articleOpen = false; }
    }
    function openStudyFavorites() {
        studyReturnRoute=route;studyReturnArticle=articleOpen;studyReturnSelection=selectedArticle;
        if (articleOpen) {articlePage.savePosition();articleOpen=false;}
        studyFavorites.notice="";route="studyFavorites";
    }
    function showHome() { if (articleOpen && articleMode === "intensive") articlePage.savePosition(); leavePractice(); articleOpen = false; goHub(); }
    function reviewLabel(a) {
        if (a.lastReviewed) return "上次精读 · " + new Date(a.lastReviewed).toLocaleDateString(Qt.locale(), "M月d日");
        if (a.position > 0 || a.intensive === "progress") return "上次停在第 " + (a.readParagraph || 1) + " 段";
        return "";
    }
    function isFavorite(a) { return favoriteIds[a.id] === undefined ? !!a.demoFavorite : !!favoriteIds[a.id]; }
    function toggleFavorite(a) {
        var next = Object.assign({}, favoriteIds); next[a.id] = !isFavorite(a); favoriteIds = next; persist();
    }
    function updateRecord(id, changes) {
        var next = Object.assign({}, readingRecords); next[id] = Object.assign({}, next[id] || {}, changes);
        readingRecords = next; persist();
    }
    property var groups: {
        var result = [], known = {};
        languageItems.forEach(function(a) {
            if (!known[a.group]) { known[a.group] = true; result.push(a.group) }
        });
        if (!known['我的文章'] && reading.importer.folders.some(function(f) { return f.language===home.language; })) result.push('我的文章');
        return result.sort(function(a,b) {
            if (a==='我的文章') return -1;
            if (b==='我的文章') return 1;
            if (a.indexOf('托福资料 · ')===0 && b.indexOf('托福资料 · ')===0) {
                var am=a.match(/(\d+)月/),bm=b.match(/(\d+)月/);
                return (am ? Number(am[1]) : 99)-(bm ? Number(bm[1]) : 99);
            }
            return 0;
        });
    }
    function sectionIds(group) {
        var ids = [];
        languageItems.forEach(function(a) {
            if (a.group === group && ids.indexOf(a.setId) < 0) ids.push(a.setId);
        });
        return ids;
    }
    function groupManuallyComplete(group) {
        var ids = sectionIds(group);
        return ids.length > 0 && ids.every(function(id) { return home.completedSections[id] === true });
    }
    function toggleSectionComplete(id) {
        var article = languageItems.find(function(a) { return a.setId === id });
        if (!article) return;
        var marks = Object.assign({}, completedSections);
        if (marks[id]) delete marks[id];
        else marks[id] = true;
        completedSections = marks;
        // Use every source in the month, including sources hidden by a filter.
        if (marks[id] && groupManuallyComplete(article.group)) {
            var folds = Object.assign({}, collapsed); folds[article.group] = true; collapsed = folds;
        }
        persist();
    }
    property var directory: {
        var result = [];
        groups.forEach(function(g) {
            var seen = {}, sets = [];
            home.languageItems.filter(function(a) { return a.group === g && home.matchesMaterial(a) }).sort(function(a,b){
                return a.order-b.order || (a.sourceGroup || '').localeCompare(b.sourceGroup || '');
            }).forEach(function(a) {
                if (seen[a.setId]) return;
                seen[a.setId] = true;
                var articles = home.languageItems.filter(function(b) { return b.setId === a.setId && home.matchesMaterial(b) });
                var questions = articles.filter(function(b) { return b.hasQuestions !== false });
                var done = questions.filter(function(b) { return b.practice === "done" }).length;
                var started = done > 0 || questions.some(function(b) { return b.practice === "progress" });
                var status = !questions.length ? "plain" : done === questions.length ? "done" : started ? "progress" : "new";
                if (home.completionScope !== "all" && (!questions.length || (home.completionScope === "done" ? done === 0 : status === "done"))) return;
                sets.push({kind:"set", label:a.setTitle, id:a.setId, count:questions.length, articleCount:articles.length,
                           practiceCount:questions.length, intensiveCount:articles.length-questions.length,
                           sourceGroup:a.sourceKind==='toefl_personal_materials' || a.sourceKind==='personal_import' || a.sourceKind==='user_paste', done:done, status:status,
                           manuallyComplete:home.completedSections[a.setId] === true});
            });
            if (g === '我的文章' && home.materialScope !== 'practice')
                reading.importer.folders.filter(function(f) { return f.language===home.language; }).forEach(function(f) {
                    if (!seen[f.id]) sets.push({kind:"set",label:f.name,id:f.id,count:0,articleCount:0,practiceCount:0,intensiveCount:0,sourceGroup:true,done:0,status:"plain",manuallyComplete:false});
                });
            if (!sets.length) return;
            result.push({kind:"group", label:g, id:g, total:sets.length, manuallyComplete:home.groupManuallyComplete(g)});
            if (!home.collapsed[g]) result = result.concat(sets);
        }); return result;
    }
    property var results: {
        var needle = query.trim().toLowerCase();
        var found = languageItems.filter(function(a) {
            if (home.route === "favorites" && !home.isFavorite(a)) return false;
            if (home.collection==='personal' && a.sourceKind!=='personal_import' && a.sourceKind!=='user_paste') return false;
            if (home.collection.indexOf('personal-folder-')===0 && a.setId!==home.collection) return false;
            if (!home.matchesMaterial(a)) return false;
            if (!home.matchesCompletion(a)) return false;
            if (!needle && home.collection !== "all" && home.collection !== "favorites" && home.collection !== "personal" && home.collection.indexOf('personal-folder-')!==0 && a.setId !== home.collection) return false;
            if (needle && [a.title, a.setTitle, a.group, a.body].join(" ").toLowerCase().indexOf(needle) < 0) return false;
            if (home.filterIndex > 0 && home.filterIndex < 5 && a.hasQuestions === false) return false;
            if (home.filterIndex === 1 && a.practice !== "new") return false;
            if (home.filterIndex === 2 && a.practice !== "progress") return false;
            if (home.filterIndex === 3 && a.practice !== "done") return false;
            if (home.filterIndex === 4 && !(a.wrong > 0)) return false;
            if (home.filterIndex === 5 && !(a.lastReviewed || a.intensive === "done")) return false;
            if (home.filterIndex === 6 && !(a.practice === "done" && !a.lastReviewed && a.intensive !== "done")) return false;
            if (home.filterIndex === 7 && !a.visited) return false;
            return true;
        });
        found.sort(function(a,b) {
            if (home.personalScope && home.sortIndex===0)
                return (b.visited || b.order)-(a.visited || a.order);
            if (home.sortIndex === 0) {
                if (a.visited !== b.visited) return b.visited - a.visited;
            }
            if (a.sourceGroup && b.sourceGroup && a.sourceGroup!==b.sourceGroup) {
                var sourceDayA=Math.floor(a.order/1000),sourceDayB=Math.floor(b.order/1000);
                return sourceDayA-sourceDayB || a.sourceGroup.localeCompare(b.sourceGroup);
            }
            return a.order - b.order;
        }); return found;
    }
    property string collectionTitle: query.trim() ? "搜索结果" : collection === "all" ? (materialScope==='practice' ? "可练习文章" : materialScope==='intensive' ? "仅精读正文" : "全部文章") : collection === "favorites" ? "我的收藏" : collection==='personal' ? "我的文章" : (personalFolders.find(function(f){return f.id===home.collection;}) || {}).name || (languageItems.filter(function(a) { return a.setId === home.collection })[0] || {}).setTitle || "材料库"
    function snapshot() {
        var index = articles.indexAt(1, articles.contentY + 1);
        var item = index >= 0 ? articles.itemAtIndex(index) : null;
        return {collection:collection, materialScope:materialScope, query:query, completion:completionScope, filter:filterIndex, sort:sortIndex,
            collapsed:collapsed, scroll:Math.max(0, articles.contentY - articles.originY),
            topArticle:index >= 0 && results[index] ? results[index].id : "",
            topOffset:item ? Math.max(0, articles.contentY-item.y) : 0};
    }
    function persist() {
        if (restoring) return;
        rememberDestination();
        var memory = Object.assign({}, languageMemory); memory[language] = snapshot(); languageMemory = memory;
        stateEdited(Object.assign({version:6, language:language, byLanguage:memory, destinations:destinationMemory, favorites:favoriteIds, records:readingRecords, completedSections:completedSections}, snapshot()));
    }
    function choose(id) {
        collection = id; query = ""; filterIndex = 0; completionScope = 'all'; materialScope = 'all';
        sortIndex = id === "personal" || id === "learning" ? 0 : 1;
        articles.positionViewAtBeginning(); persist(); directoryDrawer.close();
    }
    function changeLanguage(value) {
        if (language === value) return;
        rememberDestination(); persist(); restoring = true; language = value;
        var previous = route === "hub" ? (languageMemory[value] || {}) : destinationMemory[value+":"+route] || {collection:route === "favorites" ? "favorites" : "all"};
        applyState(previous);
        Qt.callLater(function() { restoreList(previous); home.restoring = false; home.persist(); });
    }
    function applyState(state) {
        materialScope=state.materialScope || (state.collection==='toefl-reviewed-selection' ? 'practice' : 'all');
        collection = ["recent", "learning"].indexOf(state.collection) >= 0 ? "all" : state.collection || "all"; query = state.query || "";
        if (collection==='toefl-reviewed-selection') collection='all';
        filterIndex = state.filter || 0; sortIndex = state.sort === undefined ? 1 : state.sort;
        completionScope = state.completion || (route === "library" && exercises.length && !filterIndex && !hasReviewedMaterials ? "unfinished" : "all");
        collapsed = state.collapsed || {};
    }
    function restoreList(state) {
        var index = state.topArticle ? results.findIndex(function(a) { return a.id === state.topArticle }) : -1;
        if (index < 0 && state.pageStart) index = Math.min(results.length-1, state.pageStart);
        if (index >= 0) {
            articles.positionViewAtIndex(index, ListView.Beginning);
            Qt.callLater(function() {
                var item = articles.itemAtIndex(index);
                if (item) articles.contentY = Math.max(articles.originY, Math.min(item.y + (state.topOffset || 0), articles.originY + Math.max(0,articles.contentHeight-articles.height)));
                home.persist();
            });
        } else articles.contentY = articles.originY + Math.max(0, Math.min(state.scroll || 0, Math.max(0, articles.contentHeight-articles.height)));
    }
    function restore() {
        restoring = true;
        language = savedState.language || "en"; languageMemory = savedState.byLanguage || {};
        favoriteIds = savedState.favorites || {}; readingRecords = savedState.records || {};
        completedSections = savedState.completedSections || {};
        destinationMemory = savedState.destinations || {};
        applyState(savedState.version >= 3 ? savedState : {});
        route = "hub";
        Qt.callLater(function() { restoreList(home.savedState); home.restoring = false; });
    }
    Component.onCompleted: restore()
    function openArticle(a, mode) {
        if (mode === "practice" && !reading.open(a.id)) return;
        reviewReturnId = "";
        selectedArticle = a; articleMode = mode; articleOpen = true;
        var changes = {visited:Date.now(), lastMode:mode};
        if (mode === "practice") changes.lastPracticeAt = Date.now();
        if (mode === "intensive") {
            changes.readParagraph = a.readParagraph || 1;
            changes.paragraphCount = a.body.split(/\n\s*\n/).length;
        }
        updateRecord(a.id, changes);
    }
    function practiceRatio(a) {
        var total = a.questionCount || 5;
        return a.pending ? Math.min(1, (a.answered || 0)/total) : a.practice === "done" ? 1 : a.practice === "progress" ? Math.min(1, (a.answered || 0) / total) : 0;
    }
    function snippet(a) {
        var n = query.trim().toLowerCase(), at = a.body.toLowerCase().indexOf(n);
        return n && at >= 0 ? (at > 28 ? "…" : "") + a.body.slice(Math.max(0, at-28), at+100) : a.body;
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 14; visible: !home.articleOpen && home.route !== "hub" && home.route !== "grammarFavorites" && home.route !== "studyFavorites"
        ReadingPageHeader { Layout.fillWidth: true; title: home.route === "favorites" ? "我的收藏" : "材料库"
            showBack: true; language: home.language; onBackRequested: home.goHub()
            onLanguageChosen: function(value) { home.changeLanguage(value) } }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            AppButton { objectName: "readingImportArticle"; text: "＋ 导入文章"; visible: home.route === "library"; onClicked: importDialog.open() }
            AppButton { objectName: "readingCreateFolder"; text: "＋ 新建文件夹"; visible: home.route === "library"; onClicked: { folderName.text=""; createFolderPopup.open(); } }
            Text { visible: home.materials.length > 0 && !home.compact; text: home.materials.some(function(a){return a.mock}) ? "设计预览 · 含模拟目录" : home.materials.some(function(a){return a.sourceKind==='toefl_personal_materials'}) ? "已核单选 · 精读正文" : "自编演示材料"; color: home.muted; font.pixelSize: 11 }
            Item { Layout.fillWidth: true; visible: !home.compact }
            TextField {
                id: search; objectName: "readingSearch"; Layout.fillWidth: home.compact
                Layout.preferredWidth: home.compact ? 200 : Math.min(390, home.width * 0.46)
                implicitHeight: 36; text: home.query; selectByMouse: true
                placeholderText: home.personalScope ? "搜索我的文章或文件夹" : "搜索标题、来源或原文"; color: home.ink; font.pixelSize: 12
                leftPadding: 12; rightPadding: 34
                background: Rectangle { radius: 8; color: settings.palette.surface; border.color: search.activeFocus ? home.accent : home.line }
                onTextEdited: { home.query = text; articles.positionViewAtBeginning(); home.persist() }
                ToolButton { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 32; text: "×"
                    objectName: "readingClearSearch"; visible: search.text.length > 0
                    onClicked: { home.query = ""; articles.positionViewAtBeginning(); home.persist() } }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 14
            Loader { id: desktopDirectory; visible: !home.compact && home.route === "library"; active: visible
                Layout.preferredWidth: 220; Layout.fillHeight: true; sourceComponent: directoryPanel }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 13; color: settings.palette.surface; border.color: home.line
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        AppButton { objectName: "readingOpenDirectory"; visible: home.compact && home.route === "library"; text: "☰ 来源"; onClicked: directoryDrawer.open() }
                        AppButton { objectName: "readingAllArticles"; visible: home.route === "library";
                            text: "全部文章"; primary: home.collection==='all' && home.materialScope==='all'; flat: !primary;
                            onClicked: home.choose('all') }
                        AppButton { objectName: "readingPersonalArticles"; visible: home.route === "library";
                            text: home.personalScope && home.collection!=="personal" ? "‹ 我的文章" : "我的文章 · "+home.personalArticleCount;
                            primary: home.personalScope; flat: !primary; onClicked: home.choose('personal') }
                        Text { objectName: "readingCollectionTitle";
                            text: !home.query.trim() && (home.collection==='all' || home.collection==='personal') ? "" : home.collectionTitle;
                            color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold
                            Layout.fillWidth: true; elide: Text.ElideRight }
                        Text { text: home.results.length + " 篇"; color: home.muted; font.pixelSize: 12 }
                    }
                    ColumnLayout { visible: home.collection==='personal'; Layout.fillWidth: true; spacing: 8
                        Text { text: "按文件夹浏览"; color: home.muted; font.pixelSize: 12 }
                        Flickable { id: personalFolderArea; objectName: "readingPersonalFolders"; Layout.fillWidth: true;
                            Layout.preferredHeight: Math.min(206,personalFolderFlow.height); clip: true
                            contentWidth: width; contentHeight: personalFolderFlow.height; boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            Flow { id: personalFolderFlow; width: personalFolderArea.width; height: childrenRect.height; spacing: 10
                                Repeater { model: home.personalFolders.filter(function(f) {return !home.query.trim() || f.name.toLowerCase().indexOf(home.query.trim().toLowerCase())>=0;})
                                    delegate: Button { required property var modelData; objectName: "readingFolderCard_"+modelData.id
                                        width: Math.max(158,Math.floor((personalFolderArea.width-24)/3)); height: 76; hoverEnabled: true
                                        background: Rectangle { radius: 9; color: parent.hovered ? settings.palette.selection : settings.palette.page; border.color: home.line }
                                        contentItem: ColumnLayout { spacing: 4
                                            Text { text: modelData.name; color: home.ink; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                                            Text { text: modelData.count+" 篇文章  ›"; color: home.muted; font.pixelSize: 11 }
                                        }
                                        leftPadding: 13; rightPadding: 13; topPadding: 9; bottomPadding: 9
                                        onClicked: home.choose(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Repeater { model: [{label:"全部", value:"all"}, {label:"未完成", value:"unfinished"}, {label:"已完成", value:"done"}]
                            AppButton { required property var modelData; visible: home.route === "library" && !home.personalScope && home.exercises.length > 0
                                objectName: "readingCompletion_" + modelData.value; text: modelData.label; implicitWidth: 62
                                primary: home.completionScope === modelData.value; flat: !primary; onClicked: home.chooseCompletion(modelData.value) }
                        }
                        Text { visible: home.personalScope; Layout.fillWidth: true; text: "搜索范围：我的文章"; color: home.muted; font.pixelSize: 11 }
                        AppCombo { id: statusFilter; objectName: "readingStatusFilter"; Layout.fillWidth: true; visible: !home.personalScope
                            model: ["全部状态", "未练习", "练习未完成", "练习已完成", "有错题", "有精读记录", "练习后未复习", "读过的文章"]
                            currentIndex: home.filterIndex
                            onActivated: { home.filterIndex = currentIndex; home.completionScope = "all"; articles.positionViewAtBeginning(); home.persist() } }
                        AppCombo { id: sorting; objectName: "readingSort"; Layout.preferredWidth: 124
                            model: ["最近打开", "来源顺序"]; currentIndex: home.sortIndex
                            onActivated: { home.sortIndex = currentIndex; articles.positionViewAtBeginning(); home.persist() } }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: home.line }
                    ListView {
                        id: articles; objectName: "readingArticleList"; Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; model: home.results; spacing: 0; boundsBehavior: Flickable.StopAtBounds
                        onMovementEnded: home.persist()
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; onPressedChanged: if (!pressed) home.persist() }
                        delegate: Item {
                            id: entry; required property var modelData; required property int index
                            objectName: "readingRow_" + modelData.id
                            width: articles.width; height: sectionHeight + (home.compact ? 118 : 108)
                            property bool newGroup: index === 0 || home.results[index-1].setId !== modelData.setId
                            property real sectionHeight: newGroup ? 30 : 0
                            Text { visible: entry.newGroup; y: 6; text: entry.modelData.group + "  /  " + entry.modelData.setTitle
                                color: home.muted; font.pixelSize: 11; width: parent.width - 14; elide: Text.ElideRight }
                            Rectangle {
                                x: 0; y: entry.sectionHeight; width: parent.width - 10; height: parent.height - entry.sectionHeight - 6
                                radius: 9; color: rowHover.hovered ? settings.palette.selection : "transparent"
                                HoverHandler { id: rowHover }
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 10; spacing: 7
                                    RowLayout { Layout.fillWidth: true; spacing: 8
                                        Text { text: (entry.modelData.number < 10 ? "0" : "") + entry.modelData.number; color: home.muted; font.pixelSize: 12 }
                                        Text { text: entry.modelData.title; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold
                                            Layout.fillWidth: true; elide: Text.ElideRight }
                                        Text { visible: !home.compact; text: entry.modelData.mock ? "模拟条目" : entry.modelData.sourceKind==='toefl_personal_materials' ? (entry.modelData.hasQuestions===false ? "精读正文" : "已核单选") : (entry.modelData.sourceKind==='personal_import' || entry.modelData.sourceKind==='user_paste') ? "个人文章" : "自编演示"; color: home.muted; font.pixelSize: 10 }
                                        AppButton { objectName: "readingFavorite_" + entry.modelData.id; text: home.isFavorite(entry.modelData) ? "★" : "☆"
                                            implicitWidth: 30; implicitHeight: 26; flat: true; onClicked: home.toggleFavorite(entry.modelData) }
                                    }
                                    Text { text: home.snippet(entry.modelData); color: home.muted; font.pixelSize: 12
                                        Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight }
                                    Item { Layout.fillWidth: true; implicitHeight: 36
                                        Column { anchors.left: parent.left; anchors.right: actions.left; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 5
                                            ReadingProgress { width: parent.width; visible: entry.modelData.hasQuestions !== false
                                                label: "练习"; value: home.practiceRatio(entry.modelData); tint: home.accent
                                                detail: entry.modelData.pending ? (entry.modelData.answered || 0)+"/"+entry.modelData.questionCount+" 题" : entry.modelData.practice === "done" ? (entry.modelData.score ? "已完成 · " + entry.modelData.score : "已完成") : entry.modelData.practice === "progress" ? (entry.modelData.answered || 0) + "/" + (entry.modelData.questionCount || 5) + " 题" : "未开始" }
                                            Text { text: home.reviewLabel(entry.modelData); visible: text.length > 0; color: home.muted; font.pixelSize: 10 }
                                        }
                                        Row { id: actions; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 7
                                        AppButton { objectName: "readingPractice_"+entry.modelData.id; visible: entry.modelData.hasQuestions !== false; text: entry.modelData.pending || entry.modelData.practice === "progress" ? "继续练习" : entry.modelData.practice === "done" ? "复盘" : "练习"
                                            flat: true; onClicked: home.openArticle(entry.modelData, "practice") }
                                        AppButton { objectName: "readingIntensive_" + entry.modelData.id; text: "精读"
                                            onClicked: home.openArticle(entry.modelData, "intensive") }
                                        AppButton { objectName: "readingManage_" + entry.modelData.id; visible: entry.modelData.sourceKind==='personal_import'; text: "管理"; flat: true
                                            onClicked: {home.managedArticle=entry.modelData; manageArticlePopup.open();} }
                                        }
                                    }
                                }
                            }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width - 10; height: 1; color: home.line }
                        }
                        Text { anchors.centerIn: parent; visible: home.results.length === 0
                            text: home.collection==='personal' ? (home.query.trim() ? "没有匹配的个人文章" : "还没有个人文章，点击上方“导入文章”添加") : home.collection.indexOf('personal-folder-')===0 ? "文件夹里还没有文章" : home.materials.length === 0 ? "还没有阅读材料" : home.collection === "favorites" ? "还没有收藏的文章" : "没有匹配的材料"; color: home.muted; font.pixelSize: 13 }
                    }

                }
            }
        }
    }
    ReadingHub {
        anchors.fill: parent; visible: !home.articleOpen && home.route === "hub"
        language: home.language; resumeArticle: home.resumeArticle; nextArticle: home.nextArticle; practiceComplete: home.practiceComplete
        favoriteItems: home.favoritePreview; materialItems: home.materialPreview
        favoriteCount: home.favoriteCount; materialCount: home.languageItems.length
        grammarFavoriteCount: reading.intensive.grammarFavorites.filter(function(a) { return a.language===home.language; }).length
        studyFavoriteCount: reading.intensive.saved.view.items.filter(function(a) {return a.language===home.language;}).length
        onLanguageChosen: function(value) { home.changeLanguage(value) }
        onOpenLibrary: home.openDestination("library")
        onOpenFavorites: home.openDestination("favorites")
        onOpenGrammarFavorites: home.openGrammarFavorites()
        onOpenStudyFavorites: home.openStudyFavorites()
        onOpenReview: home.openCompleted()
        onOpenArticle: function(article, mode) { home.openArticle(article, mode) }
    }
    ReadingGrammarFavorites {
        id: grammarFavorites; anchors.fill: parent; visible: !home.articleOpen && home.route==="grammarFavorites"
        language: home.language
        onLanguageChosen: function(value) { home.changeLanguage(value); }
        onBackRequested: {
            home.route=home.grammarReturnRoute;
            if (home.grammarReturnArticle) { home.selectedArticle=home.grammarReturnSelection; home.articleOpen=true; }
        }
        onSourceRequested: function(item) {
            var source=home.materials.find(function(a) { return a.id===item.article_id; });
            if (!source || !reading.intensive.favoriteSourceMatches(item.id,source.body)) {
                notice="来源文章已变化或不在资料库，收藏的原句和解释仍保留。";
                return;
            }
            notice="";home.openArticle(source,"intensive");
            Qt.callLater(function() { articlePage.focusFavorite(item); });
        }
    }
    ReadingStudyFavorites {
        id: studyFavorites;anchors.fill: parent;visible: !home.articleOpen && home.route==="studyFavorites"
        language: home.language
        onLanguageChosen: function(value) {home.changeLanguage(value);}
        onBackRequested: {
            home.route=home.studyReturnRoute;
            if (home.studyReturnArticle) {home.selectedArticle=home.studyReturnSelection;home.articleOpen=true;}
        }
        onSourceRequested: function(item) {
            var source=home.materials.find(function(a) {return a.id===item.article_id;});
            if (!source || !reading.intensive.studyFavoriteSourceMatches(item.id,source.body)) {
                notice="来源文章已变化或不在资料库，收藏内容仍保留。";return;
            }
            notice="";home.openArticle(source,"intensive");
            Qt.callLater(function() {articlePage.focusStudyFavorite(item);});
        }
    }
    Component {
        id: directoryPanel
        Rectangle {
            radius: 13; color: settings.palette.surface; border.color: home.line
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 10; spacing: 4
                Text { text: "分类与来源"; color: home.muted; font.pixelSize: 11; Layout.margins: 8 }
                AppButton { objectName: "readingMaterial_all";Layout.fillWidth: true;text: "全部文章 · "+home.languageItems.length+"篇";
                    primary: home.materialScope==='all' && home.collection==='all';flat: !primary;onClicked: {home.chooseMaterial('all');directoryDrawer.close();} }
                AppButton { objectName: "readingMaterial_practice";Layout.fillWidth: true;text: "可练习 · "+home.exercises.length+"篇";
                    primary: home.materialScope==='practice' && home.collection==='all';flat: !primary;onClicked: {home.chooseMaterial('practice');directoryDrawer.close();} }
                AppButton { objectName: "readingMaterial_intensive";Layout.fillWidth: true;text: "仅精读 · "+home.intensiveOnlyCount+"篇";
                    primary: home.materialScope==='intensive' && home.collection==='all';flat: !primary;onClicked: {home.chooseMaterial('intensive');directoryDrawer.close();} }
                Rectangle { Layout.fillWidth: true; Layout.topMargin: 8; Layout.bottomMargin: 8; height: 1; color: home.line }
                ListView {
                    id: readingDirectory; objectName: "readingDirectory"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: home.directory; boundsBehavior: Flickable.StopAtBounds
                    function toggleGroup(group, visibleY) {
                        var folds=Object.assign({},home.collapsed); folds[group]=!folds[group]; home.collapsed=folds;
                        Qt.callLater(function() {
                            var index=home.directory.findIndex(function(row){return row.kind==='group' && row.id===group;});
                            if (index>=0) {
                                readingDirectory.positionViewAtIndex(index,ListView.Beginning);
                                readingDirectory.forceLayout();
                                var target=readingDirectory.itemAtIndex(index);
                                if (target) readingDirectory.contentY=Math.max(readingDirectory.originY,Math.min(
                                    target.y-visibleY,readingDirectory.originY+Math.max(0,readingDirectory.contentHeight-readingDirectory.height)));
                            }
                            home.persist();
                        });
                    }
                    Component.onCompleted: {
                        var selected = home.directory.findIndex(function(d) { return d.id === home.collection });
                        if (selected >= 0) positionViewAtIndex(selected, ListView.Contain);
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Button {
                        id: folder
                        required property var modelData; width: ListView.view.width - 8; height: modelData.kind === "group" ? 38 : 52
                        objectName: "readingDirectory_" + modelData.id
                        hoverEnabled: true; leftPadding: modelData.kind === "group" ? 8 : 16; rightPadding: 7
                        background: Rectangle { radius: 7; color: home.collection === folder.modelData.id ? settings.palette.selection : folder.hovered ? settings.palette.page : "transparent" }
                        contentItem: ColumnLayout { spacing: 3
                            RowLayout { Layout.fillWidth: true; spacing: 5
                                Text { text: folder.modelData.kind === "group" ? (home.collapsed[folder.modelData.id] ? "›  " : "⌄  ") + folder.modelData.label : folder.modelData.label
                                    color: folder.modelData.manuallyComplete ? home.accent : home.ink; font.pixelSize: 12; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
                                AppButton { visible: folder.modelData.kind==='set' && folder.modelData.id.indexOf('personal-folder-')===0 && folder.modelData.label!=='未分类' && folder.modelData.articleCount===0
                                    text: "×"; flat: true; implicitWidth: 24; implicitHeight: 24
                                    onClicked: {home.managedFolder=folder.modelData;deleteFolderPopup.open();} }
                                Text { visible: folder.modelData.kind === "group" && folder.modelData.manuallyComplete === true
                                    text: "✓"; color: home.accent; font.pixelSize: 13 }
                                CheckBox {
                                    id: sectionMark
                                    objectName: "readingSectionComplete_" + folder.modelData.id
                                    visible: folder.modelData.kind === "set"
                                    Layout.preferredWidth: 28; Layout.preferredHeight: 28; padding: 0
                                    checked: folder.modelData.manuallyComplete === true
                                    hoverEnabled: true
                                    Accessible.name: (checked ? "取消完成：" : "标记完成：") + folder.modelData.label
                                    indicator: Rectangle {
                                        x: (sectionMark.width-width)/2; y: (sectionMark.height-height)/2
                                        implicitWidth: 18; implicitHeight: 18; radius: 4
                                        color: sectionMark.checked ? home.accent : "transparent"
                                        border.width: sectionMark.activeFocus ? 2 : 1
                                        border.color: sectionMark.checked || sectionMark.hovered || sectionMark.activeFocus ? home.accent : home.muted
                                        Text { anchors.centerIn: parent; text: "✓"; visible: sectionMark.checked; color: "white"; font.pixelSize: 13; font.weight: Font.DemiBold }
                                    }
                                    contentItem: Item {}
                                    ToolTip.visible: hovered
                                    ToolTip.text: checked ? "已完成，点击取消" : "点击标记本节已完成"
                                    onClicked: home.toggleSectionComplete(folder.modelData.id)
                                }
                            }
                            Text { visible: folder.modelData.kind === "set" && (folder.modelData.count > 0 || folder.modelData.sourceGroup)
                                text: folder.modelData.sourceGroup ? folder.modelData.articleCount+"篇 · "+folder.modelData.practiceCount+"可练习 · "+folder.modelData.intensiveCount+"精读" : folder.modelData.done + "/" + folder.modelData.count + " 篇已做"; color: home.muted; font.pixelSize: 9 }
                        }
                        onClicked: {
                            if (modelData.kind === "group") {
                                readingDirectory.toggleGroup(modelData.id,folder.y-readingDirectory.contentY);
                            } else home.choose(modelData.id);
                        }
                    }
                }
            }
        }
    }
    Popup { id: directoryDrawer; objectName: "readingDirectoryPopup"; width: Math.min(280, home.width * 0.8); height: home.height
        parent: Overlay.overlay
        onAboutToShow: { var origin = home.mapToItem(parent, 0, 0); x = origin.x; y = origin.y; }
        modal: true; padding: 0
        Loader { anchors.fill: parent; sourceComponent: directoryPanel }
    }
    Popup { id: createFolderPopup; objectName: "readingCreateFolderPopup"; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; focus: true
        width: Math.min(380,parent.width-32); padding: 20; closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 12; color: settings.palette.surface; border.color: home.line }
        contentItem: ColumnLayout { spacing: 14
            Text { text: "新建"+(home.language==='ja' ? "日语" : "英语")+"文件夹"; color: home.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
            TextField { id: folderName; objectName: "readingNewFolderName"; Layout.fillWidth: true; implicitHeight: 40
                leftPadding: 12; rightPadding: 12; placeholderText: "文件夹名称"; maximumLength: 100; selectByMouse: true
                color: home.ink; placeholderTextColor: home.muted
                background: Rectangle { radius: 8; color: settings.palette.surface
                    border.width: folderName.activeFocus ? 2 : 1
                    border.color: folderName.activeFocus ? home.accent : home.line }
                onAccepted: createFolderButton.clicked() }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                AppButton { text: "取消"; flat: true; onClicked: createFolderPopup.close() }
                AppButton { id: createFolderButton; objectName: "readingNewFolderSave"; text: "创建"; primary: true; enabled: folderName.text.trim().length>0
                    onClicked: { if (reading.importer.createFolder(home.language,folderName.text)) {home.materialScope='all';home.completionScope='all';home.collection=reading.importer.folders.find(function(f){return f.language===home.language && f.name===folderName.text.trim()}).id;home.persist();createFolderPopup.close();} else {home.practiceError=reading.importer.view.error;practiceNotice.open();} } }
            }
        }
    }
    Popup { id: manageArticlePopup; objectName: "readingManageArticlePopup"; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; focus: true
        width: Math.min(420,parent.width-32); padding: 20; closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 12; color: settings.palette.surface; border.color: home.line }
        contentItem: ColumnLayout { spacing: 14
            Text { text: home.managedArticle.title || "个人文章"; Layout.fillWidth: true; elide: Text.ElideRight; color: home.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
            Text { text: "移动到文件夹"; color: home.muted; font.pixelSize: 12 }
            AppCombo { id: moveTarget; objectName: "readingMoveTarget"; Layout.fillWidth: true
                model: reading.importer.folders.filter(function(f) {return f.language===home.managedArticle.language;}).map(function(f) {return f.name;})
                Component.onCompleted: currentIndex=Math.max(0,model.indexOf(home.managedArticle.setTitle)) }
            RowLayout { Layout.fillWidth: true; spacing: 8
                AppButton { objectName: "readingDeleteArticle"; text: "删除文章"; flat: true; onClicked: {manageArticlePopup.close();deleteArticlePopup.open();} }
                Item { Layout.fillWidth: true }
                AppButton { text: "取消"; flat: true; onClicked: manageArticlePopup.close() }
                AppButton { objectName: "readingMoveArticle"; text: "移动"; primary: true
                    onClicked: { if (reading.importer.moveArticle(home.managedArticle.id,moveTarget.currentText)) {home.collection=reading.importer.folders.find(function(f){return f.language===home.managedArticle.language && f.name===moveTarget.currentText}).id;home.persist();manageArticlePopup.close();} else {home.practiceError=reading.importer.view.error;practiceNotice.open();} } }
            }
        }
        onOpened: moveTarget.currentIndex=Math.max(0,moveTarget.model.indexOf(home.managedArticle.setTitle))
    }
    Popup { id: deleteArticlePopup; objectName: "readingDeleteArticlePopup"; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; focus: true
        width: Math.min(420,parent.width-32); padding: 20; closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 12; color: settings.palette.surface; border.color: home.line }
        contentItem: ColumnLayout { spacing: 16
            Text { text: "删除「"+(home.managedArticle.title || "文章")+"」？"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: home.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
            Text { text: "会从个人文章库移除这篇文章；原始 TXT / Markdown 文件不会删除。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: home.muted; font.pixelSize: 12 }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                AppButton { text: "取消"; flat: true; onClicked: deleteArticlePopup.close() }
                AppButton { objectName: "readingConfirmDeleteArticle"; text: "删除"; primary: true
                    onClicked: { if (reading.importer.deleteArticle(home.managedArticle.id)) {
                        var records=Object.assign({},home.readingRecords), favorites=Object.assign({},home.favoriteIds);
                        delete records[home.managedArticle.id]; delete favorites[home.managedArticle.id];
                        home.readingRecords=records; home.favoriteIds=favorites;
                        if (home.collection===home.managedArticle.setId && !home.languageItems.some(function(a){return a.setId===home.collection;})) home.collection='all';
                        home.persist();deleteArticlePopup.close();
                    } else {home.practiceError=reading.importer.view.error;practiceNotice.open();} } }
            }
        }
    }
    Popup { id: deleteFolderPopup; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; focus: true
        width: Math.min(400,parent.width-32); padding: 20; closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 12; color: settings.palette.surface; border.color: home.line }
        contentItem: ColumnLayout { spacing: 16
            Text { text: "删除空文件夹「"+(home.managedFolder.label || "")+"」？"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: home.ink; font.pixelSize: 16 }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                AppButton { text: "取消"; flat: true; onClicked: deleteFolderPopup.close() }
                AppButton { text: "删除"; primary: true; onClicked: {if (reading.importer.deleteFolder(home.language,home.managedFolder.label)) {if (home.collection===home.managedFolder.id) home.collection='all';home.persist();deleteFolderPopup.close();} else {home.practiceError=reading.importer.view.error;practiceNotice.open();}} }
            }
        }
    }
    ReadingArticlePage {
        id: articlePage; anchors.fill: parent; visible: home.articleOpen && home.articleMode === "intensive"
        article: home.selectedArticle; mode: home.articleMode
        favorite: home.isFavorite(home.selectedArticle)
        record: home.readingRecords[home.selectedArticle.id] || {}
        onFavoriteRequested: home.toggleFavorite(home.selectedArticle)
        onGrammarFavoritesRequested: home.openGrammarFavorites()
        onStudyFavoritesRequested: home.openStudyFavorites()
        onBookmarkEdited: function(changes) { home.updateRecord(home.selectedArticle.id, changes) }
        onBackRequested: {
            if (home.reviewReturnId) {
                reading.reviewAttempt(home.reviewReturnId); reading.chooseQuestion(home.reviewReturnIndex);
                home.reviewReturnId = ""; home.articleMode = "practice";
            } else home.articleOpen = false;
        }
    }
    ReadingPracticeView {
        id: practicePage; anchors.fill: parent; visible: home.articleOpen && home.articleMode === "practice"
        onBackRequested: home.leavePractice()
        onIntensiveRequested: {
            home.reviewReturnId = reading.view.id; home.reviewReturnIndex = reading.view.index;
            home.selectedArticle = Object.assign({},home.selectedArticle,{body:reading.view.body,title:reading.view.title,language:reading.view.language});
            home.updateRecord(home.selectedArticle.id,{position:Math.max(0,practicePage.passagePosition)});
            practicePage.savePosition(); reading.leave(); home.articleMode = "intensive";
        }
        onNextRequested: { home.leavePractice(); if (home.nextArticle.id) home.openArticle(home.nextArticle,"practice"); else home.goHub(); }
        hasNext: !!home.nextArticle.id
    }
    Connections { target: reading
        function onError(message) { home.practiceError = message; practiceNotice.open(); }
    }
    Popup { id: practiceNotice; parent: Overlay.overlay; anchors.centerIn: parent; modal: true; width: Math.min(440,parent.width-48); padding: 24
        background: Rectangle { radius: 12; color: settings.palette.surface }
        contentItem: ColumnLayout { spacing: 16
            Text { text: home.practiceError; Layout.fillWidth: true; wrapMode: Text.Wrap; color: home.ink; font.pixelSize: 14 }
            AppButton { text: "知道了"; Layout.alignment: Qt.AlignRight; onClicked: practiceNotice.close() }
        }
    }
    ReadingImportDialog {
        id: importDialog
        libraryLanguage: home.language
        onArticleImported: function(articleId, openNow) {
            var article = reading.catalogue.find(function(a) { return a.id === articleId });
            if (!article) return;
            home.changeLanguage(article.language); home.openDestination("library");
            Qt.callLater(function() {
                home.collection = article.setId; home.materialScope = "all"; home.completionScope = "all";
                home.query = ""; home.filterIndex = 0; home.persist();
                if (openNow) home.openArticle(article, "intensive");
            });
        }
    }
}
