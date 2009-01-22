import os
import time
import uuid

from PyQt4 import QtGui

# return True if given file exists.
def fileExists(filename):
    try:
        os.stat(filename)
    except OSError:
        return False

    return True

# simple timer class for use during development only
class TimerDev:

    # how many TimerDev instances are currently in existence
    nestingLevel = 0

    def __init__(self, msg = ""):
        self.msg = msg
        self.__class__.nestingLevel += 1
        self.t = time.time()

    def __del__(self):
        self.t = time.time() - self.t
        self.__class__.nestingLevel -= 1
        print "%s%s took %.5f seconds" % (" " * self.__class__.nestingLevel,
                                          self.msg, self.t)

# write 'data' to 'filename', popping up a messagebox using 'parent'
# (QWidget) as parent on errors. returns True on success.
def writeToFile(filename, data, parent):
    try:
        f = open(filename, "wb")

        try:
            f.write(data)
        finally:
            f.close()

        return True

    except IOError, (errno, strerror):
        QtGui.QMessageBox.critical(
            parent, "Error", "Error writing file '%s': %s" % (
                filename, strerror))

        return False

# return a string representation of a floating point value that preserves
# all precision, i.e. "val = float(float2str(val))" is guaranteed to be a
# no-op
def float2str(val):
    s = ("%.22f" % val).rstrip("0")

    if s.endswith("."):
        s += "0"

    return s

# return random new UUID
def UUID():
    return uuid.uuid4().hex
