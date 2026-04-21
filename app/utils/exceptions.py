import warnings


def safe_str(obj):
    """Return the byte string representation of obj"""
    warnings.warn("safe_str() is deprecated. Drop it or use str() instead.")
    try:
        return str(obj)
    except UnicodeEncodeError:
        # obj is unicode
        return str(obj).encode("unicode_escap")


class UserException(Exception):
    def __init__(self, msg):
        self.msg = msg or "User input incorrect"

    def __str__(self):
        return safe_str(self.msg)


class InvalidAPIKey(UserException):
    def __init__(self):
        self.message = "API key not found in Doppler. Please configure the project correctly."
        super().__init__(self.message)

    def __str__(self):
        return safe_str(self.message)
