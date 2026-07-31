import os

def ping(host: str) -> int:
    return os.system("ping -c1 " + host)
