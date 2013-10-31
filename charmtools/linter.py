

class Linter(object):
    def __init__(self, debug=False):
        self.lint = []
        self.exit_code = 0
        self.debug = debug

    def crit(self, msg):
        """Called when checking cannot continue."""
        self.err("FATAL: " + msg)

    def err(self, msg):
        global EXIT_CODE
        self.lint.append("E: " + msg)
        if self.exit_code < 200:
            self.exit_code = 200

    def info(self, msg):
        """Ignorable but sometimes useful."""
        self.lint.append("I: " + msg)

    def warn(self, msg):
        global EXIT_CODE
        self.lint.append("W: " + msg)
        if self.exit_code < 100:
            self.exit_code = 100
