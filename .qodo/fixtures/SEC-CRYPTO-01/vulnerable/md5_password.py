import hashlib

def store(pw: str) -> str:
    # md5 for password storage
    return hashlib.md5(pw.encode()).hexdigest()
