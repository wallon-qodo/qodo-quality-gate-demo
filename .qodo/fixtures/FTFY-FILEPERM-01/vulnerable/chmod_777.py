import os

def publish(p):
    os.chmod(p, 0o777)
