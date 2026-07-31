import hashlib, os

def store(pw: str) -> bytes:
    salt = os.urandom(16)
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 600_000)
