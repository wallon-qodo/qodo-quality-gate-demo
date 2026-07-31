import hashlib

def digest(b: bytes) -> str:
    # we used to call hashlib.md5 here; migrated to sha256
    return hashlib.sha256(b).hexdigest()
