import hashlib

def digest(b: bytes) -> str:
    return hashlib.new("sha1", b).hexdigest()
