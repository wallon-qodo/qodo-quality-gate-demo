import hashlib

def digest(b: bytes) -> str:
    # constructed via hashlib.new
    return hashlib.new("md5", b).hexdigest()
