#!/usr/bin/python
# coding: Latin-1

import util

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
    Color("Pink", 254, 36, 154),
    Color("Orange", 255, 127, 0),
    Color("Brown", 150, 75, 0),
    Color("White", 255, 255, 255),
    Color("Black", 0, 0, 0)
]

_currentColor = -1

# misc globally needed stuff
class Main:
    # modes
    WALL_MOVE, WALL_ADD, WALL_DELETE, ROUTE_ADD, ROUTE_EDIT = range(5)

    modeNames = {
        WALL_MOVE : "Move walls",
        WALL_ADD : "Add walls",
        WALL_DELETE : "Delete walls",
        ROUTE_ADD : "Add routes",
        ROUTE_EDIT : "Edit routes"
        }

    def __init__(self):
        self.modeCombo = None

        # main widget (CWall)
        self.w = None

    def setMode(self, mode):
        self.mode = mode

    def modeComboActivated(self):
        mode = self.modeCombo.itemData(self.modeCombo.currentIndex()).toInt()[0]
        if mode != self.mode:
            print "changing mode to %s" % mode
            self.mode = mode

M = Main()
mypd = None

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

class Walls:
    def __init__(self):
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

        self.pen = QtGui.QPen(QtCore.Qt.black)
        self.pen.setWidthF(2.0)

    def paint(self, pnt):
        pnt.setPen(self.pen)

        for wall in self.walls:
            pnt.drawLine(wall.p1.x, wall.p1.y, wall.p2.x, wall.p2.y)

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

        self.font = QtGui.QFont("DejaVu Sans Mono", 18)
        #self.font = QtGui.QFontDialog.getFont(self.font)[0]

        self.fontMetrics = QtGui.QFontMetrics(self.font)

        self.offset = 10
        self.flipSide = False

    def attachTo(self, wall, closestPt, t):
        self.wall = wall
        self.t = t

        self.recalcPos()

    def recalcPos(self):
        AB = self.wall.p2 - self.wall.p1

        pos = self.wall.p1 + AB * self.t

        self.x = pos.x
        self.y = pos.y

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

        if mypd and 0:
            # FIXME: remove
            font = QtGui.QFont(self.font, mypd)
            pnt.setFont(font)
        else:
            pnt.setFont(self.font)

        pnt.translate(self.x, self.y)
        pnt.rotate(self.angle)

        #pnt.scale(0.5, 0.5)

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

        self.setFocusPolicy(QtCore.Qt.WheelFocus)
        self.setMouseTracking(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.BlankCursor))
        #self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)

        self.mousePos = Point(-1, -1)
        self.mouseDown = False
        self.route = Route()
        self.routes = []

        self.walls = Walls()

        self.wallEdit = True

        # wall editing stuff

        # closest wall point
        self.closestWallPt = None

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_F:
            self.route.flipSide = not self.route.flipSide
            self.update()
        elif key == QtCore.Qt.Key_A:
            self.routes.append(self.route)
            self.route = Route()
            self.update()
        elif key == QtCore.Qt.Key_S:
            global mypd
            #printer = QtGui.QPrinter(QtGui.QPrinter.HighResolution)
            printer = QtGui.QPrinter(QtGui.QPrinter.ScreenResolution)
            printer.setOutputFileName("wall.pdf")
            #printer.setResolution(1200)

            mypd = printer

            pnt = QtGui.QPainter()
            pnt.begin(printer)
            self.paint(pnt)
            pnt.end()

            print "saved PDF file"
        elif key == QtCore.Qt.Key_W:
            if not self.wallEdit:
                self.wallEdit = True
            else:
                self.wallEdit = False

            self.update()

        elif key == QtCore.Qt.Key_T:
            zz = util.TimerDev("50 paints")

            for i in xrange(50):
                self.repaint()

    def wallEditActivity(self):
        if self.wallEdit and self.mouseDown and self.closestWallPt:
            self.closestWallPt.x = self.mousePos.x
            self.closestWallPt.y = self.mousePos.y

        # TODO: optimize this, we only need to recalc the routes belonging
        # to the two wall segments touching the modified point
        for route in self.routes:
            route.recalcPos()

    def mouseMoveEvent(self, event):
        self.mousePos = Point(event.x(), event.y())
        self.wallEditActivity()
        self.update()

    def mousePressEvent(self, event):
        self.mouseDown = True
        self.wallEditActivity()
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouseDown = False
        self.wallEditActivity()
        self.update()

    def paintEvent(self, event):
        pnt = QtGui.QPainter()
        pnt.begin(self)

        self.paint(pnt)

        pnt.end()

    def paint(self, pnt):
        #size = self.size()

        pnt.setRenderHint(QtGui.QPainter.Antialiasing)
        pnt.setRenderHint(QtGui.QPainter.TextAntialiasing)

        self.walls.paint(pnt)

        pen = QtGui.QPen(QtCore.Qt.red)
        pen.setWidthF(2.0)
        pnt.setPen(pen)

        pnt.drawEllipse(self.mousePos.x - 2.5, self.mousePos.y - 2.5, 5, 5)

        pen = QtGui.QPen(QtCore.Qt.blue)
        pen.setWidthF(2.0)
        pnt.setPen(pen)

        if self.wallEdit:
            closestDistance = 99999999.9
            closestPt = None

            for pt in self.walls.points:
                dst = pt.distanceTo(self.mousePos)

                if dst < closestDistance:
                    closestDistance = dst
                    closestPt = pt

            if closestPt:
                pnt.drawEllipse(closestPt.x - 2.5, closestPt.y - 2.5, 5, 5)
                self.closestWallPt = closestPt

            # FIXME: debug stuff, remove
            for route in self.routes:
                route.paint(pnt)

        else:
            for route in self.routes:
                route.paint(pnt)

            closestDistance = 99999999.9
            closestPt = None
            closestT = None
            closestWall = None

            for wall in self.walls.walls:
                closest, t = closestPoint(wall.p1, wall.p2, self.mousePos)

                dst = closest.distanceTo(self.mousePos)

                if dst < closestDistance:
                    closestDistance = dst
                    closestPt = closest
                    closestT = t
                    closestWall = wall

            if closestPt:
                #pnt.drawEllipse(closestPt.x - 2.5, closestPt.y - 2.5, 5, 5)

                self.route.attachTo(closestWall, closestPt, closestT)
                self.route.paint(pnt)



