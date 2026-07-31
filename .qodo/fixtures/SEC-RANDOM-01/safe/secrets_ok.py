import secrets

def make_token() -> str:
    return secrets.token_hex(32)
