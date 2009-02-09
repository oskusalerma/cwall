#!/usr/bin/python
# coding: Latin-1

from __future__ import with_statement

import error
import gutil
import util

import sys, random, math

import lxml.etree as etree
from PyQt4 import QtGui, QtCore

QRectF = QtCore.QRectF
QPointF = QtCore.QPointF
QLineF = QtCore.QLineF
QPen = QtGui.QPen

SQRT_2 = math.sqrt(2)

# Qt's font rendering system can't really handle font sizes as small as
# 0.09 and then scaling the painting context up 50x, so internally we
# operate not in meters but in centimeters so we can use 100x bigger
# numbers. all user-exposed numbers are in meters though.
SCALE = 100.0

# size of small marker circles, in pixels
CIRCLE_SIZE = 8

# size of small marker rectangles
RECTANGLE_SIZE = 20

# font for displaying information about walls such as length etc
WALL_FONT = QtGui.QFont("Courier New", 18)
WALL_FONT.setPixelSize(48)

class Color:
    def __init__(self, name, r, g, b):
        self.name = name
        self.r = r
        self.g = g
        self.b = b

        self.brush = QtGui.QBrush(QtGui.QColor(r, g, b))

    def save(self):
        return self.name

    @staticmethod
    def load(s):
        for c in COLORS:
            if c.name == s:
                return c

        util.cfgAssert(0, "Unknown color '%s'" % s)

# FIXME: move inside Color
COLORS = [
    Color("Blue", 40, 67, 176),
    Color("Light blue", 128, 128, 255),
    Color("Green", 41, 102, 68),
    Color("Light green", 19, 151, 126),
    Color("Red", 245, 32, 34),
    Color("Yellow", 237, 237, 0),
    Color("Pink", 222, 47, 222),
    Color("Orange", 230, 114, 0),
    Color("Brown", 150, 75, 0),
    Color("White", 240, 240, 240),
    Color("Black", 0, 0, 0)
]

class Rating:
    # all possible Rating objects, ordered from easiest to hardest
    RATINGS = []

    def __init__(self, text, compareIdx):
        # textual representation, e.g. "5.4" or "5.10a"
        self.text = text

        # integral comparison index, with easier routes having a lower
        # number
        self.compareIdx = compareIdx

    @staticmethod
    def add(ratings):
        for s in ratings:
            Rating.RATINGS.append(Rating(s, len(Rating.RATINGS)))

    def save(self):
        return self.text

    @staticmethod
    def load(s):
        for r in Rating.RATINGS:
            if r.text == s:
                return r

        util.cfgAssert(0, "Unknown rating '%s'" % s)

Rating.add([
        ("5.4"), ("5.5"), ("5.6"), ("5.7"), ("5.8"), ("5.9"),
        ("5.10a"), ("5.10b"), ("5.10c"), ("5.10d"),
        ("5.11a"), ("5.11b"), ("5.11c"), ("5.11d"),
        ("5.12a"), ("5.12b"), ("5.12c"), ("5.12d"),
        ("5.13a"), ("5.13b"), ("5.13c"), ("5.13d"),
        ("5.14a"), ("5.14b"), ("5.14c"), ("5.14d"),
        ("5.15a"), ("5.15b")
        ])

