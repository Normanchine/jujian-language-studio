import QtQuick

Canvas {
    id: glyph
    property string kind: "home"
    property bool active: false
    width: 24
    height: 24
    onKindChanged: requestPaint()
    onActiveChanged: requestPaint()
    onPaint: {
        var p = getContext("2d")
        p.clearRect(0, 0, width, height)
        p.save()
        p.scale(width / 24, height / 24)
        p.strokeStyle = active ? "#B54456" : "#607069"
        p.lineWidth = 1.8
        p.lineCap = "round"
        p.lineJoin = "round"
        function path(points) {
            p.beginPath()
            p.moveTo(points[0], points[1])
            for (var i = 2; i < points.length; i += 2) p.lineTo(points[i], points[i + 1])
            p.stroke()
        }
        if (kind === "home") {
            path([3.5, 10.5, 12, 4, 20.5, 10.5])
            path([5.5, 10, 5.5, 20, 18.5, 20, 18.5, 10])
            path([10, 20, 10, 14.5, 14, 14.5, 14, 20])
        } else if (kind === "listen") {
            p.beginPath(); p.arc(12, 13, 8, Math.PI, Math.PI * 2); p.stroke()
            path([4, 13, 4, 18.5, 6, 20, 8, 20, 8, 14.5, 4, 14.5])
            path([20, 13, 20, 18.5, 18, 20, 16, 20, 16, 14.5, 20, 14.5])
        } else if (kind === "writing") {
            path([5, 18.5, 5.8, 14.8, 16.7, 4, 20, 7.3, 9.1, 18.2, 5, 18.5])
            path([14.8, 6, 18, 9.2])
            path([4.5, 21, 19.5, 21])
        } else if (kind === "library") {
            p.strokeRect(4.5, 4.5, 15, 4)
            p.strokeRect(4.5, 10, 15, 4)
            p.strokeRect(4.5, 15.5, 15, 4)
        } else if (kind === "notes") {
            path([6, 3.5, 15, 3.5, 19, 7.5, 19, 20.5, 6, 20.5, 6, 3.5])
            path([15, 3.5, 15, 7.5, 19, 7.5])
            path([9, 11.5, 16, 11.5])
            path([9, 15.5, 16, 15.5])
        } else if (kind === "settings") {
            p.beginPath(); p.arc(12, 12, 5.5, 0, Math.PI * 2); p.stroke()
            p.beginPath(); p.arc(12, 12, 1.8, 0, Math.PI * 2); p.stroke()
            for (var n = 0; n < 8; n++) {
                var a = n * Math.PI / 4
                path([12 + Math.cos(a) * 7.5, 12 + Math.sin(a) * 7.5,
                      12 + Math.cos(a) * 9.2, 12 + Math.sin(a) * 9.2])
            }
        }
        p.restore()
    }
}