def main():
    app = QtGui.QApplication(sys.argv)

    mw = QtGui.QMainWindow()
    mw.setGeometry(400, 50, 850, 700)
    mw.setWindowTitle("Climbing walls")

    w = QtGui.QWidget()
    vbox = QtGui.QVBoxLayout(w)
    hbox = QtGui.QHBoxLayout()

    M.modeCombo = QtGui.QComboBox(w)

    for key, val in M.modeNames.iteritems():
        M.modeCombo.addItem(val, QtCore.QVariant(key))

    M.modeCombo.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

    QtCore.QObject.connect(M.modeCombo, QtCore.SIGNAL("activated(int)"),
                           M.modeComboActivated)

    hbox.addWidget(M.modeCombo)
    hbox.addStretch()

    hbox.setContentsMargins(5, 5, 5, 5)

    vbox.addLayout(hbox)

    sep = QtGui.QFrame(w)
    sep.setFrameStyle(QtGui.QFrame.HLine)
    vbox.addWidget(sep)

    M.w = CWall(w)

    vbox.addWidget(M.w, 1)

    vbox.setSpacing(0)
    vbox.setContentsMargins(0, 0, 0, 0)

    mw.setCentralWidget(w)

    M.setMode(Main.WALL_MOVE)

    mw.show()

    app.exec_()

main()