# misc globally needed stuff
class Main:
    def __init__(self):

        self.modes = [
            ("Move walls", WallMoveMode),
            ("Add walls", WallAddMode),
            ("Split walls", WallSplitMode),
            ("Combine walls", WallCombineMode),
            ("Add routes", RouteAddMode),
            ("Edit routes", RouteEditMode)
            ]

        # key = Mode subclass class object, value = index in above list
        self.mode2index = {}

        for index, (name, modeClass) in enumerate(self.modes):
            self.mode2index[modeClass] = index

        # mode selection combobox
        self.modeCombo = None

        # whether to show wall lengths checkbox
        self.showWallLengthsCb = None

        # main widget (MyWidget)
        self.w = None

        # main window
        self.mw = None

        self.clear()

    def clear(self, initTime = True):
        if initTime:
            # physical mouse pos in window system pixel coordinates
            self.physicalMousePos = Point(-1, -1)

        # logical mouse pos in translated / scaled coordinates
        self.mousePos = Point(-1, -1)

        self.mouseDown = False
        self.route = None

        self.viewportOffset = Point(0.0, 0.0)
        self.viewportScale = 0.2

        # mode class (WallMoveMode, ...)
        self.modeClass = None

        # mode class instance
        self.mode = None

    def saveCW(self):
        CW.save()

    def loadCW(self):
        global CW

        data = util.loadFile("pump2.xml", self.mw)

        if data is None:
            return

        try:
            CW = ClimbingWall.load(data)
            M.clear(False)
            M.calcMousePos()
            M.setMode(RouteEditMode, True)

        except error.ConfigError, e:
            QtGui.QMessageBox.critical(
                self.mw, "Error", "Error loading file '%s': %s" % (
                    "pump2.xml", e))

    def setMode(self, modeClass, setCombo):
        if modeClass is self.modeClass:
            return

        #self.mode.deactivate()

        if setCombo:
            self.modeCombo.setCurrentIndex(self.mode2index[modeClass])

        self.route = None
        self.modeClass = modeClass
        self.mode = modeClass()
        self.mode.activate()

        self.w.update()

    def modeComboActivated(self):
        self.setMode(self.modeCombo.itemData(
                self.modeCombo.currentIndex()).toPyObject(), False)

    # transform physical coordinates to logical coordinates, returning the
    # new (x, y) pair
    def phys2log(self, x, y):
        x /= self.viewportScale
        y /= self.viewportScale

        x -= self.viewportOffset.x
        y -= self.viewportOffset.y

        return (x, y)

    # calculate logical mouse pos from physical mouse pos
    def calcMousePos(self):
        self.mousePos = Point(*self.phys2log(
                self.physicalMousePos.x, self.physicalMousePos.y))

        # FIXME: debug stuff, remove
        if 0:
            print "physical mouse pos: (%f, %f)" % (
                self.physicalMousePos.x, self.physicalMousePos.y)
        if 0:
            print "logical mouse pos: (%f, %f)\n" % (
                self.mousePos.x / SCALE, self.mousePos.y / SCALE)

    # set zoom scale. scale = 1.0 means logical/physical coordinates map
    # 1-to-1.
    def setZoom(self, scale):
        size = self.w.size()

        # center point
        centerX, centerY = self.phys2log(
            size.width() / 2.0, size.height() / 2.0)

        # logical new size
        logW = size.width() / scale
        logH = size.height() / scale

        self.viewportScale = float(scale)
        self.viewportOffset.x = -centerX + logW / 2.0
        self.viewportOffset.y = -centerY + logH / 2.0

        # FIXME: debug stuff, remove
        if 0:
            print "center: %s,%s" % (centerX, centerY)
            print "size: %s" % size
            print "log size: %s,%s" % (logW, logH)
            print "offset: %s,%s" % (self.viewportOffset.x, self.viewportOffset.y)

        self.calcMousePos()
        self.mode.moveEvent()

    def zoomIn(self):
        # FIXME: have some maximum limit
        self.setZoom(M.viewportScale * 1.1)

    def zoomOut(self):
        # FIXME: have some minimum limit
        self.setZoom(M.viewportScale * 0.9)

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
        # if we're already moving a point, don't switch to another point
        if not M.mouseDown:
            self.closestPt = getClosestEndPoint()

        if M.mouseDown and self.closestPt:
            self.closestPt.x = M.mousePos.x
            self.closestPt.y = M.mousePos.y

            # TODO: optimize this, we only need to recalc the routes
            # belonging to the two wall segments touching the modified
            # point
            for route in CW.routes:
                route.recalcPos()

    def paint(self, pnt):
        if self.closestPt:
            gutil.drawEllipse(pnt, self.closestPt,
                              CIRCLE_SIZE / M.viewportScale)

        for route in CW.routes:
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

            CW.walls.points.remove(pt)
            CW.walls.walls.remove(w2)

            self.closestPt = getClosestEndPoint()

    def moveEvent(self):
        self.closestPt = getClosestEndPoint()

    def paint(self, pnt):
        if self.closestPt:
            gutil.drawEllipse(pnt, self.closestPt,
                              CIRCLE_SIZE / M.viewportScale)

        for route in CW.routes:
            route.paint(pnt)


