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
    def __init__(self):

        self.modes = [
            ("Move walls", WallMoveMode),
            ("Split walls", WallSplitMode),
            ("Combine walls", WallCombineMode),
            ("Add routes", RouteAddMode),
#             ("Edit routes", RouteEditMode)
            ]

        # mode selection combobox
        self.modeCombo = None

        # main widget (CWall)
        self.w = None

        self.mousePos = Point(-1, -1)
        self.mouseDown = False
        self.route = Route()
        self.routes = []
        self.walls = Walls()

        # mode class (WallMoveMode, ...)
        self.modeClass = None

        # mode class instance
        self.mode = None

    def setMode(self, modeClass):
        if modeClass is self.modeClass:
            return

        #self.mode.deactivate()

        self.modeClass = modeClass
        self.mode = modeClass()
        self.mode.activate()

        self.w.update()

    def modeComboActivated(self):
        self.setMode(self.modeCombo.itemData(
                self.modeCombo.currentIndex()).toPyObject())

# base class for modes
class Mode:
    def __init__(self, drawEndPoints = False):
        self.drawEndPoints = drawEndPoints

    # mode activated
    def activate(self):
        raise "abstract method called"

    # mouse button press/release
    def buttonEvent(self, isPress, x, y):
        raise "abstract method called"

    # mouse move event
    def moveEvent(self, x, y):
        raise "abstract method called"

    # paint
    def paint(self, pnt):
        raise "abstract method called"

class WallMoveMode(Mode):
    def __init__(self):
        Mode.__init__(self, True)

        # closest wall end point
        self.closestPt = getClosestEndPoint()

    def activate(self):
        print "activating wall move mode"

    def buttonEvent(self, isPress):
        if isPress:
            self.moveEvent()

    def moveEvent(self):
        self.closestPt = getClosestEndPoint()

        if M.mouseDown and self.closestPt:
            self.closestPt.x = M.mousePos.x
            self.closestPt.y = M.mousePos.y

            # TODO: optimize this, we only need to recalc the routes
            # belonging to the two wall segments touching the modified
            # point
            for route in M.routes:
                route.recalcPos()

    def paint(self, pnt):
        if self.closestPt:
            pnt.drawEllipse(self.closestPt.x - 2.5,
                            self.closestPt.y - 2.5, 5, 5)

        for route in M.routes:
            route.paint(pnt)


class WallCombineMode(Mode):
    def __init__(self):
        Mode.__init__(self, True)

        # closest wall end point
        self.closestPt = getClosestEndPoint()

    def activate(self):
        print "activating wall combine mode"

    def buttonEvent(self, isPress):
        if isPress and self.closestPt:
            pt = self.closestPt
            w1, w2 = pt.getWalls()

            print w1, w2

            # can't delete start or end points (for now, anyway)
            if not w1 or not w2:
                return

            l1 = w1.p1.distanceTo(w1.p2)
            l2 = w2.p1.distanceTo(w2.p2)
            totalLen = l1 + l2
            r1 = l1 / totalLen
            r2 = l2 / totalLen

            w1.p2 = w2.p2

            for route in w1.getRoutes():
                newT = route.t * r1
                route.attachTo(w1, newT)

            for route in w2.getRoutes():
                newT = route.t * r2 + r1
                route.attachTo(w1, newT)

            M.walls.points.remove(pt)
            M.walls.walls.remove(w2)

            self.closestPt = getClosestEndPoint()

    def moveEvent(self):
        self.closestPt = getClosestEndPoint()

    def paint(self, pnt):
        if self.closestPt:
            pnt.drawEllipse(self.closestPt.x - 2.5,
                            self.closestPt.y - 2.5, 5, 5)

        for route in M.routes:
            route.paint(pnt)


class WallSplitMode(Mode):
    def __init__(self):
        Mode.__init__(self, True)

        self.closestPt = None
        self.closestWall = None
        self.closestT = None

    def activate(self):
        print "activating wall split mode"

    def buttonEvent(self, isPress):
        if isPress and self.closestWall:
            wOld = self.closestWall
            pt = Point(M.mousePos.x, M.mousePos.y)

            wNew = Wall(wOld.p1, pt)
            wOld.p1 = pt

            tNew = 1.0 / self.closestT
            tOld = 1.0 / (1.0 - self.closestT)

            for route in wOld.getRoutes():
                if route.t < self.closestT:
                    newT = route.t * tNew
                    route.attachTo(wNew, newT)
                else:
                    newT = (route.t - self.closestT) * tOld
                    route.attachTo(wOld, newT)

            ptIdx = M.walls.points.index(wOld.p2)
            M.walls.points.insert(ptIdx, pt)

            wallIdx = M.walls.walls.index(wOld)

            M.walls.walls.insert(wallIdx, wNew)

            self.closestPt = None
            self.closestWall = None
            self.closestT = None

    def moveEvent(self):
        closestPt, closestWall, closestT = getClosestPoint()

        if closestPt:
            self.closestPt = closestPt

        # one can't split a wall at its end points
        if closestT not in (1.0, 0.0):
            self.closestWall = closestWall
            self.closestT = closestT

        else:
            self.closestWall = None

    def paint(self, pnt):
        if self.closestPt:
            pnt.drawEllipse(self.closestPt.x - 2.5,
                            self.closestPt.y - 2.5, 5, 5)

        for route in M.routes:
            route.paint(pnt)


