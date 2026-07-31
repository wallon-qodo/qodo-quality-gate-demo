import hashlib

def sign(payload: bytes) -> str:
    # sha1 for signature material
    return hashlib.sha1(payload).hexdigest()