class WallAddMode(Mode):
    def __init__(self):
        Mode.__init__(self, True)

        self.closestPt = None

    def activate(self):
        print "activating wall add mode"

    def buttonEvent(self, isPress):
        if isPress and self.closestPt:
            pt = Point(M.mousePos.x, M.mousePos.y)

            if self.closestPt is CW.walls.points[0]:
                wall = Wall(pt, CW.walls.points[0])
                ptIdx = 0
                wallIdx = 0
            else:
                wall = Wall(CW.walls.points[-1], pt)
                ptIdx = len(CW.walls.points)
                wallIdx = len(CW.walls.walls)

            CW.walls.points.insert(ptIdx, pt)
            CW.walls.walls.insert(wallIdx, wall)

            self.closestPt = None

    def moveEvent(self):
        p1 = CW.walls.points[0]
        p2 = CW.walls.points[-1]

        if p1.distanceTo(M.mousePos) < p2.distanceTo(M.mousePos):
            self.closestPt = p1
        else:
            self.closestPt = p2

    def paint(self, pnt):
        if self.closestPt:
            pnt.setPen(CW.walls.pen)

            pnt.drawLine(QLineF(self.closestPt.x, self.closestPt.y,
                                M.mousePos.x, M.mousePos.y))

            if M.showWallLengthsCb.isChecked():
                drawDistance(pnt, self.closestPt, M.mousePos)

        for route in CW.routes:
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

            ptIdx = CW.walls.points.index(wOld.p2)
            CW.walls.points.insert(ptIdx, pt)

            wallIdx = CW.walls.walls.index(wOld)

            CW.walls.walls.insert(wallIdx, wNew)

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
            gutil.drawEllipse(pnt, self.closestPt,
                              CIRCLE_SIZE / M.viewportScale)

        for route in CW.routes:
            route.paint(pnt)


class RouteAddMode(Mode):
    def __init__(self):
        Mode.__init__(self)

        M.route = Route()
        self.closestPt = None

    def activate(self):
        print "activating route add mode"

    def buttonEvent(self, isPress):
        if isPress:
            editRoute(M.route)
            CW.routes.append(M.route)
            M.route = Route()
            self.moveEvent()

    def moveEvent(self):
        closestPt, closestWall, closestT = getClosestPoint()

        if closestPt:
            self.closestPt = closestPt
            M.route.attachTo(closestWall, closestT)

    def paint(self, pnt):
        if self.closestPt:
            gutil.drawEllipse(pnt, self.closestPt,
                              CIRCLE_SIZE / M.viewportScale)

        for route in CW.routes:
            route.paint(pnt)

        M.route.paint(pnt)


class RouteEditMode(Mode):
    def __init__(self):
        Mode.__init__(self)

        self.closestRoute = None

    def activate(self):
        print "activating route edit mode"

    def buttonEvent(self, isPress):
        if isPress and self.closestRoute:
            editRoute(self.closestRoute)

    def moveEvent(self):
        r = getClosestRoute()

        if r:
            self.closestRoute = r

    def paint(self, pnt):
        if self.closestRoute:
            r = self.closestRoute
            gutil.drawEllipse(pnt, Point(r.x, r.y),
                              CIRCLE_SIZE / M.viewportScale)

        for route in CW.routes:
            route.paint(pnt)

# a single continuous climbing wall, consisting of wall segments and
# routes positioned on those segments
class ClimbingWall:
    # file-format version that we write out
    VERSION = 1

    def __init__(self):
        self.routes = []
        self.walls = Walls.createInitial()
        self.id = util.UUID()

    def save(self):
        el = etree.Element("ClimbingWall")
        el.set("version", str(self.__class__.VERSION))
        el.set("id", self.id)
        self.walls.save(el)

        routesEl = etree.SubElement(el, "Routes")

        for route in self.routes:
            routesEl.append(route.toXml())

        data = etree.tostring(el, xml_declaration = True,
                              encoding = "UTF-8", pretty_print = True)

        util.writeToFile("pump2.xml", data, M.mw)

    @staticmethod
    def load(data):
        try:
            root = etree.XML(data)
            cw = ClimbingWall()

            version = util.str2int(util.getAttr(root, "version"), 0)

            util.cfgAssert(version > 0, "Invalid version attribute")

            util.cfgAssert(version <= cw.__class__.VERSION,
                           "File uses a newer format than this program recognizes."
                           " Please upgrade your program.")

            cw.id = util.getUUIDAttr(root, "id")

            cw.walls = Walls.load(root)

            for el in root.xpath("Routes/Route"):
                cw.routes.append(Route.load(el, cw))

            return cw

        except etree.XMLSyntaxError, e:
            util.cfgAssert(0, "XML parsing error: %s" % e)