class RouteAddMode(Mode):
    def __init__(self):
        Mode.__init__(self)

        self.closestPt = None

    def activate(self):
        print "activating route add mode"

    def buttonEvent(self, isPress):
        if isPress:
            M.routes.append(M.route)
            M.route = Route()
            self.moveEvent()

    def moveEvent(self):
        closestPt, closestWall, closestT = getClosestPoint()

        if closestPt:
            self.closestPt = closestPt
            M.route.attachTo(closestWall, closestT)

    def paint(self, pnt):
        if self.closestPt:
            pnt.drawEllipse(self.closestPt.x - 2.5,
                            self.closestPt.y - 2.5, 5, 5)

        for route in M.routes:
            route.paint(pnt)

        M.route.paint(pnt)

def getNextColor():
    global _currentColor

    _currentColor = (_currentColor + 1) % len(COLORS)
    return COLORS[_currentColor]

class Point:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def __str__(self):
        return "(%.3f,%.3f)" % (self.x, self.y)

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

    # return walls around this point as a (Wall, Wall) tuple. if point is
    # start/end point, either one may be None.
    def getWalls(self):
        w1 = None
        w2 = None

        for wall in M.walls.walls:
            if wall.p2 is self:
                w1 = wall
            elif wall.p1 is self:
                w2 = wall

            if w2:
                break

        return (w1, w2)

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

# return (Point, Wall, t) tuple of closest point on the wall to mouse
# cursor. t is same as second value returned from closestPoint().
def getClosestPoint():
    closestDistance = 99999999.9
    closestPt = None
    closestT = None
    closestWall = None

    for wall in M.walls.walls:
        closest, t = closestPoint(wall.p1, wall.p2, M.mousePos)

        dst = closest.distanceTo(M.mousePos)

        if dst < closestDistance:
            closestDistance = dst
            closestPt = closest
            closestT = t
            closestWall = wall

    return (closestPt, closestWall, closestT)

# return closest wall end point to mouse cursor, or None if it does not
# exist
def getClosestEndPoint():
    closestDistance = 99999999.9
    closestPt = None

    for pt in M.walls.points:
        dst = pt.distanceTo(M.mousePos)

        if dst < closestDistance:
            closestDistance = dst
            closestPt = pt

    if closestPt:
        return closestPt

class Wall:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

        self.routes = []

    # return a copy of the wall's routes
    def getRoutes(self):
        return list(self.routes)

    def __str__(self):
        return "P1:%s P2:%s" % (self.p1, self.p2)

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

    def paint(self, pnt, drawEndPoints):
        pnt.setPen(self.pen)

        for wall in self.walls:
            pnt.drawLine(wall.p1.x, wall.p1.y, wall.p2.x, wall.p2.y)

        if drawEndPoints:
            for pt in self.points:
                pnt.drawRect(pt.x - 2.5, pt.y - 2.5, 5.0, 5.0)

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
            size /= 3.0
            pnt.drawRect(x, -size / 2, Marker.SIZE, size)
            pnt.drawRect(x + Marker.SIZE / 2 - 	size / 2,
                         -Marker.SIZE / 2,
                         size, Marker.SIZE)

class Route:
    def __init__(self):
        self.level = "5.11a"
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

    def attachTo(self, wall, t):
        if self.wall:
            self.wall.routes.remove(self)

        self.wall = wall
        self.wall.routes.append(self)
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

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_F:
            M.route.flipSide = not M.route.flipSide
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

        elif key == QtCore.Qt.Key_T:
            zz = util.TimerDev("50 paints")

            for i in xrange(50):
                self.repaint()

    def mouseMoveEvent(self, event):
        M.mousePos = Point(event.x(), event.y())
        M.mode.moveEvent()
        self.update()

    def mousePressEvent(self, event):
        M.mouseDown = True
        M.mode.buttonEvent(True)
        self.update()

    def mouseReleaseEvent(self, event):
        M.mouseDown = False
        M.mode.buttonEvent(False)
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

        M.walls.paint(pnt, M.mode.drawEndPoints)

        pen = QtGui.QPen(QtCore.Qt.red)
        pen.setWidthF(2.0)
        pnt.setPen(pen)

        pnt.drawEllipse(M.mousePos.x - 2.5, M.mousePos.y - 2.5, 5, 5)

        pen = QtGui.QPen(QtCore.Qt.blue)
        pen.setWidthF(2.0)
        pnt.setPen(pen)

        M.mode.paint(pnt)


def main():
    global M, mypd

    M = Main()
    mypd = None

    app = QtGui.QApplication(sys.argv)

    mw = QtGui.QMainWindow()
    mw.setGeometry(400, 50, 850, 700)
    mw.setWindowTitle("Climbing walls")

    w = QtGui.QWidget()
    vbox = QtGui.QVBoxLayout(w)
    hbox = QtGui.QHBoxLayout()

    M.modeCombo = QtGui.QComboBox(w)

    for name, mode in M.modes:
        M.modeCombo.addItem(name, QtCore.QVariant(mode))

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

    M.setMode(WallMoveMode)

    mw.show()

    app.exec_()

main()
