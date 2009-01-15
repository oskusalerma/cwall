import os
import time

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