# draw distance between two points
def drawDistance(pnt, p1, p2):
    pnt.save()

    dst = p1.distanceTo(p2)

    pnt.setFont(WALL_FONT)
    pnt.drawText(QPointF((p1.x + p2.x) / 2.0,
                         (p1.y + p2.y) / 2.0),
                 "%.2f m" % (dst / SCALE))

    pnt.restore()

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

        for wall in CW.walls.walls:
            if wall.p2 is self:
                w1 = wall
            elif wall.p1 is self:
                w2 = wall

            if w2:
                break

        return (w1, w2)

    def toXml(self):
        el = etree.Element("Point")

        el.set("x", util.float2str(self.x  / SCALE))
        el.set("y", util.float2str(self.y / SCALE))

        return el

    @staticmethod
    def load(el):
        p = Point(-1, -1)

        p.x = util.getFloatAttr(el, "x") * SCALE
        p.y = util.getFloatAttr(el, "y") * SCALE

        return p

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

    for wall in CW.walls.walls:
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

    for pt in CW.walls.points:
        dst = pt.distanceTo(M.mousePos)

        if dst < closestDistance:
            closestDistance = dst
            closestPt = pt

    return closestPt

# return closest route to mouse cursor, or None if it does not exist
def getClosestRoute():
    closestDistance = 99999999.9
    closestRoute = None

    for route in CW.routes:
        dst = M.mousePos.distanceTo(Point(route.x, route.y))

        if dst < closestDistance:
            closestDistance = dst
            closestRoute = route

    return closestRoute

class RouteEditDlg(QtGui.QDialog):

    def __init__(self, route):
        QtGui.QDialog.__init__(self, M.mw)

        self.route = route

        self.setWindowTitle("Edit route")

        fl = QtGui.QFormLayout(self)

        combo = QtGui.QComboBox(self)
        combo.setMaxVisibleItems(100)

        for rating in Rating.RATINGS:
            combo.addItem(rating.text, QtCore.QVariant(rating))

            if rating is route.rating:
                combo.setCurrentIndex(combo.count() - 1)

        QtCore.QObject.connect(combo, QtCore.SIGNAL("activated(int)"),
                               self.gui2cfg)

        self.ratingCombo = combo

        fl.addRow("Rating:", combo)

        marker = MarkerSelectionWidget(route.marker, route.color, self)

        QtCore.QObject.connect(marker, QtCore.SIGNAL("stateChanged()"),
                               self.gui2cfg)

        fl.addRow("Marker:", marker)
        self.markerSel = marker

        self.addDate(fl, "dateAddedW", "added", route.dateAdded)
        self.addDate(fl, "dateRemovedW", "removed", route.dateRemoved)

    def addDate(self, fl, name, s, date):
        w = DateWidget(self, date)

        QtCore.QObject.connect(
            w, QtCore.SIGNAL("stateChanged()"), self.gui2cfg)

        fl.addRow("Date %s:" % s, w)

        setattr(self, name, w)

    def gui2cfg(self):
        self.route.rating = self.ratingCombo.itemData(
            self.ratingCombo.currentIndex()).toPyObject()

        self.route.color = self.markerSel.color
        self.route.marker = self.markerSel.marker
        self.route.dateAdded = self.dateAddedW.date
        self.route.dateRemoved = self.dateRemovedW.date

        M.w.update()

# to be used for enabling cursor over main window when showing a modal
# dialog (because the main window doesn't get mouse move events in that
# case and thus won't draw its own cursor). usage:
#
#  with CursorShower():
#    dlg.exec_()
class CursorShower:
    def __enter__(self):
        M.w.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        return self

    def __exit__(self, excType, value, traceback):
        M.w.setCursor(QtGui.QCursor(QtCore.Qt.BlankCursor))

