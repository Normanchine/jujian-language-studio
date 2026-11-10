import QtQuick

// Quiet, static paper marks. Painted only on resize or a theme change.
Canvas {
    id: paper
    property string themeKey: settings.values.theme
    property color ink: settings.palette.accent
    property string area: "hero"
    antialiasing: true
    opacity: 0.14
    onThemeKeyChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if (visible) requestPaint()

    function leaf(c, x, y, size, angle) {
        c.save(); c.translate(x, y); c.rotate(angle)
        c.beginPath(); c.moveTo(0, size)
        c.quadraticCurveTo(-size, 0, 0, -size)
        c.quadraticCurveTo(size, 0, 0, size)
        c.stroke(); c.beginPath(); c.moveTo(0, size); c.lineTo(0, -size); c.stroke()
        c.restore()
    }
    function dot(c, x, y, radius) {
        c.beginPath(); c.arc(x, y, radius, 0, Math.PI * 2); c.fill()
    }
    function motif(c) {
        var i, a
        switch (themeKey) {
        case "rose": // Five notched petals, like a small printed cherry blossom.
            for (i = 0; i < 5; ++i) {
                c.save(); c.rotate(i * Math.PI * 2 / 5)
                c.beginPath(); c.moveTo(0, 2)
                c.bezierCurveTo(-14, -4, -12, -16, -4, -19)
                c.lineTo(0, -16); c.lineTo(4, -19)
                c.bezierCurveTo(12, -16, 14, -4, 0, 2); c.stroke(); c.restore()
            }
            dot(c, 0, 0, 1.6)
            break
        case "coral": // A small fan-shaped shell.
            c.beginPath(); c.moveTo(0, 14)
            c.bezierCurveTo(-31, 3, -22, -21, 0, -19)
            c.bezierCurveTo(22, -21, 31, 3, 0, 14); c.stroke()
            for (i = -2; i <= 2; ++i) {
                c.beginPath(); c.moveTo(0, 14); c.quadraticCurveTo(i * 10, -1, i * 8, -16 + Math.abs(i) * 3); c.stroke()
            }
            break
        case "mint":
            leaf(c, -5, 3, 18, -0.5); leaf(c, 12, -9, 10, 0.65)
            break
        case "olive":
            c.beginPath(); c.moveTo(-17, 20); c.quadraticCurveTo(1, 2, 14, -23); c.stroke()
            for (i = 0; i < 3; ++i) {
                leaf(c, -12 + i * 9, 9 - i * 12, 7, -0.9)
                leaf(c, 1 + i * 7, 7 - i * 12, 7, 0.9)
            }
            break
        case "indigo":
            c.beginPath(); c.moveTo(-20, 8); c.lineTo(-6, -15); c.lineTo(8, 1); c.lineTo(23, -12); c.stroke()
            dot(c, -20, 8, 2); dot(c, -6, -15, 2.6); dot(c, 8, 1, 1.8); dot(c, 23, -12, 2)
            c.beginPath(); c.moveTo(18, 13); c.lineTo(18, 23); c.moveTo(13, 18); c.lineTo(23, 18); c.stroke()
            break
        case "silver":
            for (i = 0; i < 3; ++i) {
                c.beginPath(); c.moveTo(-15 + i * 14, -14 + i * 5); c.lineTo(-22 + i * 14, 5 + i * 5); c.stroke()
                dot(c, -9 + i * 14, 14 - i * 6, 1.4)
            }
            break
        case "blue":
            c.beginPath(); c.moveTo(-22, 12)
            c.bezierCurveTo(-37, 7, -29, -10, -17, -7)
            c.bezierCurveTo(-15, -26, 12, -26, 15, -7)
            c.bezierCurveTo(33, -13, 38, 10, 22, 12)
            c.closePath(); c.stroke()
            break
        case "violet":
            c.beginPath(); c.moveTo(0, 25); c.lineTo(0, -23); c.stroke()
            for (i = 0; i < 4; ++i) {
                leaf(c, -5, 8 - i * 8, 5, -0.7)
                leaf(c, 5, 5 - i * 8, 5, 0.7)
            }
            break
        case "warm":
            c.save(); c.rotate(-0.45); c.scale(0.68, 1)
            c.beginPath(); c.arc(0, 0, 23, 0, Math.PI * 2); c.stroke()
            c.beginPath(); c.moveTo(0, -21); c.bezierCurveTo(-15, -4, 15, 4, 0, 21); c.stroke(); c.restore()
            break
        case "teal":
            for (i = 0; i < 3; ++i) {
                c.beginPath(); c.moveTo(-25, -11 + i * 12)
                c.bezierCurveTo(-10, -25 + i * 12, 7, 5 + i * 12, 25, -11 + i * 12); c.stroke()
            }
            break
        case "gold":
            c.beginPath(); c.moveTo(0, 20); c.lineTo(-23, -10)
            c.quadraticCurveTo(-8, -27, 0, -17); c.quadraticCurveTo(8, -27, 23, -10)
            c.closePath(); c.stroke()
            for (i = -1; i <= 1; ++i) { c.beginPath(); c.moveTo(0, 20); c.lineTo(i * 12, -16); c.stroke() }
            c.beginPath(); c.moveTo(0, 20); c.lineTo(0, 28); c.stroke()
            break
        case "slate":
            c.beginPath(); c.moveTo(-28, 15); c.lineTo(-6, -19); c.lineTo(17, 15)
            c.moveTo(4, -3); c.lineTo(16, -15); c.lineTo(34, 15)
            c.moveTo(-12, -9); c.lineTo(-5, -4); c.lineTo(1, -9); c.stroke()
            break
        case "classic":
            c.beginPath(); c.moveTo(0, -14); c.quadraticCurveTo(-13, -22, -27, -16)
            c.lineTo(-27, 17); c.quadraticCurveTo(-13, 10, 0, 18)
            c.quadraticCurveTo(13, 10, 27, 17); c.lineTo(27, -16)
            c.quadraticCurveTo(13, -22, 0, -14); c.lineTo(0, 18); c.stroke()
            break
        default: // Sage: a fine fern, distinct from mint's broad leaves.
            c.beginPath(); c.moveTo(0, 24); c.quadraticCurveTo(-3, 0, 4, -26); c.stroke()
            for (i = 0; i < 5; ++i) {
                a = 17 - i * 8
                c.beginPath(); c.moveTo(0, a); c.quadraticCurveTo(-14, a - 2, -15 + i * 2, a - 12)
                c.moveTo(0, a); c.quadraticCurveTo(14, a - 2, 15 - i * 2, a - 12); c.stroke()
            }
        }
    }
    onPaint: {
        var c = getContext("2d")
        c.reset(); c.clearRect(0, 0, width, height)
        c.strokeStyle = ink; c.fillStyle = ink; c.lineWidth = 1.25
        c.lineCap = "round"; c.lineJoin = "round"
        var marks = area === "hero" ? [[width - 36, height - 39, 0.68, -0.2], [width - 102, height - 16, 0.33, 0.5]]
                  : area === "writing" ? [[width - 43, height - 48, 0.85, 0.18], [width - 100, height - 25, 0.38, -0.6], [width - 22, height - 109, 0.28, 0.5]]
                  : area === "swatch" ? [[width - 18, height - 14, 0.26, -0.2]]
                  : area === "video" ? [[width - 30, height - 36, 0.5, -0.3], [29, height - 18, 0.28, 0.7]]
                  : [[width * 0.66, height - 24, 0.46, 0.3], [width - 26, height - 56, 0.28, -0.6]]
        for (var i = 0; i < marks.length; ++i) {
            var m = marks[i]
            c.save(); c.translate(m[0], m[1]); c.scale(m[2], m[2]); c.rotate(m[3])
            if (themeKey === "rose" && m[2] < 0.4) {
                c.beginPath(); c.moveTo(0, 13)
                c.bezierCurveTo(-18, -2, -10, -18, -3, -18)
                c.lineTo(0, -14); c.lineTo(4, -18)
                c.bezierCurveTo(15, -14, 14, 0, 0, 13); c.stroke()
            } else motif(c)
            c.restore()
        }
    }
}
