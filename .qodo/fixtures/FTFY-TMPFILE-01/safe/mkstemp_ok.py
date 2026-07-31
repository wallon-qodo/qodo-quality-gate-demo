import tempfile

def scratch():
    fd, path = tempfile.mkstemp()
    return fd, path