# edit Route's properties
def editRoute(route):
    dlg = RouteEditDlg(route)

    with CursorShower():
        dlg.exec_()

class Wall:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.id = util.UUID()

        self.routes = []

    def __str__(self):
        return "P1:%s P2:%s id:%s" % (self.p1, self.p2, self.id)

    # return a copy of the wall's routes
    def getRoutes(self):
        return list(self.routes)

    def toXml(self):
        el = etree.Element("Wall")

        el.set("id", self.id)

        return el

    @staticmethod
    def load(el, walls):
        w = Wall(None, None)

        w.id = util.getUUIDAttr(el, "id")

        # use the next pair of points
        index = len(walls.walls)

        util.cfgAssert((index + 1) < len(walls.points),
                       "Not enough points defined")

        w.p1 = walls.points[index]
        w.p2 = walls.points[index + 1]

        return w

class Walls:
    def __init__(self):
        self.points = []
        self.walls = []

        self.pen = QPen(QtCore.Qt.black)
        self.pen.setWidthF(5.0)

    # return initial object suitable for use if nothing else is loaded on
    # startup
    @staticmethod
    def createInitial():
        w = Walls()

        w.points = [
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

        w.walls = []

        for i in xrange(1, len(w.points)):
            w.walls.append(Wall(w.points[i - 1], w.points[i]))

        return w

    # lookup wall segment by id. returns None if not found.
    def getWallById(self, wallId):
        for w in self.walls:
            if w.id == wallId:
                return w

        return None

    def paint(self, pnt, drawEndPoints):
        pnt.setPen(self.pen)

        showWallLen = M.showWallLengthsCb.isChecked()

        for wall in self.walls:
            pnt.drawLine(QLineF(wall.p1.x, wall.p1.y, wall.p2.x, wall.p2.y))

            if showWallLen:
                drawDistance(pnt, wall.p1, wall.p2)

        if drawEndPoints:
            offset = RECTANGLE_SIZE / 2.0

            for pt in self.points:
                pnt.drawRect(QRectF(pt.x - offset, pt.y - offset,
                                    RECTANGLE_SIZE, RECTANGLE_SIZE))

    def save(self, el):
        pointEl = etree.SubElement(el, "Points")
        wallEl = etree.SubElement(el, "Walls")

        for p in self.points:
            pointEl.append(p.toXml())

        for w in self.walls:
            wallEl.append(w.toXml())

    @staticmethod
    def load(root):
        w = Walls()

        for el in root.xpath("Points/Point"):
            w.points.append(Point.load(el))

        for el in root.xpath("Walls/Wall"):
            w.walls.append(Wall.load(el, w))

        util.cfgAssert(len(w.walls) == (len(w.points) - 1),
                       "Invalid number of points or walls")

        return w

class Marker:
    SIZE = 18

    # all possible Marker objects
    MARKERS = []

    # marker shapes
    SQUARE, RECTANGLE, CROSS, DIAMOND_TAIL = range(4)

    def __init__(self, name, shape):
        self.name = name
        self.shape = shape

        self.pen = QPen(QtCore.Qt.black)
        self.pen.setWidthF(1.0)

        self.gridPen = QPen(QtCore.Qt.green)
        self.gridPen.setWidthF(0.2)

    def size(self):
        return Marker.SIZE

    def save(self):
        return self.name

    @staticmethod
    def load(s):
        for marker in Marker.MARKERS:
            if marker.name == s:
                return marker

        util.cfgAssert(0, "Unknown marker shape '%s'" % s)

    # marker should fit in a rectangle whose dimensions are Marker.SIZE.
    # in this paint function, the coordinate system is set up as follows:
    #  x = left side of rectangle
    #  y (implicitly 0) = center of rectangle
    def paint(self, pnt, color, x):
        pnt.setPen(self.pen)
        pnt.setBrush(color.brush)

        size = Marker.SIZE
        mSize = size

        if self.shape == Marker.SQUARE:
            pnt.drawRect(QRectF(x, -size / 2.0, size, size))

        elif self.shape == Marker.RECTANGLE:
            size /= 3.0

            pnt.save()
            pnt.translate(x + mSize / 2.0, 0)
            pnt.rotate(-45)
            pnt.drawRect(QRectF(-mSize / 2.0, -size / 2.0, mSize, size))
            pnt.restore()

        elif self.shape == Marker.CROSS:
            size /= 3.0
            pnt.drawRect(QRectF(x, -size / 2.0, mSize, size))

            pnt.drawRect(QRectF(
                    x + mSize / 2.0 - size / 2.0,
                    -mSize / 2.0,
                    size, mSize))

        elif self.shape == Marker.DIAMOND_TAIL:
            tailSize = size / 3.0
            dSize = size / 2.0

            # half of the diagonal of the diamond square
            a = dSize / SQRT_2

            pnt.drawRect(QRectF(x + tailSize, -size / 2.0 + a,
                                tailSize, size - a))

            pnt.save()
            pnt.translate(x + size / 2.0,
                          -size / 2.0 + a)
            pnt.rotate(-45)
            pnt.drawRect(QRectF(-dSize / 2.0, -dSize / 2.0,
                                 dSize, dSize))

            pnt.restore()

        #self.paintGrid(pnt, x, 0)

    # when debugging paint problems, it's useful to have a grid painted on
    # top of the marker to show boundaries and center lines.
    def paintGrid(self, pnt, x, y):
        size = Marker.SIZE

        pnt.save()
        pnt.setPen(self.gridPen)

        # vertical
        pnt.drawLine(QLineF(x, y + -size / 2.0, x, y + size / 2.0))
        pnt.drawLine(QLineF(x + size / 2.0, y + -size / 2.0,
                            x + size / 2.0, y + size / 2.0))
        pnt.drawLine(QLineF(x + size, y + -size / 2.0, x + size,
                            y + size / 2.0))

        # horizontal
        pnt.drawLine(QLineF(x, y + -size / 2.0, x + size,
                            y + -size / 2.0))
        pnt.drawLine(QLineF(x, y, x + size, y))
        pnt.drawLine(QLineF(x, y + size / 2.0, x + size,
                            y + size / 2.0))

        pnt.restore()

Marker.MARKERS.extend(
    [Marker("Square", Marker.SQUARE),
     Marker("Rectangle", Marker.RECTANGLE),
     Marker("Cross", Marker.CROSS),
     Marker("DiamondTail", Marker.DIAMOND_TAIL)
     ])

class Route:
    def __init__(self):
        self.id = util.UUID()
        self.rating = Rating.RATINGS[0]
        self.color = COLORS[0]
        self.marker = Marker.MARKERS[0]
        self.dateAdded = None
        self.dateRemoved = None

        self.x = 0
        self.y = 0

        self.t = 0
        self.angle = 0.0
        self.wall = None

        self.font = QtGui.QFont("DejaVu Sans Mono", 18)
        self.font.setPixelSize(18)
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

    def toXml(self):
        el = etree.Element("Route")

        el.set("id", self.id)
        el.set("wallId", self.wall.id)
        el.set("t", util.float2str(self.t))
        el.set("color", self.color.save())
        el.set("marker", self.marker.save())
        el.set("rating", self.rating.save())

        if self.dateAdded:
            el.set("dateAdded", self.dateAdded.save())

        if self.dateRemoved:
            el.set("dateRemoved", self.dateRemoved.save())

        return el

    @staticmethod
    def load(el, cw):
        r = Route()

        r.id = util.getUUIDAttr(el, "id")
        r.color = Color.load(util.getAttr(el, "color"))
        r.marker = Marker.load(util.getAttr(el, "marker"))
        r.rating = Rating.load(util.getAttr(el, "rating"))
        r.dateAdded = util.getDateAttr(el, "dateAdded")
        r.dateRemoved = util.getDateAttr(el, "dateRemoved")

        wallId = util.getUUIDAttr(el, "wallId")
        wall = cw.walls.getWallById(wallId)

        util.cfgAssert(wall, "Route attached to unknown wall '%s'" % wallId)

        r.attachTo(wall, t = util.getFloatAttr(el, "t"))

        return r

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

        #pnt.drawLine(QLineF(0, 0, self.offset, 0))

        # FIXME: have an option whether to include name of color
        #s = "%s %s" % (self.rating.text, self.color.name)
        s = "%s" % (self.rating.text)

        textRect = pnt.boundingRect(0, 0, 0, 0, 0, s)

        if self.flipSide:
            x = -textRect.width() - self.offset * 1.5 - self.marker.size()
        else:
            x = self.offset

        pnt.drawText(
            QPointF(x, -self.fontMetrics.descent() + textRect.height() / 2.0),
            s)

        x += textRect.width() + self.offset / 2.0

        self.marker.paint(pnt, self.color, x)
        pnt.restore()


# date widget that has an on/off selection as well that means "no date is
# specified at all"
class DateWidget(QtGui.QWidget):
    def __init__(self, parent, date):
        QtGui.QWidget.__init__(self, parent)

        hbox = QtGui.QHBoxLayout(self)
        hbox.setContentsMargins(5, 0, 0, 0)

        self.cb = QtGui.QCheckBox("Set", self)
        self.cb.setChecked(date is not None)

        QtCore.QObject.connect(
            self.cb, QtCore.SIGNAL("stateChanged(int)"), self.gui2cfg)

        hbox.addWidget(self.cb)

        calW = QtGui.QCalendarWidget()
        calW.setFirstDayOfWeek(QtCore.Qt.Monday)

        if date:
            qd = date.toQDate()
        else:
            qd = QtCore.QDate.currentDate()

        dateW = QtGui.QDateEdit(qd, self)
        dateW.setDisplayFormat("d MMM yyyy")
        dateW.setCalendarPopup(True)
        dateW.setCalendarWidget(calW)

        dateW.setEnabled(date is not None)

        QtCore.QObject.connect(
            dateW, QtCore.SIGNAL("dateChanged(const QDate&)"), self.gui2cfg)

        hbox.addWidget(dateW)
        self.dateW = dateW

        self.gui2cfg(emitEvent = False)

    # unusedArg must remain so when Qt calls this from various signals the
    # argument it passes us is swallowed up
    def gui2cfg(self, unusedArg = None, emitEvent = True):
        active = self.cb.isChecked()

        self.dateW.setEnabled(active)

        if active:
            self.date = util.Date.fromQDate(self.dateW.date())
        else:
            self.date = None

        if emitEvent:
            self.emit(QtCore.SIGNAL("stateChanged()"))

class MarkerSelectionWidget(QtGui.QWidget):
    def __init__(self, marker, color, parent):
        QtGui.QWidget.__init__(self, parent)

        self.marker = marker
        self.color = color

        # empty space between markers
        self.spacing = 10

        # empty space around complete widget
        self.padding = 10

        self.size = Marker.SIZE + self.spacing

        self.setMinimumSize(
            self.size * len(COLORS) - self.spacing + self.padding * 2,
            self.size * len(Marker.MARKERS) - self.spacing + self.padding * 2)

        self.pen = QPen(QtCore.Qt.black)
        self.pen.setWidthF(1.0)

    def mousePressEvent(self, event):
        xp, yp = event.x(), event.y()

        xp -= self.padding
        yp -= self.padding

        x = util.clamp(xp // self.size, 0, len(COLORS)- 1)
        y = util.clamp(yp // self.size, 0, len(Marker.MARKERS) - 1)

        self.marker = Marker.MARKERS[y]
        self.color = COLORS[x]

        self.update()

        self.emit(QtCore.SIGNAL("stateChanged()"))

    def paintEvent(self, event):
        pnt = QtGui.QPainter()
        pnt.begin(self)

        # FIXME: move render settings to common place
        pnt.setRenderHint(QtGui.QPainter.Antialiasing)
        pnt.setRenderHint(QtGui.QPainter.TextAntialiasing)

        for y, marker in enumerate(Marker.MARKERS):
            for x, color in enumerate(COLORS):
                pnt.save()
                pnt.translate(x * self.size + self.padding,
                              y * self.size + Marker.SIZE / 2.0 + self.padding)
                marker.paint(pnt, color, 0)

                if marker is self.marker and color is self.color:
                    pnt.setPen(self.pen)
                    pnt.setBrush(QtCore.Qt.NoBrush)
                    pnt.drawRect(-self.spacing / 2.0,
                                  -Marker.SIZE / 2.0 - self.spacing / 2.0,
                                  self.size, self.size)

                pnt.restore()

        pnt.end()

class MyWidget(QtGui.QWidget):
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)

        self.setMinimumSize(800, 600)
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

        # FIXME: make movement proportional, i.e. X% of current displayed
        # size. now it's too slow if you're zoomed out and too fast if
        # you're zoomed in.
        elif key == QtCore.Qt.Key_Up:
            M.viewportOffset.y += 100.0
            M.calcMousePos()
            M.mode.moveEvent()
            self.update()

        elif key == QtCore.Qt.Key_Down:
            M.viewportOffset.y -= 100.0
            M.calcMousePos()
            M.mode.moveEvent()
            self.update()

        elif key == QtCore.Qt.Key_Left:
            M.viewportOffset.x += 100.0
            M.calcMousePos()
            M.mode.moveEvent()
            self.update()

        elif key == QtCore.Qt.Key_Right:
            M.viewportOffset.x -= 100.0
            M.calcMousePos()
            M.mode.moveEvent()
            self.update()

        elif key == QtCore.Qt.Key_Plus:
            M.zoomIn()
            self.update()

        elif key == QtCore.Qt.Key_Minus:
            M.zoomOut()
            self.update()

        else:
            QtGui.QWidget.keyPressEvent(self, event)

    def mouseMoveEvent(self, event):
        M.physicalMousePos = Point(event.x(), event.y())
        M.calcMousePos()
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

    def wheelEvent(self, event):
        steps = event.delta() / 120.0

        if steps > 0:
            M.zoomIn()
        else:
            M.zoomOut()

        event.accept()

        self.update()

    def paintEvent(self, event):
        pnt = QtGui.QPainter()
        pnt.begin(self)

        self.paint(pnt)

        pnt.end()

    def paint(self, pnt):
        #size = self.size()

        #print "scale: %f" % M.viewportScale
        pnt.scale(M.viewportScale, M.viewportScale)

        voffs = M.viewportOffset
        pnt.translate(voffs.x, voffs.y)

        pnt.setRenderHint(QtGui.QPainter.Antialiasing)
        pnt.setRenderHint(QtGui.QPainter.TextAntialiasing)

        CW.walls.paint(pnt, M.mode.drawEndPoints)

        pen = QPen(QtCore.Qt.red)
        pen.setWidthF(3.0 / M.viewportScale)
        pnt.setPen(pen)

        gutil.drawEllipse(pnt, M.mousePos, CIRCLE_SIZE / M.viewportScale)

        pen = QPen(QtCore.Qt.blue)
        pen.setWidthF(3.0 / M.viewportScale)
        pnt.setPen(pen)

        M.mode.paint(pnt)


def main():
    global M, CW, mypd

    M = Main()
    CW = ClimbingWall()

    mypd = None

    app = QtGui.QApplication(sys.argv)

    mw = QtGui.QMainWindow()
    mw.move(400,50)
    mw.setWindowTitle("Climbing walls")
    M.mw = mw

    mb = mw.menuBar()
    fmenu = mb.addMenu("&File")
    fmenu.addAction("Save climbing wall", M.saveCW, QtGui.QKeySequence.Save)
    fmenu.addAction("Load climbing wall", M.loadCW, QtGui.QKeySequence.Open)

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

    M.showWallLengthsCb = QtGui.QCheckBox("Show wall lengths", w)

    QtCore.QObject.connect(M.showWallLengthsCb, QtCore.SIGNAL("stateChanged(int)"),
                           w.update)

    hbox.addWidget(M.showWallLengthsCb)

    hbox.addStretch()

    hbox.setSpacing(10)
    hbox.setContentsMargins(5, 5, 5, 5)

    vbox.addLayout(hbox)

    sep = QtGui.QFrame(w)
    sep.setFrameStyle(QtGui.QFrame.HLine)
    vbox.addWidget(sep)

    M.w = MyWidget(w)

    vbox.addWidget(M.w, 1)

    vbox.setSpacing(0)
    vbox.setContentsMargins(0, 0, 0, 0)

    mw.setCentralWidget(w)

    M.setMode(WallMoveMode, True)

    mw.show()
    M.w.setFocus()

    app.exec_()

main()
