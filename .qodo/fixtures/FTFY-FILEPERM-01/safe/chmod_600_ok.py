import os

def protect(p):
    os.chmod(p, 0o600)
