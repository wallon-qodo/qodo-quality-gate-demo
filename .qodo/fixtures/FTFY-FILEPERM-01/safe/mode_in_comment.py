import os

def protect(p):
    # never use 0o777 here
    os.chmod(p, 0o600)
