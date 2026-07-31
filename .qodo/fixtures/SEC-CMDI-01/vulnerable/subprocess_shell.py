import subprocess

def ping(host: str):
    return subprocess.run("ping -c1 " + host, shell=True)
