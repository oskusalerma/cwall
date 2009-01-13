#!/usr/bin/python
# coding: Latin-1

import sys, random, math
from PyQt4 import QtGui, QtCore

class Color:
    def __init__(self, name, r, g, b):
        self.name = name
        self.r = r
        self.g = g
        self.b = b

        self.brush = QtGui.QBrush(QtGui.QColor(r, g, b))

COLORS = [
    Color("Blue", 0, 0, 255),
    Color("Light blue", 128, 128, 255),
    Color("Green", 0, 255, 0),
    Color("Red", 255, 0, 0),
    Color("Yellow", 255, 255, 0),
    Color("Brown", 150, 75, 0),
    Color("White", 255, 255, 255),
    Color("Black", 0, 0, 0)
]

_currentColor = -1

def getNextColor():
    global _currentColor

    _currentColor = (_currentColor + 1) % len(COLORS)
    return COLORS[_currentColor]

class Point:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def __str__(self):
        return "%.3f,%.3f" % (self.x, self.y)

    def __add__(self, pt):
        return Point(self.x + pt.x, self.y + pt.y)

    def __sub__(self, pt):
        return Point(self.x - pt.x, self.y - pt.y)

    def __mul__(self, pt):
        if not isinstance(pt, (float, int, long)):
            return NotImplemented

        return Point(self.x * pt, self.y * pt)

    # returns distance to another point
    def distanceTo(self, pt):
        return math.sqrt((self.x - pt.x)**2 + (self.y - pt.y)**2)

# return Point on line segment (A, B) that's closest to P as first element
# of tuple, and a value between [0,1] as a second element that tells how
# far along the line segment from A to B the closest point is.
#
# references:
# http://local.wasp.uwa.edu.au/~pbourke/geometry/pointline/
# http://www.gamedev.net/community/forums/topic.asp?topic_id=444154&whichpage=1&#2941160
def closestPoint(A, B, P):
    AP = P - A
    AB = B - A

    ab2 = AB.x * AB.x + AB.y * AB.y
    ap_ab = AP.x * AB.x + AP.y * AB.y

    # FIXME: check ab2 != 0.0
    t = ap_ab / ab2

    if t > 1.0:
        t = 1.0
    elif t < 0.0:
        t = 0.0

    closest = A + AB * t

    return (closest, t)

class Wall:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

class Marker:
    SIZE = 18

    # marker shapes
    BOX, RECTANGLE, CROSS = range(3)

    def __init__(self):
        self.shape = random.randint(0, Marker.CROSS)

        self.pen = QtGui.QPen(QtCore.Qt.black)
        self.pen.setWidthF(1.0)

    def size(self):
        return Marker.SIZE

    def paint(self, pnt, color, x):
        pnt.setPen(self.pen)
        pnt.setBrush(color.brush)

        #pnt.drawLine(x, -Marker.SIZE / 2.0, x, Marker.SIZE / 2.0)
        #pnt.drawLine(x, 0, x, Marker.SIZE)

        size = Marker.SIZE

        if self.shape == Marker.BOX:
            pnt.drawRect(x, -size / 2, Marker.SIZE, size)

        elif self.shape == Marker.RECTANGLE:
            size /= 3.0
            pnt.drawRect(x, -size / 2, Marker.SIZE, size)
        elif self.shape == Marker.CROSS:
            # FIXME: implement
            size /= 3.0
            pnt.drawRect(x, -size / 2, Marker.SIZE, size)
            pnt.drawRect(x + Marker.SIZE / 2 - size / 2,
                         -Marker.SIZE / 2,
                         size, Marker.SIZE)

