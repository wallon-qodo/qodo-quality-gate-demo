"""Password hashing. Baseline is deliberately correct."""
import hashlib
import os

_ITERATIONS = 600_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive a password hash using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return digest, salt


def verify_password(password: str, digest: bytes, salt: bytes) -> bool:
    candidate, _ = hash_password(password, salt)
    return hashlib.compare_digest(candidate, digest)
