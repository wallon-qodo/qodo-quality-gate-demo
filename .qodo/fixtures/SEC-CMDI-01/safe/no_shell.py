import subprocess

def listing(path: str):
    return subprocess.check_output(["ls", "-la", path])