class Route:
    def __init__(self):
        self.level = "5.10a"
        self.color = getNextColor()
        self.marker = Marker()

        self.x = 0
        self.y = 0

        self.t = 0
        self.angle = 0.0
        self.wall = None

        self.font = QtGui.QFont("Helvetica", 18)
        self.fontMetrics = QtGui.QFontMetrics(self.font)

        self.offset = 10
        self.flipSide = False

    def attachTo(self, wall, closestPt, t):
        self.wall = wall
        self.x = closestPt.x
        self.y = closestPt.y 
        self.t = t

        AB = self.wall.p2 - self.wall.p1
        AB.y = -AB.y

        if AB.x != 0:
            self.angle = math.atan(AB.y / AB.x) * 180.0 / math.pi
        else:
            self.angle = 90.0

        #print AB, self.angle

        if self.angle < 0:
            self.angle += 180

        self.angle = 90 - self.angle

    def paint(self, pnt):
        pnt.save()
        pnt.setFont(self.font)
        pnt.translate(self.x, self.y)
        pnt.rotate(self.angle)

        #pnt.drawLine(0, 0, self.offset, 0)

        s = "%s %s" % (self.level, self.color.name)
        textRect = pnt.boundingRect(0, 0, 0, 0, 0, s)

        if self.flipSide:
            x = -textRect.width() - self.offset * 1.5- self.marker.size()
        else:
            x = self.offset

        #print textRect

        #pnt.drawText(x, textRect.height() + self.fontMetrics.descent(), s)
        pnt.drawText(x, -self.fontMetrics.descent() + textRect.height() / 2.0, s)
        x += textRect.width() + self.offset / 2.0

#         pnt.drawText(10, 0, 200, 200, QtCore.Qt.AlignVCenter,
#                      "%s %s" % (self.level, self.color))

        self.marker.paint(pnt, self.color, x)
        pnt.restore()

class CWall(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        self.setGeometry(400, 50, 800, 700)
        self.setWindowTitle("Climbing walls")
        self.setMouseTracking(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.BlankCursor))

        self.mousePos = Point(-1, -1)
        self.route = Route()
        self.routes = []

        self.points = [
            Point(600, 550),
            Point(620, 400),
            Point(750, 200),
            Point(740, 100),
            Point(150, 90),
            Point(100, 80),
            Point(50, 350),
            Point(125, 410),
            Point(35, 440),
            Point(30, 550)
            ]

        self.walls = []

        for i in xrange(1, len(self.points)):
            self.walls.append(Wall(self.points[i - 1], self.points[i]))

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_F:
            self.route.flipSide = not self.route.flipSide
            self.update()
        elif key == QtCore.Qt.Key_A:
            self.routes.append(self.route)
            self.route = Route()
            self.update()

    def mouseMoveEvent(self, event):
        self.mousePos = Point(event.x(), event.y())
        self.update()

    def paintEvent(self, event):
        paint = QtGui.QPainter()
        paint.begin(self)

        #size = self.size()

        paint.setRenderHint(QtGui.QPainter.Antialiasing)
        paint.setRenderHint(QtGui.QPainter.TextAntialiasing)

        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidthF(2.0)
        paint.setPen(pen)

        for wall in self.walls:
            paint.drawLine(wall.p1.x, wall.p1.y, wall.p2.x, wall.p2.y)

        pen = QtGui.QPen(QtCore.Qt.red)
        pen.setWidthF(2.0)
        paint.setPen(pen)

        paint.drawEllipse(self.mousePos.x - 2.5, self.mousePos.y - 2.5, 5, 5)

        pen = QtGui.QPen(QtCore.Qt.blue)
        pen.setWidthF(2.0)
        paint.setPen(pen)

        for route in self.routes:
            route.paint(paint)

        closestDistance = 99999999.9
        closestPt = None
        closestT = None
        closestWall = None

        for wall in self.walls:
            closest, t = closestPoint(wall.p1, wall.p2, self.mousePos)

            dst = closest.distanceTo(self.mousePos)

            if dst < closestDistance:
                closestDistance = dst
                closestPt = closest
                closestT = t
                closestWall = wall

        if closestPt:
            #paint.drawEllipse(closestPt.x - 2.5, closestPt.y - 2.5, 5, 5)

            self.route.attachTo(closestWall, closestPt, closestT)
            self.route.paint(paint)

        paint.end()

app = QtGui.QApplication(sys.argv)
dt = CWall()
dt.show()
app.exec_()
