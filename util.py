import error

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

# load at most maxSize (all if -1) bytes from 'filename', returning the
# data as a string or None on errors. pops up message boxes using 'parent'
# as parent on errors.
def loadFile(filename, parent, maxSize = -1):
    ret = None

    try:
        f = open(filename, "rb")

        try:
            ret = f.read(maxSize)
        finally:
            f.close()

    except IOError, (errno, strerror):
        QtGui.QMessageBox.critical(
            parent, "Error", "Error loading file '%s': %s" % (
                filename, strerror))
        ret = None

    return ret

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

# clamps the given value to a specific range. both limits are optional.
def clamp(val, minVal = None, maxVal = None):
    ret = val

    if minVal != None:
        ret = max(ret, minVal)

    if maxVal != None:
        ret = min(ret, maxVal)

    return ret

# convert given string to float, clamping it to the given range
# (optional). never throws any exceptions, return defVal (possibly clamped
# as well) on any errors.
def str2float(s, defVal, minVal = None, maxVal = None):
    val = defVal

    try:
        val = float(s)
    except (ValueError, OverflowError):
        pass

    return clamp(val, minVal, maxVal)

# like str2float, but for ints.
def str2int(s, defVal, minVal = None, maxVal = None, radix = 10):
    val = defVal

    try:
        val = int(s, radix)
    except ValueError:
        pass

    return clamp(val, minVal, maxVal)

# get named attribute value from el, which is an etree.Element. throws
# error.ConfigError if attribute does not exist.
def getAttr(el, attrName):
    val = el.get(attrName)

    cfgAssert(val is not None, "Attribute '%s' not found in element '%s'" % (
            attrName, el.tag))

    return val

# like getAttr, but validates value for being a valid float, and returns a
# float.
def getFloatAttr(el, attrName):
    val = str2float(getAttr(el, attrName), None)

    cfgAssert(val is not None,
              "Invalid float attribute '%s' in element '%s'" % (
            attrName, el.tag))

    return val

# like getAttr, but also validates value for being a valid UUID
def getUUIDAttr(el, attrName):
    val = getAttr(el, attrName)

    cfgAssert(isValidUUID(val),
              "Invalid ID attribute '%s' in element '%s'" % (
            attrName, el.tag))

    return val

# return random new UUID
def UUID():
    return uuid.uuid4().hex

# return true if uuid is a valid string representation of an UUID
def isValidUUID(uuid):
    return ((len(uuid) == 32) and
            (str2int(uuid, defVal = None, radix = 16) is not None))

def cfgAssert(val, s):
    myAssert(val, s, error.ConfigError)

def myAssert(val, s, errorClass):
    if not val:
        raise errorClass(s)
