import tempfile

def scratch():
    with tempfile.TemporaryDirectory() as d:
        return d
