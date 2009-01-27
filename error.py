# exception classes

class CWallError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

class ConfigError(CWallError):
    def __init__(self, msg):
        CWallError.__init__(self, msg)
