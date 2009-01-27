from PyQt4 import QtCore

QRectF = QtCore.QRectF

# draw centered ellipse
def drawEllipse(pnt, center, size):
    offset = size / 2.0
    pnt.drawEllipse(QRectF(center.x - offset, center.y - offset, size, size))
