.pragma library

// Anchor within the source paragraph, so expanded translations and notes in
// earlier paragraphs do not change what is restored on the next visit.
function capture(view, paragraphs) {
    var index = view.indexAt(10, view.contentY + 1);
    if (index < 0) {
        var nearest = -Infinity;
        for (var i = 0; i < view.count; i++) {
            var candidate = view.itemAtIndex(i);
            if (candidate && candidate.y <= view.contentY + 1 && candidate.y > nearest) {
                index = i; nearest = candidate.y;
            }
        }
    }
    var block = index >= 0 ? view.itemAtIndex(index) : null;
    var anchor = null;
    if (block) {
        var height = Math.max(1, block.bookmarkHeight);
        var offset = Math.max(0, Math.min(view.contentY - block.y, height));
        anchor = {version: 1, paragraph: index, offset: offset, textHeight: height,
                  source: String(paragraphs[index] || "").slice(0, 64)};
    }
    return {position: Math.max(0, view.contentY-view.originY),
            readParagraph: Math.max(0, index)+1, paragraphCount: paragraphs.length,
            readingAnchor: anchor, visited: Date.now()};
}

function restore(view, record, paragraphs, current, finished) {
    paragraphs = paragraphs || [];
    var anchor = record.readingAnchor;
    var anchored = anchor && anchor.version === 1 && anchor.paragraph >= 0
        && anchor.paragraph < paragraphs.length
        && anchor.source === String(paragraphs[anchor.paragraph] || "").slice(0, 64);
    Qt.callLater(function() {
        if (!current()) return;
        view.forceLayout();
        if (anchored) view.positionViewAtIndex(anchor.paragraph, 1); // ListView.Beginning
        Qt.callLater(function() {
            if (!current()) return;
            view.forceLayout();
            var block = anchored ? view.itemAtIndex(anchor.paragraph) : null;
            if (block) {
                var height = Math.max(1, block.bookmarkHeight);
                var offset = Math.abs(height-anchor.textHeight) < 2 ? anchor.offset
                    : anchor.offset / Math.max(1, anchor.textHeight) * height;
                view.contentY = block.y + Math.max(0, Math.min(offset, height));
            } else {
                view.contentY = view.originY + Math.max(0, record.position || 0);
            }
            view.returnToBounds();
            finished();
        });
    });
}
