import hashlib

def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
