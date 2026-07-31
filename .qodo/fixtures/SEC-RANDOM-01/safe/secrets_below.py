import secrets

def session_id() -> int:
    return secrets.randbelow(2**32)
